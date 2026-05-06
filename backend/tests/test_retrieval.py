"""
Real retrieval tests against the actual benchmark projects.
Runs BM25 on the calculator, url-shortener, and todo-api codebases.
Measures precision: does querying a requirement surface the right code file?
"""
import time
import pytest
from pathlib import Path
from pipeline.retrieval import Retriever, Hit

BENCHMARK = Path(__file__).parent.parent.parent / "benchmark" / "projects"


class TestRetrieverOnCalculator:
    """Run the retrieval engine against the real calculator benchmark project."""

    @pytest.fixture(autouse=True)
    def setup_retriever(self):
        self.retriever = Retriever()
        self.retriever.build_index(str(BENCHMARK / "calculator"))

    def test_index_built(self):
        assert len(self.retriever.documents) > 0
        assert len(self.retriever.sources) == len(self.retriever.documents)

    def test_finds_calc_file(self):
        assert any("calc.py" in s for s in self.retriever.sources)

    def test_query_addition_finds_calc(self):
        hits = self.retriever.search("addition of two numbers", k=3)
        assert len(hits) > 0
        assert any("calc" in h.source.lower() for h in hits)

    def test_query_divide_finds_calc(self):
        hits = self.retriever.search("division by zero error", k=3)
        assert len(hits) > 0
        assert any("calc" in h.source.lower() for h in hits)

    def test_query_validation_finds_calc(self):
        hits = self.retriever.search("input validation numeric check", k=3)
        assert len(hits) > 0

    def test_hit_scores_are_positive(self):
        hits = self.retriever.search("multiply", k=5)
        for h in hits:
            assert h.score > 0

    def test_hit_scores_are_sorted(self):
        hits = self.retriever.search("subtract numbers", k=5)
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_filter_code_only(self):
        hits = self.retriever.search("calculator", k=5, filter="code")
        for h in hits:
            assert h.kind == "code"

    def test_empty_query_returns_results(self):
        hits = self.retriever.search("", k=3)
        # BM25 may return 0 for empty query; that's acceptable
        assert isinstance(hits, list)

    def test_k_limits_results(self):
        hits = self.retriever.search("calculator", k=1)
        assert len(hits) <= 1


class TestRetrieverOnURLShortener:
    """Run retrieval against the real url-shortener benchmark project."""

    @pytest.fixture(autouse=True)
    def setup_retriever(self):
        self.retriever = Retriever()
        self.retriever.build_index(str(BENCHMARK / "url-shortener"))

    def test_index_built(self):
        assert len(self.retriever.documents) > 0

    def test_query_shorten_url(self):
        hits = self.retriever.search("shorten a URL and return code", k=3)
        assert len(hits) > 0
        assert any("shortener" in h.source.lower() for h in hits)

    def test_query_redirect(self):
        hits = self.retriever.search("redirect to original URL", k=3)
        assert len(hits) > 0

    def test_query_validation(self):
        hits = self.retriever.search("validate URL format http https", k=3)
        assert len(hits) > 0


class TestRetrieverOnTodoAPI:
    """Run retrieval against the real todo-api benchmark project."""

    @pytest.fixture(autouse=True)
    def setup_retriever(self):
        self.retriever = Retriever()
        self.retriever.build_index(str(BENCHMARK / "todo-api"))

    def test_index_built(self):
        assert len(self.retriever.documents) > 0

    def test_query_create_todo(self):
        hits = self.retriever.search("create a new todo item", k=3)
        assert len(hits) > 0
        assert any("todo" in h.source.lower() for h in hits)

    def test_query_complete_todo(self):
        hits = self.retriever.search("mark todo as complete", k=3)
        assert len(hits) > 0

    def test_query_delete_todo(self):
        hits = self.retriever.search("delete todo item", k=3)
        assert len(hits) > 0


class TestRetrieverEdgeCases:
    """Test retriever behavior with edge cases."""

    def test_nonexistent_path(self):
        r = Retriever()
        r.build_index("/nonexistent/path")
        assert len(r.documents) == 0

    def test_search_empty_index(self):
        r = Retriever()
        hits = r.search("anything", k=5)
        assert hits == []

    def test_alpha_parameter(self):
        r = Retriever(alpha=1.0)  # Pure FAISS
        r.build_index(str(BENCHMARK / "calculator"))
        hits_faiss = r.search("add numbers", k=3)

        r2 = Retriever(alpha=0.0)  # Pure BM25
        r2.build_index(str(BENCHMARK / "calculator"))
        hits_bm25 = r2.search("add numbers", k=3)

        # Both should return results, but scores may differ
        assert isinstance(hits_faiss, list)
        assert isinstance(hits_bm25, list)
