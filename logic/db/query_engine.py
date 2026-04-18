import sqlite3
import pandas as pd
from ..project_manager import ProjectManager

class FSDMQueryEngine:
    @staticmethod
    def query_table(project_name, table_name, query_text):
        """Executes a natural language-ish query (simplified) against an FSDM table."""
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        
        # In a full implementation, this would use an LLM to generate SQL
        # For now, return a preview of the table
        try:
            df = pd.read_sql(f"SELECT * FROM '{table_name}' LIMIT 10", conn)
            conn.close()
            return df
        except Exception as e:
            conn.close()
            return str(e)
