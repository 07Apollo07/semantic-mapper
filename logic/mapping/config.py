from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class MappingConfig:
    """Configuration for column mapping templates and per-sheet overrides."""
    data_start_row: int = 1 # Row number where data begins (1-based)
    source_fields: Dict[str, str] = field(default_factory=lambda: {
        "subj": "", "db": "", "tbl": "", "col": "", "type": ""
    })
    target_fields: Dict[str, str] = field(default_factory=lambda: {
        "subj": "", "db": "", "tbl": "", "col": "", "type": ""
    })
    trans_fields: Dict[str, str] = field(default_factory=lambda: {
        "type": "", "cond": "", "remarks": ""
    })
    
    # Physical source definition fields, mirroring source_fields structure
    physical_source_fields: Dict[str, str] = field(default_factory=lambda: {
        "subj": "", "db": "", "tbl": "", "col": "", "type": ""
    })

    @staticmethod
    def update_inventory(metadata: Dict[str, Any], inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Updates the mapping_inventory within the project metadata.
        """
        metadata["mapping_inventory"] = inventory
        return metadata

    @staticmethod
    def get_inventory(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieves the mapping_inventory from project metadata."""
        return metadata.get("mapping_inventory", [])
