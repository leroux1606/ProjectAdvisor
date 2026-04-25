"""
Tests for the OpenRouter client. HTTP is mocked — no network calls.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.llm import openrouter


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Each test starts with no provider configured."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_APP_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_APP_NAME", raising=False)


def _ok_response(content: str = "hello", model: str = "anthropic/claude-haiku-4-5"):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "model": model,
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }
    return response


def test_llm_available_false_without_keys():
    assert openrouter.llm_available() is False


def test_llm_available_true_with_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert openrouter.llm_available() is True


def test_llm_available_true_with_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert openrouter.llm_available() is True


def test_call_chat_routes_to_openrouter_when_configured(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENROUTER_APP_URL", "http://localhost:3000")
    monkeypatch.setenv("OPENROUTER_APP_NAME", "Test App")

    with patch("app.llm.openrouter.requests.post", return_value=_ok_response()) as mock_post:
        result = openrouter.call_chat([{"role": "user", "content": "hi"}])

    assert result.text == "hello"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8

    args, kwargs = mock_post.call_args
    assert args[0] == "https://openrouter.ai/api/v1/chat/completions"
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-or-test"
    assert headers["HTTP-Referer"] == "http://localhost:3000"
    assert headers["X-Title"] == "Test App"


def test_call_chat_falls_back_to_openai_when_only_openai_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    with patch(
        "app.llm.openrouter.requests.post",
        return_value=_ok_response(model="gpt-4o"),
    ) as mock_post:
        openrouter.call_chat([{"role": "user", "content": "hi"}])

    assert mock_post.call_args[0][0] == "https://api.openai.com/v1/chat/completions"


def test_call_chat_raises_when_no_provider():
    with pytest.raises(openrouter.LLMNotConfigured):
        openrouter.call_chat([{"role": "user", "content": "hi"}])


def test_call_chat_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    err_response = MagicMock()
    err_response.status_code = 429
    err_response.text = '{"error":{"message":"Rate limited"}}'
    err_response.json.return_value = {"error": {"message": "Rate limited"}}

    with patch("app.llm.openrouter.requests.post", return_value=err_response):
        with pytest.raises(openrouter.LLMError, match="Rate limited"):
            openrouter.call_chat([{"role": "user", "content": "hi"}])


def test_call_json_parses_clean_json(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    with patch(
        "app.llm.openrouter.requests.post",
        return_value=_ok_response(content='{"answer": 42}'),
    ):
        data, result = openrouter.call_json("system", "user")

    assert data == {"answer": 42}
    assert result.total_tokens == 20


def test_call_json_extracts_object_from_prose(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    payload = 'Sure! Here is the result:\n{"answer": "hello"}\nLet me know if you need more.'

    with patch(
        "app.llm.openrouter.requests.post",
        return_value=_ok_response(content=payload),
    ):
        data, _ = openrouter.call_json("system", "user")

    assert data == {"answer": "hello"}


def test_call_json_raises_when_no_json_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    with patch(
        "app.llm.openrouter.requests.post",
        return_value=_ok_response(content="No JSON here at all"),
    ):
        with pytest.raises(openrouter.LLMError, match="did not return JSON"):
            openrouter.call_json("system", "user")


def test_default_model_is_haiku(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    with patch(
        "app.llm.openrouter.requests.post",
        return_value=_ok_response(),
    ) as mock_post:
        openrouter.call_chat([{"role": "user", "content": "hi"}])

    payload = mock_post.call_args.kwargs["json"]
    assert payload["model"] == "anthropic/claude-haiku-4-5"


def test_explicit_model_override(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-6")

    with patch(
        "app.llm.openrouter.requests.post",
        return_value=_ok_response(),
    ) as mock_post:
        openrouter.call_chat(
            [{"role": "user", "content": "hi"}],
            model="meta-llama/llama-3.1-70b-instruct",
        )

    assert mock_post.call_args.kwargs["json"]["model"] == "meta-llama/llama-3.1-70b-instruct"
