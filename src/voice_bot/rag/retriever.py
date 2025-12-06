"""RAG retriever for fetching relevant context during conversations."""

import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Retrieves relevant context from a customer's knowledge base."""

    def __init__(
        self,
        openai_api_key: str,
        data_path: Path,
        default_k: int = 3,
    ):
        """
        Initialize the RAG retriever.

        Args:
            openai_api_key: OpenAI API key for embeddings
            data_path: Base path where customer vector stores are saved
            default_k: Default number of documents to retrieve
        """
        self.embeddings = OpenAIEmbeddings(api_key=openai_api_key)
        self.data_path = Path(data_path)
        self.default_k = default_k
        self._store_cache: dict[str, FAISS] = {}

    def _get_store_path(self, customer_id: str) -> Path:
        """Get the path to a customer's vector store."""
        return self.data_path / customer_id

    def _load_store(self, customer_id: str) -> FAISS | None:
        """Load a customer's vector store (with caching)."""
        if customer_id in self._store_cache:
            return self._store_cache[customer_id]

        store_path = self._get_store_path(customer_id)

        if not store_path.exists():
            logger.warning(f"No vector store found for customer {customer_id}")
            return None

        try:
            store = FAISS.load_local(
                str(store_path),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
            self._store_cache[customer_id] = store
            return store
        except Exception as e:
            logger.error(f"Error loading vector store for {customer_id}: {e}")
            return None

    def get_context(self, customer_id: str, query: str, k: int | None = None) -> str:
        """
        Retrieve relevant context for a query.

        Args:
            customer_id: Customer whose knowledge base to search
            query: The user's question or message
            k: Number of documents to retrieve (uses default if not specified)

        Returns:
            Concatenated relevant context, or empty string if none found
        """
        store = self._load_store(customer_id)

        if store is None:
            return ""

        k = k or self.default_k

        try:
            docs = store.similarity_search(query, k=k)

            if not docs:
                return ""

            # Format context with source attribution
            context_parts = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("source_file", "unknown")
                context_parts.append(f"[{source}]: {doc.page_content}")

            return "\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return ""

    def get_context_with_scores(
        self,
        customer_id: str,
        query: str,
        k: int | None = None,
        score_threshold: float = 0.0,
    ) -> list[tuple[str, float]]:
        """
        Retrieve relevant context with relevance scores.

        Args:
            customer_id: Customer whose knowledge base to search
            query: The user's question or message
            k: Number of documents to retrieve
            score_threshold: Minimum score threshold (0-1, higher = more relevant)

        Returns:
            List of (content, score) tuples
        """
        store = self._load_store(customer_id)

        if store is None:
            return []

        k = k or self.default_k

        try:
            docs_with_scores = store.similarity_search_with_score(query, k=k)

            results = []
            for doc, score in docs_with_scores:
                # FAISS returns L2 distance, lower = more similar
                # Convert to similarity score (this is approximate)
                similarity = 1 / (1 + score)

                if similarity >= score_threshold:
                    source = doc.metadata.get("source_file", "unknown")
                    results.append((f"[{source}]: {doc.page_content}", similarity))

            return results

        except Exception as e:
            logger.error(f"Error retrieving context with scores: {e}")
            return []

    def clear_cache(self, customer_id: str | None = None) -> None:
        """
        Clear the vector store cache.

        Args:
            customer_id: Specific customer to clear, or None to clear all
        """
        if customer_id:
            self._store_cache.pop(customer_id, None)
        else:
            self._store_cache.clear()

    def has_knowledge_base(self, customer_id: str) -> bool:
        """Check if a customer has an existing knowledge base."""
        return self._get_store_path(customer_id).exists()

