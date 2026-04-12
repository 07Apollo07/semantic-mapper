import pandas as pd
from typing import Dict, Any, List, Optional
from agent.agents.fsdm_detective import create_fsdm_detective
from agent.agents.mapping_engineer import create_mapping_engineer
from agent.agents.agents_utils import FSDMDiscoveryState, SemanticMappingState
from logic.utils import get_cell_value
from langchain_core.messages import HumanMessage, AIMessage

class AgentExecutor:
    """
    Handles synchronous, row-by-row agent execution for both batch mapping 
    and single-row regeneration. Chains FSDM Detective and Mapping Engineer.
    """

    def __init__(self, state):
        self.state = state
        self.fsdm_detective = None
        self.mapping_engineer = None

    def _initialize_agents(self):
        if self.fsdm_detective is not None and self.mapping_engineer is not None:
            return
            
        llm_config = self.state.get_llm_config()
        
        if not llm_config.get("model_name"):
            self._log("⚠️ LLM Model not selected. Please configure LLM in the sidebar.")
            return

        self._log(f"🤖 Initializing Detective & Engineer for project: {self.state.current_project}...")

        try:
            retriever = self.state.v_manager.get_retriever()
            self.fsdm_detective = create_fsdm_detective(
                model_name=llm_config["model_name"],
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"]
            )
            self.mapping_engineer = create_mapping_engineer(
                retriever=retriever,
                model_name=llm_config["model_name"],
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"]
            )
        except Exception as e:
            self._log(f"❌ Failed to initialize agents: {str(e)}")
            self.fsdm_detective = None
            self.mapping_engineer = None

    def _log(self, message: str):
        self.state.add_log(message)
        print(message)

    def _get_table_metadata(self, table_name: str) -> str:
        """Finds metadata for a specific FSDM table from the state's inventory."""
        for item in self.state.fsdm_inventory:
            for s_name, s_info in item.get("sheets", {}).items():
                if s_name == table_name:
                    return s_info.get("metadata", "No metadata found for this table.")
        return "Table not found in FSDM inventory metadata."

    def process_row(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Invokes the FSDM Detective Agent followed by the Mapping Engineer Agent."""
        self._initialize_agents()
        
        if self.fsdm_detective is None or self.mapping_engineer is None:
            return {
                "row_idx": row_idx,
                "transformation_type": "ERROR",
                "transformation_logic": "Agents not initialized.",
                "reasoning": "Agent initialization failed."
            }

        source_info = row_data.get('source_info', {})
        source_table = source_info.get('table_name')
        
        # 1. Phase 1: FSDM Lineage Discovery (Detective)
        self._log(f"🕵️ [Detective] Tracing lineage for Row {row_idx} ({source_table})...")
        
        metadata = self._get_table_metadata(source_table)
        
        fsdm_inputs = {
            "source_info": source_info,
            "target_info": row_data.get('target_info', {}),
            "fsdm_instructions": "", 
            "metadata": metadata,
            "project_name": self.state.current_project,
            "messages": [HumanMessage(content=f"Trace lineage for {source_info.get('column_name')} in {source_table}.")]
        }
        if feedback:
            fsdm_inputs["feedback"] = feedback

        lineage_intent = "No lineage context provided."
        lineage_status = "Failed"

        try:
            fsdm_res = self.fsdm_detective.invoke(fsdm_inputs)
            # Extract output from tool call in last message
            last_msg = fsdm_res['messages'][-1]
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                # Find FSDMIntentOutput call
                intent_call = next((tc for tc in last_msg.tool_calls if tc['name'] == 'FSDMIntentOutput'), None)
                if intent_call:
                    lineage_intent = intent_call['args'].get('lineage_intent', "No intent generated.")
                    lineage_status = "Success"
                    self._log(f"✅ [Detective] Lineage traced.")
                else:
                    self._log(f"⚠️ [Detective] No structured output.")
            else:
                self._log(f"❌ [Detective] Failed to provide AIMessage with tool calls.")
        except Exception as e:
            self._log(f"❌ [Detective] Error: {str(e)}")
            lineage_intent = f"Error during discovery: {str(e)}"

        # 2. Phase 2: SQL Engineering (Engineer)
        self._log(f"⚙️ [Engineer] Generating SQL for Row {row_idx}...")
        
        mapping_inputs = {
            "source_info": source_info,
            "target_info": row_data.get('target_info', {}),
            "transformation_specs": row_data.get('transformation_specs', {}),
            "fsdm_lineage_intent": lineage_intent,
            "project_name": self.state.current_project,
            "messages": [HumanMessage(content="Generate the SQL mapping based on the provided lineage intent.")],
            "feedback": feedback
        }

        mapping_res = {
            "row_idx": row_idx,
            "target_table": row_data.get('target_info', {}).get('table_name'),
            "source_info": source_info,
            "target_info": row_data.get('target_info', {}),
            "transformation_specs": row_data.get('transformation_specs', {}),
            "fsdm_intent": lineage_intent,
            "fsdm_status": lineage_status,
            "mapping_status": "Pending"
        }

        try:
            eng_res = self.mapping_engineer.invoke(mapping_inputs)
            last_msg = eng_res['messages'][-1]
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                output_call = next((tc for tc in last_msg.tool_calls if tc['name'] == 'MappingOutput'), None)
                if output_call:
                    args = output_call['args']
                    mapping_res.update({
                        "mapping_status": "Complete",
                        "transformation_type": args.get('transformation_type'),
                        "transformation_logic": args.get('transformation_logic'),
                        "reasoning": args.get('reasoning')
                    })
                    self._log(f"✅ [Engineer] SQL Generated.")
                    return mapping_res
            
            self._log(f"❌ [Engineer] No structured output.")
            mapping_res["mapping_status"] = "Error: Failed to call MappingOutput."
            return mapping_res
        except Exception as e:
            self._log(f"❌ [Engineer] Error: {str(e)}")
            mapping_res["mapping_status"] = f"Error: {str(e)}"
            return mapping_res
