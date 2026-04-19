import os
import chromadb
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

class VectorStoreManager:
    def __init__(self, model_name="Snowflake/snowflake-arctic-embed-s", persist_directory=None):
        self.model_name = model_name
        self.embeddings = None
        self.persist_directory = persist_directory
        
        # Initialize a single persistent client
        if persist_directory:
            os.makedirs(persist_directory, exist_ok=True)
            print(f"DEBUG: Vector store initializing at {persist_directory}")
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            print("DEBUG: Vector store initializing in ephemeral mode")
            self.client = chromadb.EphemeralClient()

    def load_model(self):
        """Loads and caches the HuggingFace model."""
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        return self.embeddings

    def _get_collection(self, collection_name: str):
        """Returns a thread-safe Chroma collection instance."""
        self.load_model()
        return Chroma(
            client=self.client,
            collection_name=collection_name,
            embedding_function=self.embeddings
        )

    def add_documents(self, documents, collection_name: str):
        """Adds documents to the specified collection."""
        collection = self._get_collection(collection_name)
        collection.add_documents(documents)

    def remove_document(self, source_name, sheet_name=None, collection_name: str = "knowledge_base"):
        """Removes documents from the specified collection."""
        collection = self._get_collection(collection_name)
        try:
            where_clause = {"source": source_name}
            if sheet_name:
                where_clause = {
                    "$and": [
                        {"source": source_name},
                        {"sheet": sheet_name}
                    ]
                }
            
            # Direct delete via the underlying chromadb collection
            collection._collection.delete(where=where_clause)
            return True
        except Exception as e:
            print(f"Error removing {source_name} (sheet: {sheet_name}) from {collection_name}: {e}")
            return False

    def get_retriever(self, k: int = 5, collection_name: str = "knowledge_base"):
        """Returns a retriever for the specified collection."""
        collection = self._get_collection(collection_name)
        return collection.as_retriever(search_kwargs={"k": k})

    def query(self, text, k: int = 5, collection_name: str = "knowledge_base"):
        """Queries the specified collection."""
        collection = self._get_collection(collection_name)
        return collection.similarity_search(text, k=k)
