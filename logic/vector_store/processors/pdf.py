from langchain_core.documents import Document
import io

def process_pdf(file_bytes, filename):
    """Processes a PDF file and returns LangChain Documents."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            docs.append(Document(page_content=text, metadata={"source": filename, "page": i+1}))
    return docs
