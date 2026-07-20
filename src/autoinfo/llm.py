"""LLM extraction pipeline — structured information extraction from collected items.

Uses LiteLLM to call configured models (default: deepseek/deepseek-chat via OpenRouter)
and extract structured fields (TL;DR, key points, entities, relevance score) from
raw article content. All LLM calls go through :func:`litellm.completion`.

Typical usage::

    from autoinfo.llm import LLMExtractor
    from autoinfo.models import Item

    extractor = LLMExtractor()
    item = Item(id="1", source_name="pubmed", title="...", content="...", collected_at="...")
    result = extractor.extract(item)
    print(result.tl_dr)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

from autoinfo.config import Config, get_config_path, load_config
from autoinfo.models import ExtractionResult, Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PROVIDER = "openrouter"
DEFAULT_MODEL = "deepseek/deepseek-chat"

SYSTEM_PROMPT = (
    "You are AutoInfo, an information extraction assistant. "
    "Extract structured information from the following article. "
    "Respond with valid JSON only, no markdown formatting."
)

FIELD_DESCRIPTIONS: dict[str, str] = {
    "tl_dr": '"tl_dr": "2-3 sentence summary of the article"',
    "key_points": '"key_points": ["3-5 most important findings or takeaways"]',
    "entities": (
        '"entities": [{"name": "Entity name", "type": "person|org|concept|technology|procedure|outcome"}]'
    ),
    "relevance_score": '"relevance_score": integer 0-100 indicating relevance to medical research',
}

# Fields always included when no custom schema is provided.
DEFAULT_SCHEMA: list[str] = ["tl_dr", "key_points", "entities", "relevance_score"]

# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class LLMExtractor:
    """Extract structured fields from a collected :class:`Item` using an LLM.

    Parameters
    ----------
    config : Config, optional
        Application configuration.  If omitted the extractor tries to load the
        config from the default paths (``.autoinfo/config.yaml`` or
        ``~/.autoinfo/config.yaml``).  When neither exists an empty config is
        used and the provider/model fall back to their defaults.
    """

    def __init__(self, config: Optional[Config] = None) -> None:
        if config is None:
            config_path = get_config_path()
            if config_path is not None:
                config = load_config(config_path)
            else:
                config = Config()

        self._config = config

        provider = config.llm.provider or DEFAULT_PROVIDER
        model = config.llm.model or DEFAULT_MODEL
        self._model = f"{provider}/{model}"

        # If the config carries an API key, let the environment variable take
        # it — LiteLLM reads OPENROUTER_API_KEY automatically for OpenRouter
        # calls, OPENAI_API_KEY for OpenAI calls, etc.
        if config.llm.api_key:
            env_key = f"{provider.upper()}_API_KEY"
            os.environ.setdefault(env_key, config.llm.api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        item: Item,
        schema: Optional[list[str]] = None,
    ) -> ExtractionResult:
        """Extract structured fields from *item*.

        Returns an :class:`ExtractionResult` with the parsed fields.  If the
        LLM call or JSON parsing fails the result contains empty/default values
        (no exception is raised).
        """
        try:
            return self._call_llm(item, schema)
        except Exception as exc:
            logger.error("LLM extraction failed for item %s: %s", item.id, exc)
            return ExtractionResult(item_id=item.id, title=item.title)

    def dry_run(
        self,
        item: Item,
        schema: Optional[list[str]] = None,
    ) -> str:
        """Return the full prompt that *would* be sent to the LLM.

        No API call is made — useful for debugging and prompt iteration.
        """
        system, user = self._build_prompt(item, schema)
        return f"System:\n{system}\n\nUser:\n{user}"

    def extract_with_retry(
        self,
        item: Item,
        max_retries: int = 2,
        schema: Optional[list[str]] = None,
    ) -> ExtractionResult:
        """Extract with retry logic.

        On failure the method logs a warning, waits 1 second, and retries.
        If all attempts fail a :class:`RuntimeError` is raised.

        Raises
        ------
        RuntimeError
            When extraction fails after *max_retries* + 1 attempts.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                return self._call_llm(item, schema)
            except Exception as exc:
                last_exception = exc
                logger.warning(
                    "LLM extraction attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(1)

        raise RuntimeError(
            f"LLM extraction failed after {max_retries + 1} attempts"
        ) from last_exception

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        item: Item,
        schema: Optional[list[str]] = None,
    ) -> tuple[str, str]:
        """Build (system_prompt, user_prompt) for the given *item*.

        If *schema* is provided it controls which fields the LLM is asked to
        extract; otherwise the default set (TL;DR, key points, entities,
        relevance score) is used.
        """
        if schema is None:
            schema = DEFAULT_SCHEMA

        lines = [SYSTEM_PROMPT, "", "Extract the following fields:"]
        for field in schema:
            desc = FIELD_DESCRIPTIONS.get(field, f'"{field}": <value>')
            lines.append(f"  - {desc}")

        system = "\n".join(lines)
        user = (
            f"Title: {item.title}\n\n"
            f"Content: {item.content}\n\n"
            "Extract structured information from this article."
        )
        return system, user

    @staticmethod
    def _get_litellm() -> Any:
        """Lazily import and return the ``litellm`` module.

        Returns ``None`` when the package is not available (graceful
        degradation for environments where LiteLLM is not installed).
        """
        try:
            import litellm  # noqa: PLC0415 — deferred import

            return litellm
        except (ImportError, ModuleNotFoundError):
            logger.error("litellm is not installed — run 'pip install litellm'")
            return None

    def _call_llm(
        self,
        item: Item,
        schema: Optional[list[str]] = None,
    ) -> ExtractionResult:
        """Execute the LLM completion and parse the result.

        Raises on network error, API error, or empty response.  The caller
        (``extract`` / ``extract_with_retry``) decides how to handle failures.
        """
        _litellm = self._get_litellm()
        if _litellm is None:
            raise RuntimeError("litellm is not available")

        system, user_prompt = self._build_prompt(item, schema)

        response = _litellm.completion(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.1,
        )

        content: str = response.choices[0].message.content  # type: ignore[union-attr]
        parsed = self._parse_response(content)

        return ExtractionResult(
            item_id=item.id,
            title=item.title,
            tl_dr=parsed.get("tl_dr", ""),
            key_points=parsed.get("key_points", []),
            entities=parsed.get("entities", []),
            relevance_score=max(
                0.0, min(100.0, float(parsed.get("relevance_score", 0)))
            ),
        )

    @staticmethod
    def _parse_response(content: str) -> dict[str, Any]:
        """Parse the LLM response as JSON with several fallback strategies.

        1. Direct :func:`json.loads`.
        2. Extract JSON from markdown code blocks (```json ... ```).
        3. Find the first ``{…}`` brace-delimited block.

        Returns an empty dict when all strategies fail.
        """
        # Strategy 1 — direct JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Strategy 2 — markdown fenced code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3 — bare JSON object anywhere in the text
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse LLM response as JSON: %.200s", content)
        return {}
