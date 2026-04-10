from .pdf import process_pdf
from .excel import process_excel_sheets, get_excel_sheets
from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_documents(documents, chunk_size=1000, chunk_overlap=200):
    """Splits documents into smaller chunks for vector store."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return text_splitter.split_documents(documents)
