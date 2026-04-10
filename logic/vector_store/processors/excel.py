import pandas as pd
from langchain_core.documents import Document
import io

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
