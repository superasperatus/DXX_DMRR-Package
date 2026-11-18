"""Validate provider settings and normalize a single API attempt."""

import os
import re
from urllib.parse import parse_qs, urlparse

import requests

from .config import MODELS, SYSTEM_PROMPT, parameters_for
from .prompts import parse_response


def validate_live_configuration(models: list[str]) -> None:
    # Refuse live execution until endpoints and environment-variable keys exist.
    for model in models:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
            raise ValueError("Use simple model IDs without path separators")
        config = MODELS[model]
        url = urlparse(config["endpoint"])
        if url.scheme != "https" or not url.netloc or url.username or url.password:
            raise ValueError(f"{model}: add your own HTTPS endpoint in 01_collection/config.py before --execute")
        if {key.lower() for key in parse_qs(url.query)} & {"key", "api_key", "api-key", "token"}:
            raise ValueError(f"{model}: credentials belong in environment variables, not the URL")
        if config["auth"] not in ("api-key", "bearer"):
            raise ValueError(f"{model}: auth must be 'api-key' or 'bearer'")
        if not os.environ.get(config["key_env"], "").strip():
            raise ValueError(f"{model}: set the {config['key_env']} environment variable")


def http_failure(response: requests.Response) -> tuple[dict, str]:
    # A generic HTTP 400 is a configuration error, not automatically a filter.
    code = ""
    try:
        body = response.json()
    except ValueError:
        body = {}
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        code = str(body["error"].get("code", ""))
    if response.status_code == 400 and code.lower() in ("content_filter", "responsibleaipolicyviolation"):
        return {"error": "Provider content filter"}, "blocked"
    status = "retry" if response.status_code in (408, 429, 500, 502, 503, 504) else "fatal"
    return {"error": f"HTTP {response.status_code}"}, status


def read_completion(body: dict) -> dict:
    # Keep provider metadata when present; missing usage is blank, not zero.
    first = body["choices"][0]
    content = first["message"]["content"]
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise TypeError("The provider returned non-text content")
    usage = body.get("usage") or {}
    return {
        "raw_response": content, "parsed_response": parse_response(content),
        "prompt_tokens": usage.get("prompt_tokens", ""),
        "completion_tokens": usage.get("completion_tokens", ""),
        "provider_model": body.get("model", ""),
        "provider_response_id": body.get("id", ""),
        "system_fingerprint": body.get("system_fingerprint") or "",
        "finish_reason": first.get("finish_reason", ""),
    }


def request_once(session: requests.Session, model: str, prompt: str, temperature: float) -> tuple[dict, str]:
    # Perform one attempt; the collection loop decides whether a retry is allowed.
    config = MODELS[model]
    key = os.environ[config["key_env"]].strip()
    headers = {"api-key": key} if config["auth"] == "api-key" else {"Authorization": f"Bearer {key}"}
    payload = parameters_for(model, temperature)
    payload["messages"] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    try:
        response = session.post(config["endpoint"], headers=headers, json=payload, timeout=90)
    except (requests.Timeout, requests.ConnectionError) as exc:
        return {"error": type(exc).__name__}, "retry"
    if not response.ok:
        return http_failure(response)
    try:
        result = read_completion(response.json())
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        return {"error": f"Malformed provider response: {type(exc).__name__}"}, "retry"
    if result["finish_reason"] == "content_filter":
        return {**result, "parsed_response": "INVALID", "error": "Provider content filter"}, "blocked"
    if result["parsed_response"] == "INVALID":
        return {**result, "error": "Unparseable model response"}, "retry"
    return {**result, "error": ""}, "valid"
