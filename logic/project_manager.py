import os
import shutil
import json
import pandas as pd
from typing import List, Dict, Any, Optional
import io
import re # Import re for regex operations
import sqlite3 # Import sqlite3 for database operations

PROJECTS_DIR = "projects"

class ProjectManager:
    @staticmethod
    def list_projects() -> List[str]:
        if not os.path.exists(PROJECTS_DIR):
            os.makedirs(PROJECTS_DIR)
        return [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]

    @staticmethod
    def create_project(name: str) -> bool:
        path = os.path.join(PROJECTS_DIR, name)
        if os.path.exists(path):
            return False
        os.makedirs(path)
        os.makedirs(os.path.join(path, "files"))
        os.makedirs(os.path.join(path, "vector_store"))
        return True

    @staticmethod
    def delete_project(name: str) -> bool:
        path = os.path.join(PROJECTS_DIR, name)
        if os.path.exists(path):
            shutil.rmtree(path)
            return True
        return False

    @staticmethod
    def get_project_path(name: str) -> str:
        return os.path.join(PROJECTS_DIR, name)

    @staticmethod
    def save_file(project_name: str, filename: str, file_bytes: bytes, sub_dir: str = "files") -> str:
        """Saves a file to the project's sub-directory within files."""
        path = os.path.join(PROJECTS_DIR, project_name, sub_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(file_bytes)
        return path

    @staticmethod
    def load_file(project_name: str, filename: str, sub_dir: str = "files") -> Optional[bytes]:
        """Loads a file from the project's sub-directory within files."""
        path = os.path.join(PROJECTS_DIR, project_name, sub_dir, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None

    @staticmethod
    def delete_file(project_name: str, filename: str) -> bool:
        path = os.path.join(PROJECTS_DIR, project_name, "files", filename)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    @staticmethod
    def save_metadata(project_name: str, metadata: Dict[str, Any]):
        path = os.path.join(PROJECTS_DIR, project_name, "metadata.json")
        with open(path, "w") as f:
            json.dump(metadata, f, indent=4)

    @staticmethod
    def load_metadata(project_name: str) -> Dict[str, Any]:
        path = os.path.join(PROJECTS_DIR, project_name, "metadata.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def update_metadata(project_name: str, updates: Dict[str, Any]):
        """Merges updates into existing metadata and saves."""
        meta = ProjectManager.load_metadata(project_name)
        meta.update(updates)
        ProjectManager.save_metadata(project_name, meta)
    
    @staticmethod
    def save_dataframe(project_name: str, filename: str, df: pd.DataFrame):
        path = os.path.join(PROJECTS_DIR, project_name, filename)
        # Using Excel for now as that seems to be the preferred format in this app
        if filename.endswith(".xlsx"):
            df.to_excel(path, index=False)
        elif filename.endswith(".csv"):
            df.to_csv(path, index=False)
            
    @staticmethod
    def load_dataframe(project_name: str, filename: str) -> Optional[pd.DataFrame]:
        path = os.path.join(PROJECTS_DIR, project_name, filename)
        if os.path.exists(path):
            if filename.endswith(".xlsx"):
                return pd.read_excel(path)
            elif filename.endswith(".csv"):
                return pd.read_csv(path)
        return None

    @staticmethod
    def get_db_path(project_name: str) -> str:
        return os.path.join(PROJECTS_DIR, project_name, "mapping.db")

    @staticmethod
    def get_db_uri(project_name: str) -> str:
        path = os.path.abspath(ProjectManager.get_db_path(project_name))
        return f"sqlite:///{path}"

    @staticmethod
    def initialize_project_db(project_name: str):
        import sqlite3
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create final_mappings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS final_mappings (
                row_idx INTEGER PRIMARY KEY,
                target_table TEXT,
                source_info TEXT,
                target_info TEXT,
                transformation_specs TEXT,
                pre_mapping_insight TEXT,
                human_correction TEXT,
                validation_status TEXT,
                transformation_type TEXT,
                transformation_logic TEXT,
                reasoning TEXT
            )
        """)

        # Create instructions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instructions (
                scope TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()
        conn.close()

    @staticmethod
    def save_instructions(project_name: str, scope: str, value: str):
        import sqlite3
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO instructions (scope, value) VALUES (?, ?)
        """, (scope, value))
        conn.commit()
        conn.close()

    @staticmethod
    def get_instructions(project_name: str, scope: str) -> str:
        import sqlite3
        db_path = ProjectManager.get_db_path(project_name)
        if not os.path.exists(db_path):
            return ""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM instructions WHERE scope = ?", (scope,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ""

    @staticmethod
    def save_mapping_row(project_name: str, row_data: Dict[str, Any]):
        import sqlite3
        import json
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        target_table = str(row_data.get('target_table', '')).strip()
        
        # We use INSERT OR REPLACE to handle updates
        cursor.execute("""
            INSERT OR REPLACE INTO final_mappings (
                row_idx, target_table, source_info, target_info, transformation_specs,
                pre_mapping_insight, human_correction, validation_status,
                transformation_type, transformation_logic, reasoning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row_data.get('row_idx'),
            target_table,
            json.dumps(row_data.get('source_info')),
            json.dumps(row_data.get('target_info')),
            json.dumps(row_data.get('transformation_specs')),
            row_data.get('pre_mapping_insight'),
            row_data.get('human_correction'),
            row_data.get('validation_status', 'Pending'),
            row_data.get('transformation_type'),
            row_data.get('transformation_logic'),
            row_data.get('reasoning')
        ))
        conn.commit()
        conn.close()

    @staticmethod
    def get_mappings_by_table(project_name: str, target_table: str) -> List[Dict[str, Any]]:
        import sqlite3
        import json
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        target_table = str(target_table).strip()
        cursor.execute("SELECT * FROM final_mappings WHERE target_table = ?", (target_table,))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            res = dict(row)
            res['source_info'] = json.loads(res['source_info'])
            res['target_info'] = json.loads(res['target_info'])
            res['transformation_specs'] = json.loads(res['transformation_specs'])
            results.append(res)
            
        conn.close()
        return results

    @staticmethod
    def update_mapping_validation(project_name: str, row_idx: int, updates: Dict[str, Any]):
        import sqlite3
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [row_idx]
        
        cursor.execute(f"UPDATE final_mappings SET {set_clause} WHERE row_idx = ?", params)
        conn.commit()
        conn.close()

    @staticmethod
    def get_unique_target_tables(project_name: str) -> List[str]:
        import sqlite3
        db_path = ProjectManager.get_db_path(project_name)
        if not os.path.exists(db_path):
            return []
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT target_table FROM final_mappings")
            tables = [r[0] for r in cursor.fetchall() if r[0]]
            return sorted(tables)
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    @staticmethod
    def get_sanitized_table_name(table_name: str) -> str:
        """Centralized sanitization for FSDM table names."""
        sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name).lower()
        if sanitized_name[0].isdigit():
            sanitized_name = "t_" + sanitized_name
        return sanitized_name

    @staticmethod
    def save_df_to_sql(project_name: str, table_name: str, df: pd.DataFrame):
        import sqlite3
        
        sanitized_name = ProjectManager.get_sanitized_table_name(table_name)
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        try:
            if df.empty and len(df.columns) == 0:
                # An empty DataFrame with no columns produces invalid SQL like
                # CREATE TABLE foo () which SQLite rejects with "near ')'".
                # Just DROP the table so the slate is clean.
                conn.execute(f"DROP TABLE IF EXISTS {sanitized_name}")
                conn.commit()
            else:
                df.to_sql(sanitized_name, conn, if_exists='replace', index=False)
        finally:
            conn.close()
        return sanitized_name

    @staticmethod
    def rebuild_mapping_from_config(project_name: str, df: pd.DataFrame, mapping_config_identifiers: List[str]):
        """
        Filters the original Excel DataFrame based on column identifiers (titles or letters) 
        and saves the result to the 'mapping_sheet' table in SQLite.
        """
        import pandas as pd
        from .utils import excel_col_to_idx

        selected_indices = []
        # Default to empty
        filtered_df = pd.DataFrame()

        if df is not None:
            for ident in mapping_config_identifiers:
                if not ident:
                    continue  # Skip empty identifiers

                # Try direct column name first
                if ident in df.columns:
                    selected_indices.append(df.columns.get_loc(ident))
                else:
                    # Fallback: interpret as Excel-style column letter (A, B, AA ...)
                    idx = excel_col_to_idx(ident)
                    if idx is not None and 0 <= idx < len(df.columns):
                        selected_indices.append(idx)

            unique_indices = sorted(set(selected_indices))

            if unique_indices:
                filtered_df = df.iloc[:, unique_indices]
        
        # Save the filtered DataFrame to the mapping_sheet table
        ProjectManager.save_df_to_sql(project_name, "mapping_sheet", filtered_df)
        return filtered_df

    @staticmethod
    def load_df_from_sql(project_name: str, table_name: str) -> pd.DataFrame:
        """Loads a table from the project's SQLite DB into a DataFrame."""
        import sqlite3
        import re

        sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name).lower()
        if sanitized_name[0].isdigit():
            sanitized_name = "t_" + sanitized_name

        db_path = ProjectManager.get_db_path(project_name)
        if not os.path.exists(db_path):
            return pd.DataFrame()

        conn = sqlite3.connect(db_path)
        try:
            df = pd.read_sql_query(f"SELECT * FROM {sanitized_name}", conn)
            return df
        except Exception:
            return pd.DataFrame()
        finally:
            conn.close()

    @staticmethod
    def drop_excel_sheets_from_db(project_name: str, filename: str, sheets_info: Dict[str, Dict[str, Any]]):
        """Drops SQLite tables corresponding to indexed sheets of a deleted Excel file."""
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        tables_dropped = []
        for sheet_name, info in sheets_info.items():
            if info.get("indexed", False): # Only drop if it was indexed (i.e., present in DB)
                base_table_name = "FSDM/ETL_" + sheet_name
                # Apply the same sanitization and prefixing as save_df_to_sql
                sanitized_base = re.sub(r'[^a-zA-Z0-9_]', '_', base_table_name).lower()
                if sanitized_base.startswith("t_"): # Check if it already has the prefix from save_df_to_sql
                    actual_table_name = sanitized_base
                elif sanitized_base[0].isdigit():
                    actual_table_name = "t_" + sanitized_base
                else:
                    actual_table_name = sanitized_base # Should not happen with FSDM/ETL prefix, but for completeness
                
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {actual_table_name}")
                    print(f"Dropped table '{actual_table_name}' for sheet '{sheet_name}' from project '{project_name}'.")
                    tables_dropped.append(actual_table_name)
                except sqlite3.Error as e:
                    print(f"Error dropping table '{actual_table_name}' for sheet '{sheet_name}' in project '{project_name}': {e}")
        
        if tables_dropped:
            conn.commit()
            print(f"Dropped tables: {', '.join(tables_dropped)}")
        else:
            print(f"No indexed sheets found for file '{filename}' in project '{project_name}' to drop from DB.")
        
        conn.close()
