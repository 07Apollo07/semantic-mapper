import logging
import sqlite3
import pandas as pd
import io
from ..project_manager import ProjectManager

logger = logging.getLogger(__name__)

def preprocess_sheet(file_bytes, sheet_name, combine_headers=True):
    """
    Reads an Excel sheet and applies header preprocessing.
    If combine_headers is True, merges first two rows.
    Handles merged cells in the first row by forward-filling values.
    """
    if combine_headers:
        # Read without header to manually process the first two rows
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=None)
        
        if len(df) >= 2:
            # Row 0 of df is Row 1 of Excel
            # Row 1 of df is Row 2 of Excel
            
            # Forward fill the first row to handle merged cells (e.g., "Source" over 4 columns)
            header1 = pd.Series(df.iloc[0]).ffill().fillna("").astype(str)
            header2 = pd.Series(df.iloc[1]).fillna("").astype(str)
            
            new_columns = []
            for h1, h2 in zip(header1, header2):
                h1 = h1.strip()
                h2 = h2.strip()
                if h1 and h2:
                    if h1.lower() == h2.lower():
                        combined = h1
                    else:
                        combined = f"{h1}_{h2}"
                elif h1:
                    combined = h1
                else:
                    combined = h2
                
                # Replace spaces with underscores for better DB compatibility if desired, 
                # but following user preference "source_table name" (mixture)
                # Let's keep it close to their example but ensure it's clean.
                new_columns.append(combined.strip())
            
            df.columns = new_columns
            df = df.iloc[2:].reset_index(drop=True)
            return df
        elif len(df) == 1:
            df.columns = df.iloc[0].fillna("").astype(str)
            return df.iloc[1:].reset_index(drop=True)

    return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)

class FSDMService:
    @staticmethod
    def sync(project_name, item):
        """
        Processes and syncs selected sheets from an FSDM file to SQLite.
        Drops tables if a sheet is deselected.
        """
        file_bytes = item["bytes"]
        for s_name, s_info in item["sheets"].items():
            table_name = "FSDM/ETL_" + s_name
            
            # Case 1: Sheet selected but not indexed -> Add
            if s_info.get("selected") and not s_info.get("indexed"):
                combine = s_info.get("combine_headers", False)
                df = preprocess_sheet(file_bytes, s_name, combine)
                ProjectManager.save_df_to_sql(project_name, table_name, df)
                s_info["indexed"] = True
                
            # Case 2: Sheet deselected but indexed -> Remove
            elif not s_info.get("selected") and s_info.get("indexed"):
                FSDMService.delete_table(project_name, table_name)
                s_info["indexed"] = False
                
        return item

    @staticmethod
    def delete_all_tables_for_item(project_name, item):
        """Drops all tables associated with an FSDM file item."""
        for s_name, s_info in item["sheets"].items():
            if s_info.get("indexed"):
                FSDMService.delete_table(project_name, "FSDM/ETL_" + s_name)

    @staticmethod
    def delete_table(project_name, table_name):
        """Explicitly drops an FSDM table."""
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        sanitized_name = ProjectManager.get_sanitized_table_name(table_name)
        cursor.execute(f"DROP TABLE IF EXISTS {sanitized_name}")
        conn.commit()
        conn.close()

    @staticmethod
    def get_fsdm_schema(project_name):
        """
        Returns a JSON-ready map of all uploaded FSDM tables and their column names.
        """
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all FSDM tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fsdm_etl_%'")
        tables = cursor.fetchall()
        
        schema = {}
        for table in tables:
            table_name = table[0]
            df = pd.read_sql(f"SELECT * FROM '{table_name}' LIMIT 1", conn)
            schema[table_name] = list(df.columns)
            
        conn.close()
        return schema
