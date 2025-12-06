"""Document ingestion pipeline for customer knowledge bases."""

import logging
from pathlib import Path

from langchain_community.document_loaders import (
    CSVLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
)
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class DocumentIngester:
    """Ingests documents and creates vector stores for customers."""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv", ".docx", ".doc", ".md"}

    def __init__(
        self,
        openai_api_key: str,
        data_path: Path,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        """
        Initialize the document ingester.

        Args:
            openai_api_key: OpenAI API key for embeddings
            data_path: Base path for storing customer vector stores
            chunk_size: Size of text chunks (smaller = more concise voice responses)
            chunk_overlap: Overlap between chunks to maintain context
        """
        self.embeddings = OpenAIEmbeddings(api_key=openai_api_key)
        self.data_path = Path(data_path)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _get_loader(self, file_path: Path):
        """Get the appropriate loader for a file type."""
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return PyPDFLoader(str(file_path))
        elif suffix == ".txt" or suffix == ".md":
            return TextLoader(str(file_path))
        elif suffix == ".csv":
            return CSVLoader(str(file_path))
        elif suffix in (".docx", ".doc"):
            return UnstructuredWordDocumentLoader(str(file_path))
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _get_customer_store_path(self, customer_id: str) -> Path:
        """Get the path to a customer's vector store."""
        return self.data_path / customer_id

    async def ingest_file(self, customer_id: str, file_path: Path) -> int:
        """
        Ingest a single file into a customer's knowledge base.

        Args:
            customer_id: Unique customer identifier
            file_path: Path to the file to ingest

        Returns:
            Number of chunks created
        """
        return await self.ingest_files(customer_id, [file_path])

    async def ingest_files(self, customer_id: str, file_paths: list[Path]) -> int:
        """
        Ingest multiple files into a customer's knowledge base.

        Args:
            customer_id: Unique customer identifier
            file_paths: List of file paths to ingest

        Returns:
            Total number of chunks created
        """
        all_documents: list[Document] = []

        for file_path in file_paths:
            file_path = Path(file_path)

            if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                logger.warning(f"Skipping unsupported file: {file_path}")
                continue

            try:
                loader = self._get_loader(file_path)
                documents = loader.load()

                # Add metadata
                for doc in documents:
                    doc.metadata["source_file"] = file_path.name
                    doc.metadata["customer_id"] = customer_id

                all_documents.extend(documents)
                logger.info(f"Loaded {len(documents)} documents from {file_path}")

            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                continue

        if not all_documents:
            logger.warning("No documents to ingest")
            return 0

        # Split documents into chunks
        chunks = self.splitter.split_documents(all_documents)
        logger.info(f"Split into {len(chunks)} chunks")

        # Create or update vector store
        store_path = self._get_customer_store_path(customer_id)

        if store_path.exists():
            # Load existing store and add new documents
            vector_store = FAISS.load_local(
                str(store_path),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
            vector_store.add_documents(chunks)
        else:
            # Create new vector store
            vector_store = FAISS.from_documents(chunks, self.embeddings)

        # Save the vector store
        store_path.parent.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(store_path))

        logger.info(f"Saved vector store for customer {customer_id}")
        return len(chunks)

    async def ingest_text(self, customer_id: str, text: str, source_name: str = "manual") -> int:
        """
        Ingest raw text into a customer's knowledge base.

        Args:
            customer_id: Unique customer identifier
            text: Raw text content to ingest
            source_name: Name to use for the source metadata

        Returns:
            Number of chunks created
        """
        document = Document(
            page_content=text,
            metadata={"source_file": source_name, "customer_id": customer_id},
        )

        chunks = self.splitter.split_documents([document])

        store_path = self._get_customer_store_path(customer_id)

        if store_path.exists():
            vector_store = FAISS.load_local(
                str(store_path),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
            vector_store.add_documents(chunks)
        else:
            vector_store = FAISS.from_documents(chunks, self.embeddings)

        store_path.parent.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(store_path))

        return len(chunks)

    def has_knowledge_base(self, customer_id: str) -> bool:
        """Check if a customer has an existing knowledge base."""
        return self._get_customer_store_path(customer_id).exists()

    def delete_knowledge_base(self, customer_id: str) -> bool:
        """Delete a customer's knowledge base."""
        store_path = self._get_customer_store_path(customer_id)
        if store_path.exists():
            import shutil

            shutil.rmtree(store_path)
            return True
        return False

