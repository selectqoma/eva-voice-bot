"""RAG retriever for fetching relevant context during conversations."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Placeholder retriever (OpenAI embeddings removed)."""

    def __init__(
        self,
        openai_api_key: str,  # kept for signature compatibility
        data_path: Path,
        default_k: int = 3,
    ):
        self.data_path = Path(data_path)
        self.default_k = default_k

    def get_context(self, customer_id: str, query: str, k: int | None = None) -> str:
        return ""

    def get_context_with_scores(
        self,
        customer_id: str,
        query: str,
        k: int | None = None,
        score_threshold: float = 0.0,
    ) -> list[tuple[str, float]]:
        return []

    def clear_cache(self, customer_id: str | None = None) -> None:
        return None

    def has_knowledge_base(self, customer_id: str) -> bool:
        return False

