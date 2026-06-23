import logging
import sqlite3
import pandas as pd
import io
from typing import List, Dict, Any, Optional
from logic.project_manager import ProjectManager
from logic.vector_store.service import VectorStoreService
from logic.vector_store.processors import process_excel_sheets, split_documents, process_pdf

logger = logging.getLogger(__name__)

class IngestionService:
    @staticmethod
    def sync_to_sql(project_name: str, item: Dict[str, Any], table_prefix: str):
        """Processes and syncs selected sheets to SQLite."""
        file_bytes = item["bytes"]
        for s_name, s_info in item["sheets"].items():
            table_name = table_prefix + s_name
            
            if s_info.get("selected") and not s_info.get("indexed_sql"):
                # Use FSDM preprocessing logic
                from logic.fsdm.service import preprocess_sheet
                combine = s_info.get("combine_headers", False)
                df = preprocess_sheet(file_bytes, s_name, combine)
                ProjectManager.save_df_to_sql(project_name, table_name, df)
                s_info["indexed_sql"] = True
                
            elif not s_info.get("selected") and s_info.get("indexed_sql"):
                IngestionService.delete_sql_table(project_name, table_name)
                s_info["indexed_sql"] = False
        return item

    @staticmethod
    def sync_to_vector(v_service: VectorStoreService, item: Dict[str, Any]):
        """Processes and syncs selected sheets to Vector Store."""
        file_bytes = item["bytes"]
        name = item["name"]
        
        # Excel-based sync logic (unified for sheets)
        if item["type"] == "excel":
            for s_name, s_info in item.get("sheets", {}).items():
                selected = s_info.get("selected", False)
                indexed = s_info.get("indexed_vec", False)

                if selected and not indexed:
                    logger.info(f"Indexing Excel Sheet: {name} [{s_name}]")
                    docs = process_excel_sheets(file_bytes, name, [s_name])
                    chunks = split_documents(docs)
                    v_service.manager.add_documents(chunks)
                    s_info["indexed_vec"] = True
                elif not selected and indexed:
                    logger.info(f"Removing Excel Sheet: {name} [{s_name}]")
                    v_service.manager.remove_document(name, s_name)
                    s_info["indexed_vec"] = False
        # PDF logic (keep simple)
        elif item["type"] == "pdf":
             selected = item.get("selected", False)
             indexed = item.get("indexed_vec", False)
             if selected and not indexed:
                 logger.info(f"Indexing PDF: {name}")
                 docs = process_pdf(file_bytes, name)
                 chunks = split_documents(docs)
                 v_service.manager.add_documents(chunks)
                 item["indexed_vec"] = True
             elif not selected and indexed:
                 logger.info(f"Removing PDF: {name}")
                 v_service.manager.remove_document(name)
                 item["indexed_vec"] = False
        return item

    @staticmethod
    def delete_sql_table(project_name: str, table_name: str):
        db_path = ProjectManager.get_db_path(project_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        sanitized_name = ProjectManager.get_sanitized_table_name(table_name)
        cursor.execute(f"DROP TABLE IF EXISTS {sanitized_name}")
        conn.commit()
        conn.close()
