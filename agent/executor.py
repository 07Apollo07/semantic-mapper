import pandas as pd
from typing import Dict, Any, List, Optional
from agent.graph import create_agent, create_intent_agent
from logic.utils import get_cell_value

class AgentExecutor:
    """
    Handles synchronous, row-by-row agent execution for both batch mapping 
    and single-row regeneration. Includes a retry loop for robust output.
    """

    def __init__(self, state):
        self.state = state
        self.agent = None

    def _initialize_agent(self):
        if self.agent is not None:
            return
            
        llm_config = self.state.get_llm_config()
        
        # Check for model name
        if not llm_config.get("model_name"):
            self._log("⚠️ LLM Model not selected. Please configure LLM in the sidebar.")
            return

        retriever = self.state.v_manager.get_retriever()
        
        self._log(f"🤖 Initializing ReAct Agent for project: {self.state.current_project}...")

        try:
            self.agent = create_agent(
                retriever,
                model_name=llm_config["model_name"],
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"],
                log_callback=self._log,
                project_name=self.state.current_project
            )
        except Exception as e:
            self._log(f"❌ Failed to initialize agent: {str(e)}")
            self.agent = None

    def _log(self, message: str):
        # Always log to state and print to console for "real-time" visibility
        self.state.add_log(message)
        print(message)

    def extract_row_info(self, row: pd.Series, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts source, target, and transformation info from a dataframe row."""
        s = config.get("source", {})
        t = config.get("target", {})
        tr = config.get("transformation", {})

        source_info = {
            "subject_area": get_cell_value(row, s.get("subj")),
            "db_name": get_cell_value(row, s.get("db")),
            "table_name": get_cell_value(row, s.get("tbl")),
            "column_name": get_cell_value(row, s.get("col")),
            "datatype": get_cell_value(row, s.get("type"))
        }
        target_info = {
            "subject_area": get_cell_value(row, t.get("subj")),
            "db_name": get_cell_value(row, t.get("db")),
            "table_name": get_cell_value(row, t.get("tbl")),
            "column_name": get_cell_value(row, t.get("col")),
            "datatype": get_cell_value(row, t.get("type"))
        }
        transformation_specs = {
            "type": get_cell_value(row, tr.get("type")),
            "condition": get_cell_value(row, tr.get("cond")),
            "remarks": get_cell_value(row, tr.get("remarks"))
        }

        return {
            "source_info": source_info,
            "target_info": target_info,
            "transformation_specs": transformation_specs
        }

    def process_row(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Invokes the agent for a single row of data with a retry loop."""
        self._initialize_agent()
        
        if self.agent is None:
            return {
                "row_idx": row_idx,
                "source_info": row_data["source_info"],
                "target_info": row_data["target_info"],
                "transformation_specs": row_data["transformation_specs"],
                "transformation_type": "ERROR",
                "transformation_logic": "LLM not configured.",
                "reasoning": "Agent initialization failed or model not selected."
            }

        self._log(f"🚀 [Agent] Starting SQL Generation for Row {row_idx}...")
        self._log(f"   Target: {row_data['target_info'].get('table_name')}.{row_data['target_info'].get('column_name')}")
        
        # Initialize inputs
        inputs = {
            **row_data,
            "project_name": self.state.current_project,
            "global_instructions": self.state.global_instructions,
            "pre_mapping_insight": row_data.get("pre_mapping_insight", ""),
            "messages": [],
            "context": "",
            "transformation_type": "",
            "transformation_logic": "",
            "reasoning": ""
        }
        if feedback:
            inputs["feedback"] = feedback

        max_retries = 5
        attempt = 0
        
        while attempt < max_retries:
            attempt += 1
            if attempt > 1:
                self._log(f"🔄 [Agent] Retry attempt {attempt}/{max_retries} for Row {row_idx}...")
            
            try:
                res = self.agent.invoke(inputs)
                
                # Log assistant messages and tool calls
                if "messages" in res:
                    for msg_idx, msg in enumerate(res["messages"]):
                        role = "Assistant"
                        if hasattr(msg, "type"):
                            role = msg.type.capitalize()
                        elif isinstance(msg, dict) and "role" in msg:
                            role = msg["role"].capitalize()
                        
                        content = ""
                        if hasattr(msg, "content"):
                            content = msg.content
                        elif isinstance(msg, dict) and "content" in msg:
                            content = msg["content"]
                        
                        if content:
                            # Truncate long content for logs
                            log_content = content[:200] + "..." if len(content) > 200 else content
                            self._log(f"🗨️ [{role} - Step {msg_idx}]: {log_content}")
                        
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                self._log(f"🛠️ [Tool Call]: {tc['name']}({tc['args']})")
                
                # Validation: Did we get the structured output?
                if res.get('transformation_logic') and res.get('transformation_type') != "ERROR":
                    self._log(f"✅ [Agent] Success Row {row_idx}: {res.get('transformation_type')}")
                    return {
                        "row_idx": row_idx,
                        "source_info": row_data["source_info"],
                        "target_info": row_data["target_info"],
                        "transformation_specs": row_data["transformation_specs"],
                        **res
                    }
                else:
                    self._log(f"⚠️ [Agent] Row {row_idx}: Attempt {attempt} failed to yield valid logic.")
                    # Add feedback for the next attempt
                    inputs["feedback"] = f"Previous attempt failed. Please ensure you use the TransformationOutput tool correctly. Details: {res.get('reasoning', 'Unknown error')}"
                    
            except Exception as e:
                self._log(f"❌ [Agent] Error on attempt {attempt}: {str(e)}")
                # If it's a tool error, it might be recoverable.
                # Append error to messages and try again.
                from langchain_core.messages import HumanMessage
                inputs["messages"] = inputs.get("messages", []) + [
                    HumanMessage(content=f"System: An error occurred during tool execution: {str(e)}. Please correct your approach and try again.")
                ]

        # If we reached here, we failed after max_retries
        self._log(f"🛑 [Agent] Failed to generate valid SQL for Row {row_idx} after {max_retries} attempts.")
        return {
            "row_idx": row_idx,
            "source_info": row_data["source_info"],
            "target_info": row_data["target_info"],
            "transformation_specs": row_data["transformation_specs"],
            "transformation_type": "ERROR",
            "transformation_logic": "Max retries exceeded.",
            "reasoning": "The agent was unable to provide a structured output within the allowed attempts."
        }

    def generate_insight(self, row_data: Dict[str, Any], feedback: Optional[str] = None) -> str:
        """Generates a technical hypothesis/intent for a row using the Intent Agent."""
        llm_config = self.state.get_llm_config()
        if not llm_config.get("model_name"):
            self._log("⚠️ [Preprocessing] LLM Model not selected.")
            return "Please configure LLM in the sidebar first."

        self._log(f"🔍 [Preprocessing] Generating robust insight for Row {row_data['row_idx']}...")
        
        retriever = self.state.v_manager.get_retriever()
        
        try:
            intent_agent = create_intent_agent(
                retriever,
                model_name=llm_config["model_name"],
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"],
                log_callback=self._log,
                project_name=self.state.current_project
            )
            
            inputs = {
                **row_data,
                "project_name": self.state.current_project,
                "global_instructions": self.state.global_instructions,
                "messages": [],
                "feedback": feedback if feedback else ""
            }
            
            res = intent_agent.invoke(inputs)
            
            # The process_node in intent_agent sets 'pre_mapping_insight'
            insight = res.get("pre_mapping_insight", "Failed to generate structured insight.")
            
            if insight:
                self._log(f"✨ [Preprocessing] Insight generated for Row {row_data['row_idx']}.")
                return insight
            else:
                return "Error: Intent agent did not return an insight."

        except Exception as e:
            self._log(f"❌ [Preprocessing] Error generating insight: {str(e)}")
            return f"Error generating insight: {str(e)}"
