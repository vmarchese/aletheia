from abc import abstractmethod


class Knowledge:

    def __init__(self, collection_name: str = "aletheia_common"):
        self.collection_name = collection_name

    def add_document_from_markdown_file(self,
                                        id:str,
                                        file_path: str,
                                        metadata: dict) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return self.add_document(id=id, document=content, metadata=metadata)

    @abstractmethod
    def add_document(self,
                     id:str,
                     document: str,
                     metadata: dict) -> str:
        pass

    @abstractmethod
    def list_documents(self) -> tuple[list, list]:
        pass


    @abstractmethod
    def query(self, question: str) -> str:
        pass

    @abstractmethod
    def delete_document(self, id: str) -> None:
        pass
