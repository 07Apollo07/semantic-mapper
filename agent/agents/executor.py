import pandas as pd
from typing import Dict, Any, List, Optional
from agent.agents.fsdm_detective import create_fsdm_detective
# from agent.agents.mapping_engineer import create_mapping_engineer
from agent.agents.mapping_oneshot import create_mapping_oneshot
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
            self.mapping_engineer = create_mapping_oneshot(
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

    def _get_fsdm_metadata(self) -> str:
        """Finds and formats metadata for all FSDM tables from the state's inventory."""
        formatted_metadata = ""
        for item in self.state.fsdm_inventory:
            for s_name, s_info in item.get("sheets", {}).items():
                meta = s_info.get("metadata", "No metadata provided.")
                s_name_low = s_name.lower()
                formatted_metadata += f"Metadata for table fsdm_etl_{s_name_low}:\n{meta}\n\n"
        
        return formatted_metadata if formatted_metadata else "No metadata found for FSDM tables."

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
        
        metadata = self._get_fsdm_metadata()
        
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

        lineage_intent = {} # Dictionary to hold full discovery report
        lineage_status = "Failed"

        try:
            fsdm_res = self.fsdm_detective.invoke(fsdm_inputs)
            # Extract output from tool call in last message
            last_msg = fsdm_res['messages'][-1]
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                # Find FSDMIntentOutput call
                intent_call = next((tc for tc in last_msg.tool_calls if tc['name'] == 'FSDMIntentOutput'), None)
                if intent_call:
                    lineage_intent = intent_call['args']
                    lineage_status = "Success"
                    self._log(f"✅ [Detective] Lineage traced and discovery report gathered.")
                else:
                    self._log(f"⚠️ [Detective] No structured output.")
            else:
                self._log(f"❌ [Detective] Failed to provide AIMessage with tool calls.")
        except Exception as e:
            self._log(f"❌ [Detective] Error: {str(e)}")
            lineage_intent = {"error": str(e)}

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

    def process_fsdm_only(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Regenerates only the FSDM Discovery Phase (Phase 1)."""
        self._initialize_agents()
        
        if self.fsdm_detective is None:
            return {"row_idx": row_idx, "fsdm_status": "Error: Detective not initialized."}

        source_info = row_data.get('source_info', {})
        self._log(f"🕵️ [Detective] Regenerating lineage for Row {row_idx}...")
        
        metadata = self._get_fsdm_metadata()
        fsdm_inputs = {
            "source_info": source_info,
            "target_info": row_data.get('target_info', {}),
            "fsdm_instructions": "", 
            "metadata": metadata,
            "project_name": self.state.current_project,
            "messages": [HumanMessage(content=f"Regenerate lineage for {source_info.get('column_name')}.")],
            "feedback": feedback
        }

        lineage_intent = {}
        lineage_status = "Failed"

        try:
            fsdm_res = self.fsdm_detective.invoke(fsdm_inputs)
            last_msg = fsdm_res['messages'][-1]
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                intent_call = next((tc for tc in last_msg.tool_calls if tc['name'] == 'FSDMIntentOutput'), None)
                if intent_call:
                    lineage_intent = intent_call['args']
                    lineage_status = "Success"
                    self._log(f"✅ [Detective] Lineage regeneration successful.")
                else:
                    self._log(f"⚠️ [Detective] No structured output.")
            else:
                self._log(f"❌ [Detective] Failed to provide AIMessage with tool calls.")
        except Exception as e:
            self._log(f"❌ [Detective] Error: {str(e)}")
            lineage_intent = {"error": str(e)}

        return {
            "row_idx": row_idx,
            "fsdm_intent": lineage_intent,
            "fsdm_status": lineage_status
        }

    def process_mapping_only(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Regenerates only the SQL Engineering Phase (Phase 2)."""
        self._initialize_agents()
        
        if self.mapping_engineer is None:
            return {"row_idx": row_idx, "mapping_status": "Error: Engineer not initialized."}

        source_info = row_data.get('source_info', {})
        # We reuse existing fsdm_intent if available in row_data
        lineage_intent = row_data.get('fsdm_intent', {})
        
        self._log(f"⚙️ [Engineer] Regenerating SQL for Row {row_idx}...")
        
        mapping_inputs = {
            "source_info": source_info,
            "target_info": row_data.get('target_info', {}),
            "transformation_specs": row_data.get('transformation_specs', {}),
            "fsdm_lineage_intent": lineage_intent,
            "project_name": self.state.current_project,
            "messages": [HumanMessage(content="Regenerate SQL mapping.")],
            "feedback": feedback
        }

        mapping_res = {
            "row_idx": row_idx,
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
                    self._log(f"✅ [Engineer] SQL regenerated.")
                    return mapping_res
            
            self._log(f"❌ [Engineer] No structured output.")
            mapping_res["mapping_status"] = "Error: Failed to call MappingOutput."
            return mapping_res
        except Exception as e:
            self._log(f"❌ [Engineer] Error: {str(e)}")
            mapping_res["mapping_status"] = f"Error: {str(e)}"
            return mapping_res
