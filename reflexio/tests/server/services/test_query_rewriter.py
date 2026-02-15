"""Unit tests for the QueryRewriter service.

Tests the critical paths: feature-flag bypass, LLM failure fallback,
and successful rewrite propagation.
"""

import unittest
from unittest.mock import MagicMock, patch

from reflexio_commons.api_schema.retriever_schema import RewrittenQuery
from reflexio.server.services.query_rewriter import QueryRewriter


def _make_rewriter(**overrides):
    """Create a QueryRewriter with mocked dependencies."""
    api_key_config = MagicMock()
    prompt_manager = MagicMock()
    prompt_manager.render_prompt.return_value = "rendered prompt"

    with patch("reflexio.server.services.query_rewriter.LiteLLMClient"), patch(
        "reflexio.server.services.query_rewriter.SiteVarManager"
    ) as mock_svm:
        mock_svm.return_value.get_site_var.return_value = {
            "query_rewrite_model_name": "gpt-5-nano"
        }
        rewriter = QueryRewriter(
            api_key_config=api_key_config,
            prompt_manager=prompt_manager,
            **overrides,
        )
    return rewriter


class TestQueryRewriter(unittest.TestCase):
    """Unit tests for QueryRewriter."""

    def test_rewrite_disabled_returns_original_query(self):
        """When enabled=False, should skip LLM and return original query."""
        rewriter = _make_rewriter()
        result = rewriter.rewrite("agent failed to refund", enabled=False)

        self.assertIsInstance(result, RewrittenQuery)
        self.assertEqual(result.fts_query, "agent failed to refund")
        # LLM should NOT have been called
        rewriter.llm_client.generate_response.assert_not_called()

    def test_rewrite_llm_failure_returns_fallback(self):
        """When LLM raises an exception, should gracefully fall back to original query."""
        rewriter = _make_rewriter()
        rewriter.llm_client.generate_response.side_effect = RuntimeError("API timeout")

        result = rewriter.rewrite("slow response time", enabled=True)

        self.assertIsInstance(result, RewrittenQuery)
        self.assertEqual(result.fts_query, "slow response time")

    def test_rewrite_success_returns_expanded_query(self):
        """When LLM succeeds, should return the expanded query."""
        rewriter = _make_rewriter()
        expanded = RewrittenQuery(
            fts_query="agent failed OR error to refund OR return OR reimburse"
        )
        rewriter.llm_client.generate_response.return_value = expanded

        result = rewriter.rewrite("agent failed to refund", enabled=True)

        self.assertIsInstance(result, RewrittenQuery)
        self.assertEqual(
            result.fts_query,
            "agent failed OR error to refund OR return OR reimburse",
        )

    def test_rewrite_non_structured_response_returns_fallback(self):
        """When LLM returns a non-RewrittenQuery object, should fall back."""
        rewriter = _make_rewriter()
        rewriter.llm_client.generate_response.return_value = "plain string"

        result = rewriter.rewrite("test query", enabled=True)

        self.assertIsInstance(result, RewrittenQuery)
        self.assertEqual(result.fts_query, "test query")


if __name__ == "__main__":
    unittest.main()
