import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import io

def process_pdf(file_bytes, filename):
    """Processes a PDF file and returns LangChain Documents."""
    # We need to write the file temporarily or use a stream if the loader supports it
    # PyPDFLoader usually needs a path, so we'll use a temp file or just extract text directly
    # For simplicity in this env, we use PyPDF from bytes via a temporary file or direct extraction
    # Using pypdf directly for memory-based extraction
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            docs.append(Document(page_content=text, metadata={"source": filename, "page": i+1}))
    return docs

def get_excel_sheets(file_bytes):
    """Returns a list of sheet names from an Excel file."""
    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    return xl.sheet_names

def process_excel_sheets(file_bytes, filename, selected_sheets):
    """Processes specific sheets from an Excel file and returns LangChain Documents."""
    docs = []
    xl = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_sheets)
    
    # If single sheet is selected, xl is a DataFrame, otherwise a dict
    if isinstance(xl, pd.DataFrame):
        xl = {selected_sheets[0]: xl}
        
    for sheet_name, df in xl.items():
        # Convert row to string representation for embedding
        for i, row in df.iterrows():
            content = f"Sheet: {sheet_name}\n" + "\n".join([f"{col}: {val}" for col, val in row.items()])
            docs.append(Document(page_content=content, metadata={"source": filename, "sheet": sheet_name, "row": i}))
    return docs

def excel_to_sqlite(file_bytes, project_name, selected_sheets):
    """Saves specific sheets from an Excel file to SQLite."""
    from .project_manager import ProjectManager
    xl = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_sheets)
    
    if isinstance(xl, pd.DataFrame):
        xl = {selected_sheets[0]: xl}
        
    sanitized_tables = {}
    for sheet_name, df in xl.items():
        actual_table_name = ProjectManager.save_df_to_sql(project_name, sheet_name, df)
        sanitized_tables[sheet_name] = actual_table_name
    return sanitized_tables

def split_documents(documents, chunk_size=1000, chunk_overlap=200):
    """Splits documents into smaller chunks for vector store."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return text_splitter.split_documents(documents)
