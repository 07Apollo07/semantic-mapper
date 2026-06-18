"""Wrapper executor that selects the concrete agent implementation based on the
selected ``agent_name`` stored in ``AppState``.

The original implementation (now ``DefaultExecutor``) lives in the same
package. ``LicExecutor`` and ``AlrajiExecutor`` are thin subclasses that can
override behaviour if needed.

The wrapper exposes the same public API used throughout the codebase:
* ``process_row``
* ``process_fsdm_only``
* ``process_mapping_only``
* ``process_mapping_custom``
* ``process_table_group``
* ``can_regen_sql``
* ``can_regen_fsdm``

It forwards calls to the concrete executor instance.
"""

from typing import Dict, Any, List, Optional

from agent.agents.Row.Defaults.default import DefaultExecutor  # renamed original class
from agent.agents.agent_info import AGENT_INFO


class AgentExecutor:
    """Factory/wrapper that delegates to the selected concrete executor.

    The ``state`` object provides ``agent_name`` which determines which executor
    class to instantiate. The executor is created lazily on first use.
    """

    def __init__(self, state):
        self.state = state
        self._executor: Optional[object] = None

    def _get_executor(self):
        if self._executor is not None:
            return self._executor
        # Determine which executor class to use
        name = getattr(self.state, "agent_name", "DEFAULT")
        # Fallback to DEFAULT if unknown
        if name not in AGENT_INFO:
            name = "DEFAULT"
        if name == "DEFAULT":
            self._executor = DefaultExecutor(self.state)
        elif name == "LIC":
            from agent.agents.Row.LIC.lic import LicExecutor
            self._executor = LicExecutor(self.state)
        elif name == "ALRAJI":
            from agent.agents.Row.Alraji.alraji import AlrajiExecutor
            self._executor = AlrajiExecutor(self.state)
        else:
            self._executor = DefaultExecutor(self.state)
        return self._executor

    # ----- Capability flags -----
    @property
    def can_regen_sql(self) -> bool:
        name = getattr(self.state, "agent_name", "DEFAULT")
        return AGENT_INFO.get(name, AGENT_INFO["DEFAULT"]).get("can_regen_sql", False)

    @property
    def can_regen_fsdm(self) -> bool:
        name = getattr(self.state, "agent_name", "DEFAULT")
        return AGENT_INFO.get(name, AGENT_INFO["DEFAULT"]).get("can_regen_fsdm", False)

    # ----- Delegated methods -----
    def process_row(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        return self._get_executor().process_row(row_data, row_idx, feedback)

    def process_fsdm_only(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        return self._get_executor().process_fsdm_only(row_data, row_idx, feedback)

    def process_mapping_only(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        return self._get_executor().process_mapping_only(row_data, row_idx, feedback)

    # def process_mapping_custom(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
    #     return self._get_executor().process_mapping_custom(row_data, row_idx, feedback)

    def process_table_group(self, table_name: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._get_executor().process_table_group(table_name, rows)