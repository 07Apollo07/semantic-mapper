"""LIC Agent executor.

Currently inherits all behaviour from ``DefaultExecutor``. Override methods if
custom logic is required.
"""

from agent.agents.Row.Defaults.default import DefaultExecutor
# Import the LIC‑specific custom mapping workflow
from agent.agents.LIC.mapping_custom import create_mapping_custom as create_lic_mapping_custom
# Typing imports needed for the method signatures
from typing import Dict, Any, Optional
# AIMessage is used when parsing the LLM response
from langchain_core.messages import AIMessage

class LicExecutor(DefaultExecutor):
    """Custom executor for the LIC workflow.

    Currently it inherits all behaviour from ``DefaultExecutor``. The class is
    provided so that future LIC‑specific customisations (different prompts,
    additional logging, etc.) can be added without changing the wrapper logic.
    For now we simply prepend a tag to log messages so it is easy to see which
    executor is being used during debugging.
    """

    def _log(self, message: str):
        # Prefix log entries with the agent name for easier tracing.
        super()._log(f"[LIC] {message}")

    # ---------------------------------------------------------------------
    # Override the custom‑mapping method to use the LIC‑specific workflow.
    # ---------------------------------------------------------------------
    def process_row(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Invokes the LIC‑specific Custom Mapping Agent.

        The default executor uses the generic ``Temp.mapping_custom`` workflow.
        LIC requires a richer prompt that pulls LIC‑specific table/column
        definitions, so we instantiate ``create_lic_mapping`` here.
        The rest of the logic mirrors ``DefaultExecutor.process_mapping_custom``.
        """
        llm_config = self.state.get_llm_config()

        # Build the LIC‑specific custom agent
        custom_agent = create_lic_mapping_custom(
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
            "fsdm_intent": "",  # Dummy – not used in custom flow
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
                    self._log(f"✅ [LIC Custom Agent] Mapping generated.")
                    return mapping_res
            # If we get here, the tool call was missing or malformed
            self._log(f"❌ [LIC Custom Agent] No structured output.")
            mapping_res["mapping_status"] = "Error: Failed to call MappingOutput."
            return mapping_res
        except Exception as e:
            self._log(f"❌ [LIC Custom Agent] Error: {str(e)}")
            mapping_res["mapping_status"] = f"Error: {str(e)}"
            return mapping_res

    # ---------------------------------------------------------------------
    # Compatibility shim for the generic ``process_mapping_only`` API.
    # ---------------------------------------------------------------------
    def process_mapping_only(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Alias that forwards to :meth:`process_row`.

        The ``AgentExecutor`` expects concrete executors to implement a
        ``process_mapping_only`` method with the same signature as
        ``process_row``. For the LIC executor the behavior is identical, so we
        simply delegate to ``process_row``.
        """
        return self.process_row(row_data, row_idx, feedback)
