import asyncio
import json

import httpx
import pytest
from searchmyjob.domain.usage import AgentExecutionError
from searchmyjob.infrastructure import vault
from searchmyjob.integrations.ai import provider as ai
from searchmyjob.integrations.ai import runner as ai_runner
from searchmyjob.integrations.search import providers as source_providers
from support.agents import REAL_RUN_AGENT
from support.polling import wait

REAL_VAULT_READ = vault.read


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(vault, "read", lambda: dict(data))
    monkeypatch.setattr(vault, "save", lambda values: data.update(values))
    return data


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        ai.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )


def tool_reply(provider, name="connection_check", args=None):
    if provider == "claude":
        return {
            "content": [{"type": "tool_use", "id": "call-1", "name": name, "input": args or {}}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 2},
        }
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "reasoning",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args or {})},
                        }
                    ],
                }
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 2},
        },
    }


MODELS = {
    "deepseek": "deepseek-chat",
    "kimi": "kimi-k2.5",
    "claude": "claude-sonnet-test",
    "openai": "gpt-test",
}


@pytest.mark.parametrize("provider", MODELS)
def test_probe_headers_tools_and_private_status(provider, monkeypatch, store):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.host in (
            "api.openai.com",
            "api.anthropic.com",
            "api.deepseek.com",
            "api.moonshot.ai",
        )
        body = json.loads(request.content)
        assert body["model"] == MODELS[provider]
        assert body["tools"]
        if provider == "claude":
            assert request.headers["x-api-key"] == "private-test-key"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert body["tool_choice"] == {"type": "tool", "name": "connection_check"}
        else:
            assert request.headers["authorization"] == "Bearer private-test-key"
            assert body["tool_choice"]["function"]["name"] == "connection_check"
        return httpx.Response(200, json=tool_reply(provider))

    transport(monkeypatch, handler)
    usage = asyncio.run(
        ai.test_and_save(
            ai.Configuration(provider=provider, key="private-test-key", model=MODELS[provider])
        )
    )
    assert len(seen) == 1 and usage["output_tokens"] == 5
    assert store["ai_" + provider]["key"] == "private-test-key"
    assert ai.status()[provider]["configured"]
    assert "private-test-key" not in json.dumps(ai.status())


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429, 500])
def test_error_redacted_and_previous_config_preserved(code, monkeypatch, store):
    store["ai_openai"] = {"key": "old-key", "model": "gpt-old", "tested_at": 1}
    transport(monkeypatch, lambda request: httpx.Response(code, json={"error": "secret-new-key"}))
    with pytest.raises(AgentExecutionError) as error:
        asyncio.run(
            ai.test_and_save(
                ai.Configuration(provider="openai", key="secret-new-key", model="gpt-test")
            )
        )
    assert "secret-new-key" not in str(error.value)
    assert store["ai_openai"]["key"] == "old-key"


@pytest.mark.parametrize("provider", MODELS)
def test_full_tool_roundtrip_and_usage(provider, monkeypatch, store):
    store["ai_" + provider] = {"key": "test-key", "model": MODELS[provider], "tested_at": 1}
    requests = []
    calls = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(200, json=tool_reply(provider, "get_profile"))
        last = body["messages"][-1]
        if provider == "claude":
            assert last["content"][0]["tool_use_id"] == "call-1"
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "Réponse finale"}],
                    "usage": {"input_tokens": 20, "output_tokens": 8},
                },
            )
        assert last["role"] == "tool" and last["tool_call_id"] == "call-1"
        assert body["messages"][-2]["reasoning_content"] == "reasoning"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "Réponse finale"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        )

    async def call(name, args):
        calls.append((name, args))
        return {"profile": "Profil de test"}

    transport(monkeypatch, handler)
    result = asyncio.run(
        ai.run(
            provider,
            "Demande",
            {
                "catalog": [
                    {
                        "name": "get_profile",
                        "description": "Lire",
                        "inputSchema": {"type": "object", "properties": {}},
                    }
                ],
                "call": call,
            },
        )
    )
    assert result.answer == "Réponse finale"
    assert result.usage == {"input_tokens": 32, "output_tokens": 13, "cached_input_tokens": 2}
    assert calls == [("get_profile", {})]


def test_model_listing_filters_non_chat(monkeypatch, store):
    transport(
        monkeypatch,
        lambda req: httpx.Response(
            200, json={"data": [{"id": "gpt-test"}, {"id": "gpt-image-1"}, {"id": "whisper-1"}]}
        ),
    )
    assert asyncio.run(ai.models(ai.Configuration(provider="openai", key="test-key"))) == [
        "gpt-test"
    ]


def test_no_run_without_verified_credentials(store):
    with pytest.raises(AgentExecutionError):
        asyncio.run(ai.run("openai", "Hello"))


def test_activation_requires_verified_provider(client, store):
    assert (
        client.post("/api/activation", json={"provider": "openai", "country": "de"}).status_code
        == 422
    )
    store["ai_openai"] = {"key": "test-key", "model": "gpt-test", "tested_at": 1}
    store["bright_key"] = "test-bright-key"
    assert (
        client.post("/api/activation", json={"provider": "openai", "country": "de"}).status_code
        == 200
    )
    assert client.get("/api/state").json()["settings"]["enabled"] is False


def test_ai_endpoints_never_return_key(client, monkeypatch, store):
    transport(monkeypatch, lambda req: httpx.Response(200, json=tool_reply("openai")))
    r = client.post(
        "/api/ai/test", json={"provider": "openai", "key": "private-test-key", "model": "gpt-test"}
    )
    assert r.status_code == 200
    assert "private-test-key" not in client.get("/api/ai").text
    assert "private-test-key" not in client.get("/api/state").text
    assert (
        client.post(
            "/api/ai/test", headers={"X-Workspace-Token": "bad"}, json={"provider": "openai"}
        ).status_code
        == 403
    )


def test_vault_permissions_atomic_update_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCHMYJOB_STATE", str(tmp_path))
    vault.save({"first": "one", "second": "two"})
    vault.save({"first": "updated", "second": None})
    assert REAL_VAULT_READ() == {"first": "updated"}
    assert (tmp_path / "credentials.sqlite3").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("provider", MODELS)
def test_chat_api_tools_store_draft_and_keep_final_reply(client, monkeypatch, store, provider):
    store["ai_" + provider] = {"key": "test-key", "model": MODELS[provider], "tested_at": 1}

    monkeypatch.setattr(ai_runner, "run_agent", REAL_RUN_AGENT)
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) == 1:
            return httpx.Response(200, json=tool_reply(provider, "get_profile"))
        if len(seen) == 2:
            return httpx.Response(
                200,
                json=tool_reply(
                    provider,
                    "draft_email",
                    {
                        "to": "contact@example.com",
                        "subject": "Présentation",
                        "body": "Brouillon simulé à relire.",
                    },
                ),
            )
        text = json.dumps({"reply": "Brouillon préparé, aucun envoi.", "action": "none"})
        if provider == "claude":
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": text}],
                    "usage": {"input_tokens": 5, "output_tokens": 4},
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 4},
            },
        )

    transport(monkeypatch, handler)
    assert (
        client.post(
            "/api/chat",
            json={
                "text": "Prépare un brouillon de présentation à contact@example.com",
                "provider": provider,
            },
        ).status_code
        == 200
    )
    assert wait(client)["status"] == "completed"
    data = client.get("/api/state").json()
    assert data["messages"][-1]["text"] == "Brouillon préparé, aucun envoi."
    assert len(data["emails"]) == 1 and data["emails"][0]["status"] == "draft"
    assert len(data["tool_calls"]) == 2 and len(seen) == 3
    assert not client.app.state.engine.agent_tools.sessions


def test_validation_does_not_echo_submitted_secret(client):
    secret = "private-secret-" * 100
    response = client.post(
        "/api/ai/test", json={"provider": "openai", "key": secret, "model": "gpt-test"}
    )
    assert response.status_code == 422 and "private-secret" not in response.text


def test_sources_separate_from_ai_and_no_secret_echo(client, store):
    response = client.post("/api/connections", json={"bright_key": "private-source-key"})
    assert response.status_code == 200
    assert store["bright_key"] == "private-source-key"
    assert client.get("/api/ai").json()["openai"]["configured"] is False
    result = client.get("/api/connections")
    assert result.json()["bright"] is True and "private-source-key" not in result.text
    assert client.get("/api/state").json()["runs"] == []


def test_source_connection_test_calls_only_selected_source(client, monkeypatch):
    seen = []

    async def bright(*args):
        seen.append("bright")
        return []

    async def ft(*args):
        seen.append("france")
        return []

    monkeypatch.setattr(source_providers, "bright", bright)
    monkeypatch.setattr(source_providers, "france_travail", ft)
    assert (
        client.post(
            "/api/connections/bright/test",
            json={"country": "de", "keywords": "Pflege", "platforms": ["indeed"]},
        ).status_code
        == 200
    )
    assert seen == ["bright"]
    assert client.post("/api/connections/france/test").status_code == 200
    assert seen == ["bright", "france"]
    assert client.post("/api/connections/other/test").status_code == 422
