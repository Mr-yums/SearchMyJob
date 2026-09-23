from searchmyjob.api.app import create_app
from searchmyjob.integrations.search import providers as source_providers

"""Local UI test server; providers replaced with deterministic, offline responses."""
import json
import os

if not os.environ.get("SEARCHMYJOB_STATE") or os.environ.get("SEARCHMYJOB_STATE") == "/state":
    raise SystemExit("Choisir un dossier de test séparé avec SEARCHMYJOB_STATE.")
if not os.environ.get("SEARCHMYJOB_PORT"):
    raise SystemExit("Choisir un port de test avec SEARCHMYJOB_PORT.")

from searchmyjob.integrations.ai import provider as ai_provider


async def request(client, provider, key, path, payload=None):
    if key == "bad-key":
        raise ai_provider.AgentExecutionError("Clé API refusée (HTTP 401).")
    if path == "/models":
        return {
            "data": [
                {
                    "id": {
                        "openai": "gpt-fixture",
                        "kimi": "kimi-fixture",
                        "claude": "claude-fixture",
                        "deepseek": "deepseek-fixture",
                    }[provider]
                }
            ]
        }
    if payload.get("tool_choice"):
        if provider == "claude":
            return {
                "content": [
                    {"type": "tool_use", "id": "check", "name": "connection_check", "input": {}}
                ]
            }
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "check",
                                "type": "function",
                                "function": {"name": "connection_check", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        }
    content = json.dumps({"reply": "Réponse de test : ton espace fonctionne.", "action": "none"})
    if provider == "claude":
        return {"content": [{"type": "text", "text": content}]}
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


ai_provider.request = request


async def source(*args, **kwargs):
    return []


source_providers.france_travail = source
source_providers.bright_web = source
source_providers.bright = source
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        create_app(), host="127.0.0.1", port=int(os.environ["SEARCHMYJOB_PORT"]), access_log=False
    )
