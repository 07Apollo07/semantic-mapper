from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()

class VectorStoreManager:
    def __init__(self, model_name="sentence-transformers/all-mpnet-base-v2"):
        self.model_name = model_name
        self.embeddings = None
        self.vector_store = None

    def load_model(self):
        """Loads the HuggingFace model. This can be used to pre-load or check status."""
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        return self.embeddings

    def initialize_store(self, documents):
        """Initializes an in-memory Chroma vector store with documents."""
        if not documents:
            return None
        
        # Ensure model is loaded before indexing
        self.load_model()
            
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            collection_name="knowledge_base"
        )
        return self.vector_store

    def get_retriever(self, k=5):
        """Returns a retriever for the vector store."""
        if self.vector_store is None:
            raise ValueError("Vector store not initialized.")
        return self.vector_store.as_retriever(search_kwargs={"k": k})

    def query(self, text, k=5):
        """Directly queries the vector store."""
        if self.vector_store is None:
            raise ValueError("Vector store not initialized.")
        return self.vector_store.similarity_search(text, k=k)
