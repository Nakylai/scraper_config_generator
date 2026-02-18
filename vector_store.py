import json
import logging

import chromadb
from sentence_transformers import SentenceTransformer

from mini_scraper.config_generator.schemas import LLMFeatures, SimilarConfig

logger = logging.getLogger(__name__)

COLLECTION_NAME = "website_configs"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class ConfigVectorStore:
    """ChromaDB wrapper for storing and retrieving website configs by feature similarity."""

    def __init__(self, persist_dir: str):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_config(
        self,
        config_id: str,
        llm_features: LLMFeatures,
        config_metadata: dict,
        pagination_html: str = "",
    ):
        """Add a config to the vector store.

        Args:
            config_id: Unique identifier for the config.
            llm_features: Extracted features from the config.
            config_metadata: Full config dict to store as metadata for retrieval.
            pagination_html: Extracted pagination HTML snippet for similarity search.
        """
        features_text = llm_features.to_text()
        embedding = self.embedder.encode(features_text).tolist()

        # ChromaDB metadata values must be str, int, float, or bool
        metadata = {
            "source_name": config_metadata.get("source_name", ""),
            "features_text": features_text,
            "full_config": json.dumps(config_metadata, ensure_ascii=False),
            "pagination_html": pagination_html[:2000] if pagination_html else "",
        }

        self.collection.upsert(
            ids=[config_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[features_text],
        )
        logger.info("Added config %s (%s) to vector store", config_id, metadata["source_name"])

    def find_similar(self, llm_features: LLMFeatures, k: int = 3) -> list[SimilarConfig]:
        """Find the k most similar configs to the given features.

        Args:
            llm_features: Features to search for.
            k: Number of similar configs to return.

        Returns:
            List of SimilarConfig results ordered by similarity.
        """
        features_text = llm_features.to_text()
        embedding = self.embedder.encode(features_text).tolist()

        count = self.get_count()
        if count == 0:
            return []

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(k, count),
        )

        return self._parse_query_results(results)

    def find_similar_pagination(self, pagination_html: str, k: int = 3) -> list[SimilarConfig]:
        """Find configs with similar pagination HTML.

        Args:
            pagination_html: Pagination HTML snippet to search for.
            k: Number of similar configs to return.

        Returns:
            List of SimilarConfig results ordered by similarity.
        """
        if not pagination_html:
            return []

        embedding = self.embedder.encode(pagination_html).tolist()
        count = self.get_count()
        if count == 0:
            return []

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(k, count),
        )

        return self._parse_query_results(results)

    def _parse_query_results(self, results) -> list[SimilarConfig]:
        """Convert raw ChromaDB query results into a list of SimilarConfig."""
        similar_configs = []
        if results and results["ids"] and results["ids"][0]:
            for i, config_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0

                full_config = {}
                if metadata.get("full_config"):
                    try:
                        full_config = json.loads(metadata["full_config"])
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse full_config for %s", config_id)

                similar_configs.append(
                    SimilarConfig(
                        config_id=config_id,
                        source_name=metadata.get("source_name", ""),
                        distance=distance,
                        full_config=full_config,
                        features_text=metadata.get("features_text", ""),
                        pagination_html=metadata.get("pagination_html", ""),
                    )
                )

        return similar_configs

    def get_count(self) -> int:
        """Return the number of configs in the store."""
        return self.collection.count()

    def has_config(self, config_id: str) -> bool:
        """Check if a config with the given ID exists."""
        result = self.collection.get(ids=[config_id])
        return bool(result and result["ids"])

    def reset(self):
        """Delete the collection and recreate it."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store reset")
