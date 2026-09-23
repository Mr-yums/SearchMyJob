"""API adapters: no host CLI, personal account, or arbitrary endpoint required."""

import asyncio
import json
import time
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from searchmyjob.domain.usage import AgentExecutionError, AgentResult
from searchmyjob.infrastructure import vault

Provider = Literal["deepseek", "kimi", "claude", "openai"]
PROVIDERS = {
    "deepseek": {"label": "DeepSeek", "url": "https://api.deepseek.com/v1"},
    "kimi": {"label": "Kimi", "url": "https://api.moonshot.ai/v1"},
    "claude": {"label": "Claude", "url": "https://api.anthropic.com/v1"},
    "openai": {"label": "OpenAI", "url": "https://api.openai.com/v1"},
}


class Configuration(BaseModel):
    provider: Provider
    key: str = Field("", max_length=1000)
    model: str = Field("", max_length=160, pattern=r"^[a-zA-Z0-9._:/-]*$")


def saved(provider):
    return vault.read().get("ai_" + provider, {})


def status():
    return {
        name: {
            "label": spec["label"],
            "configured": bool((c := saved(name)).get("tested_at")),
            "model": c.get("model", ""),
            "tested_at": c.get("tested_at"),
        }
        for name, spec in PROVIDERS.items()
    }


def headers(provider, key):
    if provider == "claude":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return {"Authorization": "Bearer " + key}


async def request(client, provider, key, path, payload=None):
    try:
        r = await client.request(
            "GET" if payload is None else "POST",
            PROVIDERS[provider]["url"] + path,
            headers=headers(provider, key),
            json=payload,
        )
    except httpx.HTTPError:
        raise AgentExecutionError(
            "Fournisseur IA inaccessible ou délai dépassé. Aucun nouvel essai automatique."
        ) from None
    if r.status_code >= 400:
        label = {
            401: "Clé API refusée",
            403: "Accès refusé",
            404: "Modèle ou service introuvable",
            429: "Quota épuisé ou limite de débit atteinte",
            400: "Modèle ou paramètres incompatibles",
        }
        raise AgentExecutionError(
            label.get(r.status_code, "Erreur du fournisseur") + f" (HTTP {r.status_code})."
        )
    try:
        return r.json()
    except ValueError:
        raise AgentExecutionError("Réponse du fournisseur illisible.") from None


def key_for(body):
    key = body.key.strip() or saved(body.provider).get("key", "")
    if not key or any(c.isspace() for c in key):
        raise ValueError("Renseigne une clé API valide pour ce fournisseur.")
    return key


def compatible(provider, name):
    if provider == "openai":
        return name.startswith(("gpt-", "o1", "o3", "o4")) and not any(
            x in name
            for x in (
                "audio",
                "realtime",
                "transcribe",
                "tts",
                "image",
                "search",
                "codex",
                "deep-research",
            )
        )
    return name.startswith(
        {"deepseek": ("deepseek-",), "kimi": ("kimi-", "moonshot-"), "claude": ("claude-",)}[
            provider
        ]
    )


async def models(body):
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        result = await request(client, body.provider, key_for(body), "/models")
    return sorted(
        {
            m["id"]
            for m in result.get("data", [])
            if isinstance(m.get("id"), str) and compatible(body.provider, m["id"])
        }
    )


async def completion(client, provider, key, model, messages, tools, probe=False):
    payload = {"model": model, "messages": messages}
    if provider == "claude":
        payload["max_tokens"] = 128 if probe else 8192
        if tools:
            payload["tools"] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["inputSchema"],
                }
                for t in tools
            ]
            if probe:
                payload["tool_choice"] = {"type": "tool", "name": "connection_check"}
        data = await request(client, provider, key, "/messages", payload)
        content = data.get("content", [])
        calls = [
            {"id": b["id"], "name": b["name"], "arguments": b["input"]}
            for b in content
            if b.get("type") == "tool_use"
        ]
        text = "\n".join(b["text"] for b in content if b.get("type") == "text")
        message = {"role": "assistant", "content": content}
        usage = data.get("usage", {})
        measured = (
            {
                "input_tokens": usage.get("input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cached_input_tokens": usage.get("cache_read_input_tokens", 0),
            }
            if usage
            else None
        )
    else:
        payload["max_completion_tokens" if provider == "openai" else "max_tokens"] = (
            512 if probe else 8192
        )
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["inputSchema"],
                    },
                }
                for t in tools
            ]
        # Disable reasoning for the deliberately small connection probe where supported.
        if probe and provider in ("kimi", "deepseek"):
            if model.startswith(("kimi-k2.5", "kimi-k2.6", "deepseek-")):
                payload["thinking"] = {"type": "disabled"}
        if probe:
            payload["tool_choice"] = {"type": "function", "function": {"name": "connection_check"}}
        data = await request(client, provider, key, "/chat/completions", payload)
        try:
            message = data["choices"][0]["message"]
        except KeyError, IndexError, TypeError:
            raise AgentExecutionError("Réponse du modèle absente.") from None
        # Keep reasoning_content for providers requiring it on subsequent tool turns.
        message = {
            k: v
            for k, v in message.items()
            if k in ("role", "content", "tool_calls", "reasoning_content")
        }
        calls = []
        for call in message.get("tool_calls", []):
            try:
                args = json.loads(call["function"]["arguments"])
            except ValueError, KeyError:
                raise AgentExecutionError("Arguments d’outil illisibles.") from None
            calls.append({"id": call["id"], "name": call["function"]["name"], "arguments": args})
        text = message.get("content") or ""
        usage = data.get("usage", {})
        measured = (
            {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "cached_input_tokens": usage.get("prompt_tokens_details", {}).get(
                    "cached_tokens", usage.get("prompt_cache_hit_tokens", 0)
                ),
            }
            if usage
            else None
        )
    return text, calls, message, measured


async def test_and_save(body):
    if not body.model or not compatible(body.provider, body.model):
        raise ValueError("Choisis un modèle conversationnel compatible.")
    key = key_for(body)
    tool = {
        "name": "connection_check",
        "description": "Valider la connexion, sans action externe.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    }
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        _, calls, _, usage = await completion(
            client,
            body.provider,
            key,
            body.model,
            [{"role": "user", "content": "Appelle connection_check une fois, avec un objet vide."}],
            [tool],
            probe=True,
        )
    if len(calls) != 1 or calls[0]["name"] != "connection_check" or calls[0]["arguments"] != {}:
        raise ValueError(
            "Ce modèle n’a pas validé l’appel d’outil requis. Choisis un autre modèle."
        )
    vault.save({"ai_" + body.provider: {"key": key, "model": body.model, "tested_at": time.time()}})
    return usage


async def run(provider, prompt, session=None):
    config = saved(provider)
    if not config.get("tested_at"):
        raise AgentExecutionError(
            "Configure et teste ce fournisseur dans Connexions avant de continuer."
        )
    total = {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}
    measured = True
    try:
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            catalog = session["catalog"] if session else []
            messages = [{"role": "user", "content": prompt}]
            for _ in range(12):
                text, calls, message, usage = await completion(
                    client, provider, config["key"], config["model"], messages, catalog
                )
                measured = measured and usage is not None
                for k in total:
                    total[k] += (usage or {}).get(k, 0)
                if not calls:
                    if not text.strip():
                        raise AgentExecutionError("Le modèle a renvoyé une réponse vide.")
                    return AgentResult(text, config["model"], total if measured else None)
                messages.append(message)
                blocks = []
                for call in calls:
                    if not session or call["name"] not in {t["name"] for t in catalog}:
                        raise AgentExecutionError("Le modèle a demandé un outil non autorisé.")
                    try:
                        value = await session["call"](call["name"], call["arguments"])
                        content = json.dumps(value, ensure_ascii=False)
                    except Exception:
                        content = json.dumps(
                            {
                                "error": "Outil indisponible ou arguments invalides. Ne pas réessayer automatiquement."
                            }
                        )
                    if provider == "claude":
                        blocks.append(
                            {"type": "tool_result", "tool_use_id": call["id"], "content": content}
                        )
                    else:
                        messages.append(
                            {"role": "tool", "tool_call_id": call["id"], "content": content}
                        )
                if blocks:
                    messages.append({"role": "user", "content": blocks})
            raise AgentExecutionError("Limite de 12 échanges IA atteinte pour cette réponse.")
    except BaseException as exc:
        if isinstance(exc, (AgentExecutionError, asyncio.CancelledError)):
            exc.usage = total if measured else None
        raise
