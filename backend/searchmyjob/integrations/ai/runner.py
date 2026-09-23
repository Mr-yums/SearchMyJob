"""Provider API execution with the application's bounded tools."""

import asyncio
import json

from searchmyjob.domain.context import native_session
from searchmyjob.integrations.ai.provider import run


async def run_agent(provider, prompt, timeout=240):
    return await asyncio.wait_for(run(provider, prompt, native_session.get()), timeout)


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Réponse structurée absente ; aucun changement appliqué.")
    return json.loads(text[start : end + 1])
