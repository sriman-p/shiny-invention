import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Hit:
    text: str
    score: float
    source: str
    kind: str = "code"


@dataclass
class Retriever:
    documents: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    embeddings: np.ndarray | None = None
    bm25: object | None = None
    _model: object | None = None
    alpha: float = 0.6

    def build_index(self, code_path: str) -> None:
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
                self.documents.append(content[:2000])
                self.sources.append(rel_path)
                self.kinds.append("tests" if "test" in rel_path.lower() else "code")
            except Exception as e:
                logger.debug("Failed to read %s: %s", py_file, e)

        if not self.documents:
            return

        try:
            from rank_bm25 import BM25Okapi

            tokenized = [doc.split() for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized)
        except ImportError:
            logger.warning("rank_bm25 not available; BM25 disabled")

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            self.embeddings = self._model.encode(self.documents, normalize_embeddings=True)
        except Exception as e:
            logger.warning("sentence-transformers not available: %s", e)

    def search(
        self,
        query: str,
        k: int = 5,
        filter: Literal["code", "tests", "all"] = "all",
    ) -> list[Hit]:
        if not self.documents:
            return []

        faiss_scores = np.zeros(len(self.documents))
        bm25_scores = np.zeros(len(self.documents))

        if self.embeddings is not None and self._model is not None:
            try:
                q_emb = self._model.encode([query], normalize_embeddings=True)
                faiss_scores = np.dot(self.embeddings, q_emb.T).flatten()
            except Exception:
                pass

        if self.bm25 is not None:
            try:
                bm25_scores = np.array(self.bm25.get_scores(query.split()))
                bm25_max = bm25_scores.max()
                if bm25_max > 0:
                    bm25_scores = bm25_scores / bm25_max
            except Exception:
                pass

        combined = self.alpha * faiss_scores + (1 - self.alpha) * bm25_scores

        if filter != "all":
            for i, kind in enumerate(self.kinds):
                if kind != filter:
                    combined[i] = -1

        top_indices = np.argsort(combined)[::-1][:k]

        hits = []
        for idx in top_indices:
            if combined[idx] <= 0:
                break
            hits.append(
                Hit(
                    text=self.documents[idx][:500],
                    score=float(combined[idx]),
                    source=self.sources[idx],
                    kind=self.kinds[idx],
                )
            )
        return hits
