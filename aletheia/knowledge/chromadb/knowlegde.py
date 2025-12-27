import chromadb
from aletheia.knowledge import Knowledge

class ChromaKnowledge(Knowledge):
    def __init__(self,
                 persist_directory: str = "./.chroma",
                 collection_name: str = "aletheia_common",
                 n_results: int = 5):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.n_results = n_results  
        super().__init__(collection_name=collection_name)

    def add_document(self, id: str, document: str, metadata: dict):
        return self.collection.add(ids=[id], documents=[document], metadatas=[metadata])

    def delete_document(self, id: str) -> None:
        self.collection.delete(ids=[id])

    def query(self, question: str) -> str:
        results = self.collection.query(query_texts=[question], n_results=self.n_results)
        response = ""
        if results['documents']:
            for doc in results['documents']:
                if doc:
                    response += doc[0] + "\n"

        return response

    def list_documents(self) -> tuple[list, list]:
        results = self.collection.get()
        return results['ids'],results['documents']

    