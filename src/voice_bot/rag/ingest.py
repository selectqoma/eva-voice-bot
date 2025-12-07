"""Document ingestion placeholder (OpenAI embeddings removed)."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentIngester:
    """No-op ingester retained for compatibility."""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv", ".docx", ".doc", ".md"}

    def __init__(
        self,
        openai_api_key: str,  # kept for signature compatibility
        data_path: Path,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.data_path = Path(data_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _get_customer_store_path(self, customer_id: str) -> Path:
        return self.data_path / customer_id

    async def ingest_file(self, customer_id: str, file_path: Path) -> int:
        logger.warning("RAG ingestion disabled (OpenAI removed).")
        return 0

    async def ingest_files(self, customer_id: str, file_paths: list[Path]) -> int:
        logger.warning("RAG ingestion disabled (OpenAI removed).")
        return 0

    async def ingest_text(self, customer_id: str, text: str, source_name: str = "manual") -> int:
        logger.warning("RAG ingestion disabled (OpenAI removed).")
        return 0

    def has_knowledge_base(self, customer_id: str) -> bool:
        return False

    def delete_knowledge_base(self, customer_id: str) -> bool:
        return False

