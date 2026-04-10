import logging
from typing import List, Dict, Any, Optional
from .manager import VectorStoreManager
from .processors import process_pdf, process_excel_sheets, split_documents

logger = logging.getLogger(__name__)

class VectorStoreService:
    def __init__(self, manager: VectorStoreManager):
        self.manager = manager

    def sync_project(self, inventory: List[Dict[str, Any]]):
        """
        Synchronizes the vector store with the provided inventory.
        Ensures that selected items are indexed and unselected items are removed.
        """
        for item in inventory:
            if item["type"] == "pdf":
                self._handle_pdf_sync(item)
            elif item["type"] == "excel":
                self._handle_excel_sync(item)

    def _handle_pdf_sync(self, item: Dict[str, Any]):
        name = item["name"]
        selected = item.get("selected", False)
        indexed = item.get("indexed", False)

        if selected and not indexed:
            logger.info(f"Indexing PDF: {name}")
            docs = process_pdf(item["bytes"], name)
            chunks = split_documents(docs)
            self.manager.add_documents(chunks)
            item["indexed"] = True
        elif not selected and indexed:
            logger.info(f"Removing PDF from index: {name}")
            self.manager.remove_document(name)
            item["indexed"] = False

    def _handle_excel_sync(self, item: Dict[str, Any]):
        name = item["name"]
        sheets = item.get("sheets", {})
        
        for sheet_name, info in sheets.items():
            selected = info.get("selected", False)
            indexed = info.get("indexed", False)

            if selected and not indexed:
                logger.info(f"Indexing Excel Sheet: {name} [{sheet_name}]")
                docs = process_excel_sheets(item["bytes"], name, [sheet_name])
                chunks = split_documents(docs)
                self.manager.add_documents(chunks)
                info["indexed"] = True
            elif not selected and indexed:
                logger.info(f"Removing Excel Sheet from index: {name} [{sheet_name}]")
                self.manager.remove_document(name, sheet_name)
                info["indexed"] = False

    def add_pdf(self, name: str, file_bytes: bytes):
        """Manually add a PDF to the vector store."""
        docs = process_pdf(file_bytes, name)
        chunks = split_documents(docs)
        self.manager.add_documents(chunks)

    def add_excel_sheet(self, name: str, file_bytes: bytes, sheet_name: str):
        """Manually add an Excel sheet to the vector store."""
        docs = process_excel_sheets(file_bytes, name, [sheet_name])
        chunks = split_documents(docs)
        self.manager.add_documents(chunks)

    def remove_source(self, name: str, sheet_name: Optional[str] = None):
        """Remove a source (or specific sheet) from the vector store."""
        self.manager.remove_document(name, sheet_name)
