import logging
import sqlite3
import os
import pandas as pd
from typing import List, Dict, Any
from ..project_manager import ProjectManager
from .config import MappingConfig

# Configure logger to output to stdout for Streamlit visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MappingService:
    @staticmethod
    def normalize_sheet(df: pd.DataFrame, config: MappingConfig) -> pd.DataFrame:
        """
        Normalizes a raw sheet DataFrame by extracting user-specified columns.
        Uses column identifiers (names or letters A, B...) provided in config.
        Sets internal standard headers for consistent joining.
        """
        from ..utils import excel_col_to_idx
        
        # Standard columns we always want in the DB for our unified view
        standard_cols = [
            "source_subject", "source_db", "source_table", "source_column", "source_type",
            "target_subject", "target_db", "target_table", "target_column", "target_type",
            "trans_type", "trans_condition", "remarks"
        ]
        
        mapping_map = {
            "source_subject": config.source_fields.get("subj"),
            "source_db": config.source_fields.get("db"),
            "source_table": config.source_fields.get("tbl"),
            "source_column": config.source_fields.get("col"),
            "source_type": config.source_fields.get("type"),
            "target_subject": config.target_fields.get("subj"),
            "target_db": config.target_fields.get("db"),
            "target_table": config.target_fields.get("tbl"),
            "target_column": config.target_fields.get("col"),
            "target_type": config.target_fields.get("type"),
            "trans_type": config.trans_fields.get("type"),
            "trans_condition": config.trans_fields.get("cond"),
            "remarks": config.trans_fields.get("remarks")
        }

        extracted_data = {}
        # Convert data_start_row to 0-based index. 
        # User input is 1-based, df.iloc is 0-based.
        start_row_idx = max(0, config.data_start_row - 1)
        
        for internal_name, user_col in mapping_map.items():
            if not user_col:
                continue
            
            # Identify column index
            col_idx = None
            if user_col in df.columns:
                col_idx = df.columns.get_loc(user_col)
            else:
                idx = excel_col_to_idx(user_col)
                if idx is not None and idx < len(df.columns):
                    col_idx = idx
            
            if col_idx is not None:
                # Extract data: start from user-defined row, keep all rows below
                extracted_data[internal_name] = df.iloc[start_row_idx:, col_idx].reset_index(drop=True)
            else:
                logger.warning(f"Column {user_col} not found in sheet")
                extracted_data[internal_name] = None
        
        # Create DataFrame with standard columns
        norm_df = pd.DataFrame(extracted_data)
        
        # Ensure all standard columns exist, filling missing ones with None
        for col in standard_cols:
            if col not in norm_df.columns:
                norm_df[col] = None
                
        return norm_df[standard_cols]

    @staticmethod
    def sync_sheet(project_name: str, item: Dict[str, Any], s_name: str) -> str:
        """Syncs a single sheet to SQLite and returns the table name."""
        filename = item["name"]
        file_path = os.path.join("files/mapping", filename)
        logger.info(f"Loading sheet {s_name} from {file_path}")
        raw_df = ProjectManager.load_dataframe(project_name, file_path)
        
        if raw_df is None:
            logger.error(f"Failed to load dataframe from {file_path}")
            raise ValueError(f"Could not load {filename}")

        s_info = item["sheets"][s_name]
        cfg_data = s_info.get("config")
        config = MappingConfig(**cfg_data) if isinstance(cfg_data, dict) else MappingConfig()
        # Normalization
        norm_df = MappingService.normalize_sheet(raw_df, config)
        logger.info(f"Columns in raw sheet: {list(raw_df.columns)}")
        logger.info(f"Normalized sheet {s_name}, rows={len(norm_df)}")

        
        sanitized_name = ProjectManager.get_sanitized_table_name(f"mapping_{filename}_{s_name}")
        
        db_path = ProjectManager.get_db_path(project_name)
        logger.info(f"Writing to database at {db_path}, table={sanitized_name}")
        conn = sqlite3.connect(db_path)
        norm_df.to_sql(sanitized_name, conn, if_exists='replace', index=False)
        
        # Verify content
        count = conn.execute(f"SELECT COUNT(*) FROM {sanitized_name}").fetchone()[0]
        logger.info(f"Verified rows in {sanitized_name}: {count}")
        
        conn.commit()
        conn.close()
        
        return sanitized_name

    @staticmethod
    def sync_mappings(project_name: str, inventory: List[Dict[str, Any]]):
        """
        1. Drops existing mapping tables and views.
        2. Creates new mapping tables for each selected sheet.
        3. Creates a unified view for the agent.
        """
        logger.info("Inside sync mapping")
        db_path = ProjectManager.get_db_path(project_name)
        logger.info(f"Syncing all mappings for {project_name}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Clean up old structures
        cursor.execute("DROP VIEW IF EXISTS unified_mapping_view")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mapping_%'")
        old_tables = cursor.fetchall()
        for table in old_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
            
        # 2. Recreate tables
        union_queries = []
        for item in inventory:
            for s_name, s_info in item.get("sheets", {}).items():
                if s_info.get("selected"):
                    tbl_name = MappingService.sync_sheet(project_name, item, s_name)
                    union_queries.append(f"SELECT *, '{item['name']}' as _src_file, '{s_name}' as _src_sheet FROM {tbl_name}")
        
        # 3. Create view
        if union_queries:
            view_sql = " UNION ALL ".join(union_queries)
            logger.info(f"Creating view with sql: {view_sql}")
            cursor.execute(f"CREATE VIEW unified_mapping_view AS {view_sql}")
            
        conn.commit()
        conn.close()
        logger.info("Syncing completed.")
