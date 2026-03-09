"""
LLM provider abstraction — swap between Anthropic and OpenAI via settings.

Each provider translates tool definitions and handles the
request/response/tool-loop cycle so the view layer stays provider-agnostic.
"""
import json
import logging
import time
from abc import ABC, abstractmethod

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds


def _request_with_retry(client, method, url, **kwargs):
    """HTTP request with retry on 429 (rate limit) and 5xx errors."""
    for attempt in range(MAX_RETRIES + 1):
        resp = client.request(method, url, **kwargs)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAYS[attempt]
                retry_after = resp.headers.get("retry-after")
                if retry_after:
                    try:
                        delay = max(int(retry_after), 1)
                    except ValueError:
                        pass
                logger.warning(
                    "LLM API %s (attempt %d/%d), retrying in %ds...",
                    resp.status_code, attempt + 1, MAX_RETRIES + 1, delay,
                )
                time.sleep(delay)
                continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp


# ── Base ────────────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Common interface every provider must implement."""

    @abstractmethod
    def chat(self, system: str, messages: list[dict], tools: list[dict],
             tool_executor: callable, max_rounds: int = 5) -> dict:
        """
        Run a full conversation turn, including any tool-use loops.

        Returns:
            {"reply": str, "tool_calls": [...], "usage": {...}}
        """


# ── Anthropic ───────────────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    API_URL = "https://api.anthropic.com/v1/messages"

    def _headers(self):
        return {
            "x-api-key": settings.COACH_ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Tools are already in Anthropic format (name, description, input_schema)."""
        return tools

    def chat(self, system, messages, tools, tool_executor, max_rounds=5):
        anthropic_tools = self._convert_tools(tools)
        all_tool_calls = []
        current_messages = list(messages)
        text_parts = []

        logger.info("═══ COACH SESSION START (Anthropic / %s) ═══", settings.COACH_MODEL)
        logger.info("User message: %s", messages[-1]["content"][:200] if messages else "(empty)")

        for round_num in range(max_rounds):
            payload = {
                "model": settings.COACH_MODEL,
                "max_tokens": 4096,
                "system": system,
                "messages": current_messages,
                "tools": anthropic_tools,
            }

            logger.info("── Round %d: Calling Anthropic API...", round_num + 1)
            t0 = time.time()

            with httpx.Client(timeout=60) as client:
                resp = _request_with_retry(
                    client, "POST", self.API_URL,
                    headers=self._headers(), json=payload,
                )
                data = resp.json()

            elapsed = time.time() - t0
            usage = data.get("usage", {})
            logger.info(
                "── Round %d: Anthropic responded in %.1fs (input=%s, output=%s tokens)",
                round_num + 1, elapsed,
                usage.get("input_tokens", "?"),
                usage.get("output_tokens", "?"),
            )

            # Extract text and tool_use blocks
            text_parts = []
            tool_uses = []
            for block in data.get("content", []):
                if block["type"] == "text":
                    text_parts.append(block["text"])
                elif block["type"] == "tool_use":
                    tool_uses.append(block)

            if not tool_uses:
                logger.info("── Round %d: Final answer (no tool calls). Session complete.", round_num + 1)
                logger.info("═══ COACH SESSION END — %d rounds, %d tool calls ═══", round_num + 1, len(all_tool_calls))
                return {
                    "reply": "\n".join(text_parts),
                    "tool_calls": all_tool_calls,
                    "usage": usage,
                }

            # Execute each tool call
            logger.info("── Round %d: AI requested %d tool call(s):", round_num + 1, len(tool_uses))
            assistant_content = data["content"]
            tool_results = []
            for tu in tool_uses:
                logger.info("   → %s(%s)", tu["name"], json.dumps(tu["input"], default=str)[:150])
                all_tool_calls.append({"name": tu["name"], "input": tu["input"]})
                t1 = time.time()
                result = tool_executor(tu["name"], tu["input"])
                logger.info("   ← %s returned in %.1fs (%d bytes)",
                            tu["name"], time.time() - t1, len(json.dumps(result, default=str)))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps(result, default=str),
                })

            current_messages.append({"role": "assistant", "content": assistant_content})
            current_messages.append({"role": "user", "content": tool_results})

        logger.warning("═══ COACH SESSION END — max rounds (%d) exhausted ═══", max_rounds)
        return {
            "reply": "\n".join(text_parts) if text_parts else "I gathered the data but ran out of processing steps. Please try a more specific question.",
            "tool_calls": all_tool_calls,
            "usage": {},
        }


# ── OpenAI ──────────────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    API_URL = "https://api.openai.com/v1/chat/completions"

    def _headers(self):
        return {
            "Authorization": f"Bearer {settings.COACH_OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert from Anthropic format to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    def chat(self, system, messages, tools, tool_executor, max_rounds=5):
        openai_tools = self._convert_tools(tools)
        all_tool_calls = []

        # Build OpenAI message format
        oai_messages = [{"role": "system", "content": system}]
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        logger.info("═══ COACH SESSION START (OpenAI / %s) ═══", settings.COACH_MODEL)
        logger.info("User message: %s", messages[-1]["content"][:200] if messages else "(empty)")

        for round_num in range(max_rounds):
            payload = {
                "model": settings.COACH_MODEL,
                "max_tokens": 4096,
                "messages": oai_messages,
                "tools": openai_tools,
            }

            logger.info("── Round %d: Calling OpenAI API...", round_num + 1)
            t0 = time.time()

            with httpx.Client(timeout=60) as client:
                resp = _request_with_retry(
                    client, "POST", self.API_URL,
                    headers=self._headers(), json=payload,
                )
                data = resp.json()

            elapsed = time.time() - t0
            usage = data.get("usage", {})
            logger.info(
                "── Round %d: OpenAI responded in %.1fs (prompt=%s, completion=%s tokens)",
                round_num + 1, elapsed,
                usage.get("prompt_tokens", "?"),
                usage.get("completion_tokens", "?"),
            )

            choice = data["choices"][0]
            msg = choice["message"]

            if not msg.get("tool_calls"):
                logger.info("── Round %d: Final answer (no tool calls). Session complete.", round_num + 1)
                logger.info("═══ COACH SESSION END — %d rounds, %d tool calls ═══", round_num + 1, len(all_tool_calls))
                return {
                    "reply": msg.get("content", ""),
                    "tool_calls": all_tool_calls,
                    "usage": usage,
                }

            # Execute tool calls
            logger.info("── Round %d: AI requested %d tool call(s):", round_num + 1, len(msg["tool_calls"]))
            oai_messages.append(msg)
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                args = json.loads(fn["arguments"])
                logger.info("   → %s(%s)", fn["name"], fn["arguments"][:150])
                all_tool_calls.append({"name": fn["name"], "input": args})
                t1 = time.time()
                result = tool_executor(fn["name"], args)
                logger.info("   ← %s returned in %.1fs (%d bytes)",
                            fn["name"], time.time() - t1, len(json.dumps(result, default=str)))
                oai_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, default=str),
                })

        logger.warning("═══ COACH SESSION END — max rounds (%d) exhausted ═══", max_rounds)
        return {
            "reply": "I gathered the data but ran out of processing steps. Please try a more specific question.",
            "tool_calls": all_tool_calls,
            "usage": {},
        }


# ── Factory ─────────────────────────────────────────────────────────────────

def get_provider() -> LLMProvider:
    provider = getattr(settings, "COACH_LLM_PROVIDER", "anthropic").lower()
    if provider == "openai":
        return OpenAIProvider()
    return AnthropicProvider()
