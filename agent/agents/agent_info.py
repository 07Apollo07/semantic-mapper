"""Agent metadata definitions.

This module provides a single dictionary ``AGENT_INFO`` that describes each
available agent. The UI reads this dictionary to populate the dropdown and the
help expander, and the executor wrapper uses the ``agent_name`` key from
``AppState`` to instantiate the correct concrete executor.

Each entry contains:
- ``display_name`` – Human‑readable name shown in the UI.
- ``description`` – Short markdown description displayed in the expander.
- ``required_docs`` – List of source document types the agent expects.
- ``default_mappings`` – Brief note about default column mappings.
- ``can_regen_sql`` – Whether the agent supports SQL regeneration.
- ``can_regen_fsdm`` – Whether the agent supports FSDM regeneration.
"""

AGENT_INFO = {
    "DEFAULT": {
        "display_name": "Default Agent",
        "description": (
            "The original two‑step flow (FSDM Detective → Mapping Engineer) "
            "that works for most use‑cases. It supports both SQL and FSDM "
            "regeneration."
        ),
        "required_docs": ["PDF", "Excel"],
        "default_mappings": "Auto‑maps columns based on detected lineage.",
        "can_regen_sql": True,
        "can_regen_fsdm": True,
    },
    "LIC": {
        "display_name": "LIC Agent",
        "description": (
            "Custom agent for the LIC workflow. It may use a specialised "
            "prompt or additional domain knowledge. Currently supports only "
            "SQL regeneration."
        ),
        "required_docs": ["Excel"],
        "default_mappings": "Uses LIC‑specific column heuristics.",
        "can_regen_sql": True,
        "can_regen_fsdm": False,
    },
    "ALRAJI": {
        "display_name": "Alraji Agent",
        "description": (
            "Custom agent for the Alraji workflow. Designed for a different "
            "mapping strategy and currently does not support FSDM regeneration."
        ),
        "required_docs": ["Excel"],
        "default_mappings": "Alraji‑specific mapping rules.",
        "can_regen_sql": True,
        "can_regen_fsdm": False,
    },
}
