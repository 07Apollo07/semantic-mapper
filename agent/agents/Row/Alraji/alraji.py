"""Alraji Agent executor.

Currently inherits all behaviour from ``DefaultExecutor``. Override methods if
custom logic is required.
"""

from agent.agents.Row.Defaults.default import DefaultExecutor
# Import the Alraji‑specific (currently the generic Temp) custom mapping workflow
from agent.agents.Temp.mapping_custom import create_mapping_custom as create_alraji_mapping_custom
# Typing imports needed for the method signatures
from typing import Dict, Any, Optional
# AIMessage is used when parsing the LLM response
from langchain_core.messages import AIMessage

class AlrajiExecutor(DefaultExecutor):
    """Custom executor for the Alraji workflow.

    Like ``LicExecutor``, this class currently just inherits all behaviour from
    ``DefaultExecutor``. A simple log‑prefix is added so that when the wrapper
    selects this executor you can see ``[ALRAJI]`` in the log output, making the
    execution path easy to trace.
    """

    def _log(self, message: str):
        # Prefix log entries with the agent name for debugging.
        super()._log(f"[ALRAJI] {message}")

    # ---------------------------------------------------------------------
    # Override the custom‑mapping method to use the Alraji‑specific workflow.
    # ---------------------------------------------------------------------
    def process_row(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Invokes the Alraji‑specific Custom Mapping Agent.

        At the moment the Alraji workflow re‑uses the generic Temp mapping
        custom workflow, but we keep a separate method so that future Alraji‑
        specific prompts or logic can be added without touching the wrapper.
        """
        llm_config = self.state.get_llm_config()

        # Build the Alraji‑specific custom agent (currently the Temp version)
        custom_agent = create_alraji_mapping_custom(
            model_name=llm_config["model_name"],
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
            log_callback=self._log
        )

        inputs = {
            "row_data": row_data,
            "project_name": self.state.current_project,
            "feedback": feedback,
        }

        mapping_res = {
            "row_idx": row_idx,
            "source_info": row_data.get('source_info', {}),
            "target_info": row_data.get('target_info', {}),
            "target_table": row_data.get('target_table', 'unknown_table'),
            "transformation_specs": row_data.get('transformation_specs', {}),
            "fsdm_intent": "",
            "fsdm_findings": "",
            "fsdm_reasoning": "",
            "fsdm_recommended_sources": [],
            "fsdm_status": "Not Applicable",
            "mapping_status": "Pending",
        }

        try:
            res = custom_agent.invoke(inputs)
            last_msg = res['messages'][-1]
            if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                output_call = next((tc for tc in last_msg.tool_calls if tc['name'] == 'MappingOutput'), None)
                if output_call:
                    args = output_call['args']
                    mapping_res.update({
                        "mapping_status": "Complete",
                        "transformation_type": args.get('transformation_type'),
                        "transformation_logic": args.get('transformation_logic'),
                        "reasoning": args.get('reasoning'),
                    })
                    self._log(f"✅ [Alraji Custom Agent] Mapping generated.")
                    return mapping_res
            self._log(f"❌ [Alraji Custom Agent] No structured output.")
            mapping_res["mapping_status"] = "Error: Failed to call MappingOutput."
            return mapping_res
        except Exception as e:
            self._log(f"❌ [Alraji Custom Agent] Error: {str(e)}")
            mapping_res["mapping_status"] = f"Error: {str(e)}"
            return mapping_res
