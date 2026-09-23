from searchmyjob.config import PROJECT_ROOT

"""[Sol] Bounded France Travail and Bright Data connectors, normalized provenance."""
import asyncio
import hashlib
import json
import os
import signal
from urllib.parse import urlsplit

import httpx

from searchmyjob.infrastructure.bright_budget import budget_path
from searchmyjob.infrastructure.bright_budget import status as bright_usage
from searchmyjob.infrastructure.vault import read
from searchmyjob.integrations.search.results import resolve_results, search_query


class ProviderError(Exception):
    pass


def safe_url(url):
    return url if isinstance(url, str) and urlsplit(url).scheme in ("https", "http") else ""


def offer(
    source,
    key,
    title,
    company="",
    location="",
    description="",
    url="",
    contract="",
    salary="",
    published="",
):
    return dict(
        id=hashlib.sha256((source + str(key)).encode()).hexdigest()[:24],
        source=source,
        title=title,
        company=company,
        location=location,
        description=description,
        url=safe_url(url),
        contract=contract,
        salary=salary,
        published=published,
    )


async def france_travail(criteria, limit=60):
    keys = read()
    if not keys.get("ft_client_id") or not keys.get("ft_client_secret"):
        raise ProviderError("France Travail : identifiants manquants")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire",
            data=dict(
                grant_type="client_credentials",
                client_id=keys["ft_client_id"],
                client_secret=keys["ft_client_secret"],
                scope="api_offresdemploiv2 o2dsoffre",
            ),
        )
        if r.status_code != 200:
            raise ProviderError(f"France Travail : authentification HTTP {r.status_code}")
        token = r.json().get("access_token")
        if not token:
            raise ProviderError("France Travail : jeton absent")
        params = {"motsCles": criteria["keywords"], "range": f"0-{min(limit, 150) - 1}"}
        if criteria.get("department"):
            params["departement"] = criteria["department"]
        if criteria.get("contract"):
            params["typeContrat"] = criteria["contract"]
        r = await c.get(
            "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
            params=params,
            headers={"Authorization": "Bearer " + token},
        )
        if r.status_code == 204:
            return []
        if r.status_code not in (200, 206):
            raise ProviderError(f"France Travail : recherche HTTP {r.status_code}")
        return [
            offer(
                "France Travail",
                x["id"],
                x.get("intitule", ""),
                x.get("entreprise", {}).get("nom", ""),
                x.get("lieuTravail", {}).get("libelle", ""),
                x.get("description", ""),
                x.get("origineOffre", {}).get("urlOrigine")
                or "https://candidat.francetravail.fr/offres/recherche/detail/" + x["id"],
                x.get("typeContrat", ""),
                x.get("salaire", {}).get("libelle", ""),
                x.get("dateCreation", ""),
            )
            for x in r.json().get("resultats", [])
        ]


async def bright(criteria):
    platform = criteria.get("_platform")
    if platform in ("linkedin", "indeed") and criteria.get("objectif", "emploi") == "emploi":
        from searchmyjob.integrations.search.job_platforms import discover

        return await discover(platform, criteria)
    return await bright_web(search_query(criteria), criteria.get("country", "fr"))


async def bright_web(query, geo="fr"):
    """One general web query, through the same guarded MCP and budget."""
    keys = read()
    if not keys.get("bright_key"):
        raise ProviderError("Bright Data : clé manquante")
    if bright_usage()["blocked"]:
        raise ProviderError(
            "Stop-loss Bright Data : appels bloqués (plafond local atteint ou compteur indisponible)"
        )
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/node",
        str(PROJECT_ROOT / "mcp/search.mjs"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        payload = json.dumps(
            dict(token=keys["bright_key"], query=query, budget=str(budget_path()), geo=geo)
        ).encode()
        stdout, _ = await asyncio.wait_for(proc.communicate(payload), timeout=110)
        data = json.loads(stdout)
        if proc.returncode or data.get("error"):
            raise ProviderError(data.get("error", "Bright Data : échec MCP"))
        return await normalize_bright_results(data)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()


async def normalize_bright_results(data):
    items = data.get("organic") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ProviderError(
            "Bright Data : format de résultats invalide, aucune conclusion sur les offres disponibles"
        )
    resolved = await resolve_results(items)
    if items and not resolved:
        raise ProviderError(
            f"Bright Data : {len(items)} résultats reçus mais liens inexploitables ; ce n’est pas une recherche sans résultat"
        )
    result = []
    for x in resolved:
        row = offer(
            "Bright Data",
            x["link"],
            x["title"],
            description=x.get("description", ""),
            url=x["link"],
            contract="À vérifier",
        )
        row["google_redirect"] = x["google_redirect"]
        row["result_kind"] = "web_lead"
        result.append(row)
    return result


async def bright_status():
    if not read().get("bright_key"):
        raise ProviderError("Bright Data : clé manquante")
    usage = bright_usage()
    if usage["blocked"]:
        raise ProviderError("Stop-loss Bright Data : appels bloqués")
    return {
        "status": f"MCP configuré · {usage['used']}/{usage['limit']} requêtes · clé non testée par ce contrôle local"
    }


async def bright_page(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or "." not in host
        or ":" in host
        or not any(c.isalpha() for c in host)
        or host.endswith((".local", ".localhost", ".internal", ".test", ".invalid"))
    ):
        raise ProviderError("La source doit être une page HTTPS publique.")
    keys = read()
    if not keys.get("bright_key"):
        raise ProviderError("Bright Data : clé manquante")
    if bright_usage()["blocked"]:
        raise ProviderError("Stop-loss Bright Data : appels bloqués")
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/node",
        str(PROJECT_ROOT / "mcp/page.mjs"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        payload = json.dumps(
            dict(token=keys["bright_key"], url=url, budget=str(budget_path()))
        ).encode()
        stdout, _ = await asyncio.wait_for(proc.communicate(payload), timeout=110)
        data = json.loads(stdout)
        if proc.returncode or data.get("error"):
            raise ProviderError(
                "Page inaccessible via Bright Data. Aucun nouvel essai automatique."
            )
        text = data.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 1000000:
            raise ProviderError("Contenu de page absent ou trop volumineux")
        return text
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
