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
                
                new_columns.append(combined.strip())
            
            df.columns = new_columns
            df = df.iloc[2:].reset_index(drop=True)
            return df
        elif len(df) == 1:
            df.columns = df.iloc[0].fillna("").astype(str)
            return df.iloc[1:].reset_index(drop=True)

    return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)

class DBService:
    @staticmethod
    def sync(project_name, item, prefix: str):
        """
        Processes and syncs selected sheets to SQLite.
        Drops tables if a sheet is deselected.
        """
        file_bytes = item["bytes"]
        for s_name, s_info in item["sheets"].items():
            table_name = prefix + s_name
            
            # Case 1: Sheet selected but not indexed_sql -> Add
            if s_info.get("selected") and not s_info.get("indexed_sql"):
                combine = s_info.get("combine_headers", False)
                df = preprocess_sheet(file_bytes, s_name, combine)
                ProjectManager.save_df_to_sql(project_name, table_name, df)
                s_info["indexed_sql"] = True
                
            # Case 2: Sheet deselected but indexed_sql -> Remove
            elif not s_info.get("selected") and s_info.get("indexed_sql"):
                DBService.delete_table(project_name, table_name)
                s_info["indexed_sql"] = False
                
        return item

    @staticmethod
    def delete_all_tables_for_item(project_name, item, prefix: str):
        """Drops all tables associated with a file item using the provided prefix."""
        for s_name, s_info in item["sheets"].items():
            if s_info.get("indexed_sql"):
                DBService.delete_table(project_name, prefix + s_name)


    @staticmethod
    def delete_table(project_name, table_name):
        """Explicitly drops a table."""
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        sanitized_name = ProjectManager.get_sanitized_table_name(table_name)
        cursor.execute(f"DROP TABLE IF EXISTS {sanitized_name}")
        conn.commit()
        conn.close()

