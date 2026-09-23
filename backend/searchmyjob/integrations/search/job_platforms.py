"""Bounded public job discovery through Bright Data's platform scrapers.

Contract references and verification limits: docs/search-sources.md.
"""

import asyncio
import hashlib
import re
import time
from html import unescape
from urllib.parse import urlsplit

import httpx

from searchmyjob.domain.countries import COUNTRIES, country_code
from searchmyjob.infrastructure import bright_budget
from searchmyjob.infrastructure.vault import read

DATASETS = {"linkedin": "gd_lpfll7v5hcqtkxl6l", "indeed": "gd_l4dx9j9sscpvs7no2"}
API = "https://api.brightdata.com/datasets/v3"


def discovery_input(platform, criteria):
    country = country_code(criteria.get("country", "fr"))
    location = criteria.get("location", "").strip() or COUNTRIES[country]
    keyword = criteria["keywords"].strip()
    if not keyword:
        raise ValueError("Renseigne un métier avant de rechercher.")
    if platform == "linkedin":
        return {
            "keyword": keyword,
            "location": location,
            "country": country.upper(),
            **({"remote": "Remote"} if criteria.get("remote") else {}),
            **({"job_type": "Contract"} if criteria.get("freelance") else {}),
        }
    if platform == "indeed":
        domain = (
            "www.indeed.com"
            if country == "us"
            else ("uk" if country == "gb" else country) + ".indeed.com"
        )
        return {
            "keyword_search": keyword,
            "location": location,
            "country": country.upper(),
            "domain": domain,
        }
    raise ValueError("Plateforme inconnue")


def plain(value):
    if isinstance(value, list):
        return ", ".join(plain(x) for x in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {plain(v)}" for k, v in value.items())
    return unescape(re.sub(r"<[^>]*>", " ", str(value or ""))).strip()[:60000]


def normalize(platform, rows, criteria):
    from searchmyjob.integrations.search.providers import ProviderError, offer

    if not isinstance(rows, list):
        raise ProviderError(f"Bright Data · {platform} : réponse invalide")
    result = []
    for row in rows:
        if not isinstance(row, dict) or row.get("error") or row.get("error_code"):
            raise ProviderError(
                f"Bright Data · {platform} : collecte incomplète ou refusée ; aucun nouvel essai automatique"
            )
        url = row.get("url") or row.get("job_url") or ""
        if not isinstance(url, str):
            continue
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        title = plain(row.get("job_title") or row.get("title"))
        if (
            parsed.scheme != "https"
            or not (host == platform + ".com" or host.endswith("." + platform + ".com"))
            or not title
        ):
            continue
        description = plain(
            row.get("job_summary") or row.get("description_text") or row.get("description")
        )
        result.append(
            {
                **offer(
                    "Bright Data",
                    url,
                    title,
                    company=plain(row.get("company_name")),
                    location=plain(row.get("job_location") or row.get("location")),
                    description=description,
                    url=url,
                    contract=plain(row.get("job_employment_type") or row.get("job_type")),
                    salary=plain(row.get("salary") or row.get("base_salary")),
                    published=plain(
                        row.get("date_posted_parsed")
                        or row.get("job_posted_date")
                        or row.get("date_posted")
                    ),
                ),
                "collection_method": "brightdata_scraper",
                "platform": platform,
                "requested_country": criteria.get("country", "fr"),
                "collected_at": time.time(),
                "result_kind": "individual",
            }
        )
    if rows and not result:
        raise ProviderError(
            f"Bright Data · {platform} : annonces inexploitables, pas une recherche vide"
        )
    return result[:20]


async def discover(platform, criteria):
    from searchmyjob.integrations.search.providers import ProviderError

    key = read().get("bright_key")
    if not key:
        raise ProviderError("Bright Data : clé manquante")
    params = {
        "dataset_id": DATASETS[platform],
        "type": "discover_new",
        "discover_by": "keyword",
        "limit_per_input": 20,
        "include_errors": "true",
    }
    payload = discovery_input(platform, criteria)
    # Resume a pending collection instead of triggering (and paying for) it again.
    fingerprint = hashlib.sha256(
        (
            platform + repr(sorted(payload.items())) + hashlib.sha256(key.encode()).hexdigest()
        ).encode()
    ).hexdigest()
    snapshot = None
    try:
        snapshot = bright_budget.pending(fingerprint)
        async with httpx.AsyncClient(
            timeout=45, follow_redirects=False, headers={"Authorization": "Bearer " + key}
        ) as client:
            if not snapshot:
                bright_budget.reserve("jobs:" + platform)
                response = await client.post(API + "/trigger", params=params, json=[payload])
                if response.status_code not in (200, 201, 202):
                    raise ProviderError(
                        f"Bright Data · {platform} : HTTP {response.status_code}. Vérifie la clé, l’accès au scraper et le quota."
                    )
                snapshot = response.json().get("snapshot_id")
                if not isinstance(snapshot, str) or not re.fullmatch(r"sd_[\w-]{1,120}", snapshot):
                    raise ProviderError(
                        f"Bright Data · {platform} : identifiant de collecte absent"
                    )
                bright_budget.save_pending(fingerprint, snapshot)
            # Each poll reads the same already-triggered snapshot: no paid retry.
            async with asyncio.timeout(150):
                while True:
                    response = await client.get(API + "/progress/" + snapshot)
                    if response.status_code != 200:
                        raise ProviderError(
                            f"Bright Data · {platform} : suivi HTTP {response.status_code} ; collecte {snapshot} conservée"
                        )
                    status = response.json().get("status")
                    if status == "ready":
                        break
                    if status in ("failed", "error"):
                        bright_budget.save_pending(fingerprint, None)
                        raise ProviderError(
                            f"Bright Data · {platform} : collecte refusée ({snapshot})"
                        )
                    if status not in ("running", "starting", "pending"):
                        raise ProviderError(
                            f"Bright Data · {platform} : état de collecte inconnu ({snapshot})"
                        )
                    await asyncio.sleep(3)
                response = await client.get(
                    API + "/snapshot/" + snapshot, params={"format": "json"}
                )
                if response.status_code != 200:
                    raise ProviderError(
                        f"Bright Data · {platform} : téléchargement HTTP {response.status_code} ({snapshot})"
                    )
                result = normalize(platform, response.json(), criteria)
                bright_budget.save_pending(fingerprint, None)
                return result
    except httpx.HTTPError, TimeoutError:
        raise ProviderError(
            f"Bright Data · {platform} : délai dépassé ou réseau indisponible. La collecte enregistrée sera reprise au prochain essai, sans nouveau déclenchement."
        ) from None
    except bright_budget.BrightError as exc:
        raise ProviderError(str(exc)) from None
