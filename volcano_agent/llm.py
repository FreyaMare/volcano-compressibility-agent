"""Minimal agent loop on the Claude API.

The model gets server-side web tools (search + fetch, executed by Anthropic) and one
client tool, `submit`, whose JSON schema is the structured answer we want. The loop
ends when the model calls `submit`; its input is returned.
"""
from __future__ import annotations

import json
import time
from typing import Callable, List, Optional

import anthropic

DEFAULT_MODEL = "claude-opus-5-5"

WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search"}
WEB_FETCH = {"type": "web_fetch_20250910", "name": "web_fetch"}


class AgentError(RuntimeError):
    pass


def web_tools(max_search: int, max_fetch: int, fetch_tokens: int = 25000) -> list:
    tools = []
    if max_search:
        tools.append({**WEB_SEARCH, "max_uses": max_search})
    if max_fetch:
        tools.append({**WEB_FETCH, "max_uses": max_fetch, "max_content_tokens": fetch_tokens})
    return tools


class Usage:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.searches = 0
        self.fetches = 0
        self.calls = 0

    def add(self, msg):
        u = msg.usage
        self.calls += 1
        self.input_tokens += (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) \
            + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        self.output_tokens += u.output_tokens or 0
        stu = getattr(u, "server_tool_use", None)
        if stu is not None:
            self.searches += getattr(stu, "web_search_requests", 0) or 0
            self.fetches += getattr(stu, "web_fetch_requests", 0) or 0

    def summary(self) -> str:
        return (f"{self.calls} model calls, {self.input_tokens:,} input / {self.output_tokens:,} output tokens, "
                f"{self.searches} web searches, {self.fetches} page fetches")


def run_submit_loop(client: anthropic.Anthropic, *, model: str, system: str, user,
                    submit_name: str, submit_description: str, submit_schema: dict,
                    server_tools: Optional[list] = None, max_tokens: int = 32000,
                    max_rounds: int = 24, on_event: Callable[[str], None] | None = None,
                    usage: Usage | None = None, sources: Optional[List[dict]] = None,
                    force_submit: bool = False) -> dict:
    """Run the model until it calls `submit_name`; return the tool input (a dict).

    `user` is a string or a list of content blocks. With `force_submit` the model must call
    the submit tool immediately (used when no research is needed, e.g. for the writer).
    Prompt caching is automatic (top-level cache_control): every round re-sends the growing
    conversation, and cached tokens are billed at a fraction of the input price."""
    say = on_event or (lambda s: None)
    tools = list(server_tools or []) + [{
        "name": submit_name, "description": submit_description, "input_schema": submit_schema}]
    messages: list = [{"role": "user", "content": user}]
    extra = {"tool_choice": {"type": "tool", "name": submit_name}} if force_submit else {}
    nudges = 0
    for _ in range(max_rounds):
        msg = _create(client, model=model, system=system, tools=tools, messages=messages,
                      max_tokens=max_tokens, cache_control={"type": "ephemeral"}, **extra)
        if usage is not None:
            usage.add(msg)
        submitted = None
        for block in msg.content:
            t = getattr(block, "type", "")
            if t == "server_tool_use":
                inp = getattr(block, "input", {}) or {}
                if block.name == "web_search":
                    say(f"search: {inp.get('query', '')}")
                elif block.name == "web_fetch":
                    say(f"read: {inp.get('url', '')}")
            elif t == "web_search_tool_result" and sources is not None:
                content = getattr(block, "content", None)
                if isinstance(content, list):
                    for r in content:
                        url = getattr(r, "url", None)
                        if url:
                            sources.append(dict(url=url, title=getattr(r, "title", "") or ""))
            elif t == "tool_use" and block.name == submit_name:
                submitted = block.input
        messages.append({"role": "assistant", "content": msg.content})
        client_calls = [b for b in msg.content if getattr(b, "type", "") == "tool_use"]
        if submitted is not None and msg.stop_reason != "max_tokens":
            if isinstance(submitted, str):
                submitted = json.loads(submitted)
            if isinstance(submitted, dict) and submitted:
                return submitted
        if submitted is not None or msg.stop_reason == "max_tokens":
            # the submission was cut off (or empty): ask for a complete, more concise one
            say("submission incomplete; asking the model to resubmit")
            reply = [{"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                      "content": "Your submission was incomplete or cut off. Call the tool again with the "
                                 "complete data; keep the narratives shorter."} for b in client_calls]
            if not reply:
                reply = [{"type": "text", "text": f"Your answer was cut off. Call `{submit_name}` now with "
                                                  "the complete data and shorter narratives."}]
            messages.append({"role": "user", "content": reply})
            continue
        if msg.stop_reason == "pause_turn":
            continue                                   # long server-tool turn: resume as is
        if client_calls:                               # unexpected client tool; answer and go on
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "content": "Unknown tool.", "is_error": True}
                for b in client_calls]})
            continue
        nudges += 1
        if nudges > 3:
            break
        messages.append({"role": "user", "content":
                         f"Stop researching now and call the `{submit_name}` tool with everything you have "
                         f"found. Use null values (status \"D\") for anything you could not find."})
    raise AgentError(f"The model did not call {submit_name}.")


def make_client(api_key: Optional[str] = None) -> anthropic.Anthropic:
    """Client with generous built-in retries (the SDK honours the retry-after header)."""
    kw = {"max_retries": 4, "timeout": 900.0}
    return anthropic.Anthropic(api_key=api_key, **kw) if api_key else anthropic.Anthropic(**kw)


def _create(client, **kw):
    """Streaming request (needed for long outputs) with an extra retry layer for overload,
    rate limits and dropped connections, on top of the SDK's own retries."""
    delay = 10.0
    for attempt in range(4):
        try:
            with client.messages.stream(**kw) as stream:
                return stream.get_final_message()
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError,
                anthropic.APIStatusError) as e:
            status = getattr(e, "status_code", None)
            retryable = isinstance(e, (anthropic.RateLimitError, anthropic.InternalServerError,
                                       anthropic.APIConnectionError)) or status in (408, 409, 429, 500, 502, 503, 504, 529)
            if not retryable or attempt == 3:
                raise
            wait = delay
            try:
                wait = max(wait, float(e.response.headers.get("retry-after", 0)))
            except Exception:
                pass
            time.sleep(min(wait, 120.0))
            delay *= 2
