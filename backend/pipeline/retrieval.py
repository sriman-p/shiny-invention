"""
Hybrid FAISS + BM25 retrieval engine for code search.

This module provides a retriever that combines two complementary search approaches:
  1. FAISS (via sentence-transformers): Dense vector similarity search using
     semantic embeddings. Good at finding conceptually related code even when
     different terminology is used.
  2. BM25 (via rank_bm25): Sparse keyword-based search using term frequency.
     Good at finding exact keyword matches and specific identifiers.

The two scores are combined using a weighted average (alpha controls the
FAISS weight, 1-alpha controls the BM25 weight). This hybrid approach
typically outperforms either method alone.

Usage in the pipeline:
  The Map stage can use this retriever to narrow down candidate code symbols
  before asking the AI agent to make final requirement-to-code mappings.
  By providing a "retrieval shortlist" in the prompt, the agent has a much
  smaller search space, improving both accuracy and speed.

Dependencies (gracefully degraded):
  - sentence-transformers: if not installed, FAISS search is disabled
  - rank_bm25: if not installed, BM25 search is disabled
  If neither is available, the retriever returns empty results.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Hit:
    """
    A single search result from the retriever.

    Attributes:
        text: The matched document content (truncated to 500 chars for display).
        score: Combined relevance score from the hybrid search (higher = more relevant).
        source: Relative file path where this content was found.
        kind: Either "code" (production code) or "tests" (test files), determined
            by whether "test" appears in the file path.
    """

    text: str
    score: float
    source: str
    kind: str = "code"


@dataclass
class Retriever:
    """
    Hybrid FAISS + BM25 retriever for searching project source files.

    Build the index once with build_index(), then call search() to find
    relevant code for a given query. Both search backends are optional --
    the retriever gracefully degrades if dependencies are missing.

    Attributes:
        documents: List of file contents (truncated to 2000 chars each).
        sources: Parallel list of relative file paths.
        kinds: Parallel list of "code" or "tests" tags.
        embeddings: Dense embedding matrix from sentence-transformers (or None).
        bm25: BM25Okapi index object (or None).
        _model: Sentence transformer model instance (or None).
        alpha: Weight for FAISS scores in the hybrid combination (0.0 to 1.0).
            Default 0.6 means FAISS has 60% weight, BM25 has 40%.
    """

    documents: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    embeddings: np.ndarray | None = None
    bm25: object | None = None
    _model: object | None = None
    alpha: float = 0.6

    def build_index(self, code_path: str) -> None:
        """
        Scan a project directory and build both search indices.

        Reads all .py files under code_path, truncates each to 2000 characters
        (to keep embeddings tractable), and builds:
          1. A BM25 index from whitespace-tokenized file contents
          2. Dense embeddings using the all-MiniLM-L6-v2 sentence transformer

        Files are tagged as "tests" if "test" appears anywhere in their path,
        otherwise tagged as "code". This allows filtering search results by kind.

        Args:
            code_path: Absolute or relative path to the project's source code directory.
        """
        path = Path(code_path)
        if not path.exists():
            logger.warning("Code path does not exist: %s", code_path)
            return

        self.documents = []
        self.sources = []
        self.kinds = []

        for py_file in path.rglob("*.py"):
            try:
                content = py_file.read_text(errors="ignore")
                rel_path = str(py_file.relative_to(path))
                # Truncate to 2000 chars to keep embedding computation fast
                self.documents.append(content[:2000])
                self.sources.append(rel_path)
                # Tag files containing "test" in the path as test files
                self.kinds.append("tests" if "test" in rel_path.lower() else "code")
            except Exception as e:
                logger.debug("Failed to read %s: %s", py_file, e)

        if not self.documents:
            return

        # Build BM25 index (sparse keyword search)
        try:
            from rank_bm25 import BM25Okapi

            tokenized = [doc.split() for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized)
        except ImportError:
            logger.warning("rank_bm25 not available; BM25 disabled")

        # Build dense embedding index (semantic vector search)
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            # normalize_embeddings=True enables cosine similarity via dot product
            self.embeddings = self._model.encode(self.documents, normalize_embeddings=True)
        except Exception as e:
            logger.warning("sentence-transformers not available: %s", e)

    def search(
        self,
        query: str,
        k: int = 5,
        filter: Literal["code", "tests", "all"] = "all",
    ) -> list[Hit]:
        """
        Search the index for documents relevant to the query.

        Computes scores from both FAISS (dense) and BM25 (sparse) backends,
        combines them with weighted average, and returns the top-k results.

        Args:
            query: Natural language search query (e.g., a requirement description).
            k: Maximum number of results to return.
            filter: Restrict results to "code" files, "tests" files, or "all".

        Returns:
            List of Hit objects sorted by descending relevance score. Only
            hits with positive scores are returned (zero/negative are filtered out).
        """
        if not self.documents:
            return []

        # Initialize score arrays (one score per document)
        faiss_scores = np.zeros(len(self.documents))
        bm25_scores = np.zeros(len(self.documents))

        # Compute dense similarity scores via dot product (cosine similarity
        # because embeddings are L2-normalized)
        if self.embeddings is not None and self._model is not None:
            try:
                q_emb = self._model.encode([query], normalize_embeddings=True)
                faiss_scores = np.dot(self.embeddings, q_emb.T).flatten()
            except Exception:
                pass

        # Compute BM25 keyword scores, normalized to [0, 1] range
        if self.bm25 is not None:
            try:
                bm25_scores = np.array(self.bm25.get_scores(query.split()))
                bm25_max = bm25_scores.max()
                if bm25_max > 0:
                    bm25_scores = bm25_scores / bm25_max
            except Exception:
                pass

        # Weighted combination: alpha * dense + (1-alpha) * sparse
        combined = self.alpha * faiss_scores + (1 - self.alpha) * bm25_scores

        # Apply kind filter by setting excluded documents' scores to -1
        if filter != "all":
            for i, kind in enumerate(self.kinds):
                if kind != filter:
                    combined[i] = -1

        # Get indices of top-k documents sorted by descending score
        top_indices = np.argsort(combined)[::-1][:k]

        hits = []
        for idx in top_indices:
            # Stop when scores drop to zero or below (no useful results)
            if combined[idx] <= 0:
                break
            hits.append(
                Hit(
                    text=self.documents[idx][:500],  # Truncate for display
                    score=float(combined[idx]),
                    source=self.sources[idx],
                    kind=self.kinds[idx],
                )
            )
        return hits
