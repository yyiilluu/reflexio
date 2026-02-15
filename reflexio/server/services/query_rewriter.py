"""
Query rewriter service that expands user search queries with synonyms
for improved full-text search recall using websearch_to_tsquery syntax.
"""

import logging
from typing import Optional

from reflexio_commons.api_schema.retriever_schema import RewrittenQuery
from reflexio_commons.config_schema import APIKeyConfig
from reflexio.server.llm.litellm_client import LiteLLMClient, LiteLLMConfig
from reflexio.server.prompt.prompt_manager import PromptManager
from reflexio.server.services.service_utils import log_model_response
from reflexio.server.site_var.site_var_manager import SiteVarManager

logger = logging.getLogger(__name__)


class QueryRewriter:
    """Rewrites search queries by expanding them with synonyms via LLM.

    Uses a fast, cheap model (query_rewrite_model_name from llm_model_setting.json)
    with structured output to produce expanded FTS queries in websearch_to_tsquery
    format. Falls back to the original query on any failure.
    """

    def __init__(
        self,
        api_key_config: Optional[APIKeyConfig],
        prompt_manager: PromptManager,
        model: Optional[str] = None,
        timeout: int = 5,
    ):
        """
        Initialize the QueryRewriter.

        Args:
            api_key_config (APIKeyConfig, optional): API key config for the LLM
            prompt_manager (PromptManager): Prompt manager for rendering prompts
            model (str, optional): LLM model override. Defaults to query_rewrite_model_name from llm_model_setting.json
            timeout (int): Request timeout in seconds. Defaults to 5
        """
        self.prompt_manager = prompt_manager
        if model is None:
            model_setting = SiteVarManager().get_site_var("llm_model_setting")
            model = (
                model_setting.get("query_rewrite_model_name", "gpt-5-nano")
                if isinstance(model_setting, dict)
                else "gpt-5-nano"
            )
        llm_config = LiteLLMConfig(
            model=model,
            temperature=0.0,
            max_tokens=256,
            timeout=timeout,
            max_retries=1,
            api_key_config=api_key_config,
        )
        self.llm_client = LiteLLMClient(llm_config)

    def rewrite(self, query: str, enabled: bool = True) -> RewrittenQuery:
        """
        Rewrite a search query with expanded synonyms.

        When disabled or on failure, returns the original query unchanged.

        Args:
            query (str): The original user search query
            enabled (bool): Whether query rewriting is enabled. When False,
                skips LLM call and returns fallback immediately.

        Returns:
            RewrittenQuery: The rewritten query with expanded FTS terms
        """
        if not enabled:
            return self._fallback_rewrite(query)

        try:
            return self._llm_rewrite(query)
        except Exception as e:
            logger.warning("Query rewrite failed, using fallback: %s", e)
            return self._fallback_rewrite(query)

    def _llm_rewrite(self, query: str) -> RewrittenQuery:
        """
        Use LLM to expand the query with synonyms.

        Args:
            query (str): The original search query

        Returns:
            RewrittenQuery: LLM-generated expanded query

        Raises:
            Exception: If LLM call or parsing fails
        """
        prompt = self.prompt_manager.render_prompt("query_rewrite", {"query": query})
        result = self.llm_client.generate_response(
            prompt, response_format=RewrittenQuery
        )
        log_model_response(logger, "Query rewrite response", result)

        if isinstance(result, RewrittenQuery):
            return result

        # If parsing failed, fall back
        logger.warning("LLM returned non-structured response for query rewrite")
        return self._fallback_rewrite(query)

    def _fallback_rewrite(self, query: str) -> RewrittenQuery:
        """
        Return the original query unchanged as a fallback.

        Args:
            query (str): The original search query

        Returns:
            RewrittenQuery: Fallback with original query
        """
        return RewrittenQuery(fts_query=query)
