from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()

class VectorStoreManager:
    def __init__(self, model_name="Snowflake/snowflake-arctic-embed-s", persist_directory=None):
        self.model_name = model_name
        self.embeddings = None
        self.vector_store = None
        self.persist_directory = persist_directory

    def load_model(self):
        """Loads the HuggingFace model. This can be used to pre-load or check status."""
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        return self.embeddings

    def initialize_store(self, documents=None):
        """Initializes the vector store. Loads from disk if persist_directory is set."""
        # Ensure model is loaded before indexing
        self.load_model()
            
        self.vector_store = Chroma(
            embedding_function=self.embeddings,
            collection_name="knowledge_base",
            persist_directory=self.persist_directory
        )

        if documents:
            self.vector_store.add_documents(documents)
            
        return self.vector_store

    def add_documents(self, documents):
        """Adds documents to the existing vector store."""
        if self.vector_store is None:
            return self.initialize_store(documents)
        
        self.vector_store.add_documents(documents)
        return self.vector_store

    def remove_document(self, source_name, sheet_name=None):
        """Removes documents matching a specific source filename (and optional sheet name) from the store."""
        if self.vector_store:
            try:
                where_clause = {"source": source_name}
                if sheet_name:
                    where_clause = {
                        "$and": [
                            {"source": source_name},
                            {"sheet": sheet_name}
                        ]
                    }
                
                self.vector_store._collection.delete(where=where_clause)
                return True
            except Exception as e:
                print(f"Error removing {source_name} (sheet: {sheet_name}): {e}")
                return False
        return False

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
