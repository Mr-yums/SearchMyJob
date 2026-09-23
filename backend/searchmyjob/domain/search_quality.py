"""[Sol] Bounded independent topics and conservative, evidence-bearing qualification."""

import re
import unicodedata
from urllib.parse import parse_qs, urlsplit

from searchmyjob.domain.countries import COUNTRIES

AXES = {
    "automatisation IA": '("AI automation" OR "automatisation IA" OR n8n)',
    "applications web": '("web application" OR "application web" OR "full stack")',
    "intégration API": '("API integration" OR "intégration API")',
    "dashboards": '(dashboard OR "tableau de bord")',
}


def fold(text):
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )


def search_plan(c):
    topics = c.get("axes") or [t.strip() for t in re.split(r"[,;\n]+", c["keywords"]) if t.strip()]
    topics = list(dict.fromkeys(topics))[:4]
    plans = [{**c, "keywords": t, "axes": []} for t in topics]
    if c.get("objectif", "emploi") != "emploi" or "country" not in c:
        return plans
    return [
        {**plan, "platforms": [platform], "_platform": platform}
        for plan in plans
        for platform in dict.fromkeys(c.get("platforms", DEFAULT_PLATFORMS))
    ]


PLATFORMS = ("linkedin", "indeed", "direct", "freelance")
DEFAULT_PLATFORMS = ["linkedin", "indeed", "direct"]


def platform_name(url):
    host = (urlsplit(url).hostname or "").lower()
    for domain, name in [
        ("linkedin.com", "LinkedIn"),
        ("indeed.com", "Indeed"),
        ("upwork.com", "Upwork"),
        ("freelancer.com", "Freelancer"),
    ]:
        if host == domain or host.endswith("." + domain):
            return name
    return "Autres sites"


def excluded_domains(c):
    text = fold(c.get("exclude", ""))
    return [
        domain
        for word, domain in [
            ("upwork", "upwork.com"),
            ("freelancer", "freelancer.com"),
            ("linkedin", "linkedin.com"),
            ("indeed", "indeed.com"),
        ]
        if re.search(r"(?<![a-z])" + word + r"(?![a-z])", text)
    ]


def platform_allowed(row, c):
    if row.get("source") != "Bright Data":
        return True
    selected = c.get("platforms", DEFAULT_PLATFORMS)
    platform = platform_name(row.get("url", ""))
    key = {
        "LinkedIn": "linkedin",
        "Indeed": "indeed",
        "Upwork": "freelance",
        "Freelancer": "freelance",
        "Autres sites": "direct",
    }[platform]
    return key in selected


def source_excluded(row, c):
    host = (urlsplit(row.get("url", "")).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in excluded_domains(c))


# [OXIO · Opus 4.8 · 16/09/2026] Canaux qui ne sont jamais des clients : job boards, places de
# marché, plateformes freelance et réseaux. Exclus en prospection pour faire remonter des sites d'entreprises.
NON_CLIENT_SITES = (
    "indeed.com",
    "fr.indeed.com",
    "linkedin.com",
    "welcometothejungle.com",
    "pole-emploi.fr",
    "francetravail.fr",
    "apec.fr",
    "hellowork.com",
    "leboncoin.fr",
    "pagesjaunes.fr",
    "societe.com",
    "malt.fr",
    "comeup.com",
    "fr.freelancer.com",
    "upwork.com",
    "fiverr.com",
    "facebook.com",
    "youtube.com",
    "wikipedia.org",
)


def prospect_query(c):
    """Requête orientée entreprises à démarcher : secteur + lieu + signaux de contact, sans les canaux d'emploi."""
    topic = (
        AXES.get(c["keywords"], c["keywords"].replace('"', ""))
        if c.get("international", True)
        else c["keywords"].replace('"', "")
    )
    location = ", ".join(
        filter(None, [c.get("location", "").strip(), COUNTRIES.get(c.get("country"), "")])
    )
    if fold(location) in ("international", "worldwide", "monde", "partout"):
        location = ""
    excl = " ".join(
        "-site:" + d for d in dict.fromkeys(list(NON_CLIENT_SITES) + excluded_domains(c))
    )
    hint = '(contact OR "nous contacter" OR "à propos" OR "mentions légales")'
    parts = [
        topic,
        location,
        hint,
        "-inurl:jobs",
        "-inurl:emploi",
        "-inurl:offre",
        "-inurl:recrutement",
        "-inurl:job",
        excl,
    ]
    return " ".join(x for x in parts if x)


def targeted_query(c):
    if c.get("objectif") == "prospection":
        return prospect_query(c)
    international = c.get("international", True)
    topic = (
        AXES.get(c["keywords"], c["keywords"].replace('"', ""))
        if international
        else c["keywords"].replace('"', "")
    )
    selected = c.get("platforms", DEFAULT_PLATFORMS)
    targets = {
        "linkedin": ["site:linkedin.com/jobs/view/", "site:fr.linkedin.com/jobs/view/"]
        if international
        else ["site:fr.linkedin.com/jobs/view/"],
        "indeed": ["site:indeed.com/viewjob", "site:fr.indeed.com/viewjob"]
        if international
        else ["site:fr.indeed.com/viewjob"],
        "direct": ["inurl:mission", "inurl:missions", "inurl:offre", "inurl:jobs/apply"],
        "freelance": ["site:upwork.com/freelance-jobs/apply/", "site:freelancer.com/projects/"],
    }
    target = (
        "("
        + " OR ".join(dict.fromkeys(t for p in selected if p in targets for t in targets[p]))
        + ")"
    )
    location = ", ".join(
        filter(None, [c.get("location", "").strip(), COUNTRIES.get(c.get("country"), "")])
    )
    if fold(location) in ("international", "worldwide", "monde", "partout"):
        location = ""
    exclusions = " ".join("-site:" + d for d in excluded_domains(c))
    return " ".join(
        x
        for x in [
            topic,
            location,
            "(freelance OR indépendant OR contractor OR contract)" if c.get("freelance") else "",
            "(remote OR télétravail OR worldwide)" if c.get("remote") else "",
            target,
            "-inurl:hire -inurl:profiles",
            exclusions,
        ]
        if x
    )


def kind(row):
    u = urlsplit(row.get("url", ""))
    p = u.path.lower().rstrip("/")
    host = (u.hostname or "").lower()
    if not u.hostname or row.get("google_redirect"):
        return "web_lead"
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        if re.match(r"^/jobs/view/[^/]+", p):
            return "individual"
        if p.startswith("/jobs"):
            return "listing"
    if host == "indeed.com" or host.endswith(".indeed.com"):
        if p in ("/viewjob", "/rc/clk") and parse_qs(u.query).get("jk", [""])[0]:
            return "individual"
        if p in ("/jobs", "/viewjob", "/rc/clk") or p.endswith("emplois.html"):
            return "listing"
    if re.search(r"/(search|recherche|hire(?:-[^/]+)?|profiles?|freelancers?)(/|$)", p) or any(
        k + "=" in u.query for k in ["q", "query", "search"]
    ):
        return "listing"
    if host == "upwork.com" or host.endswith(".upwork.com"):
        return "individual" if "/freelance-jobs/apply/" in p else "listing"
    if host == "freelancer.com" or host.endswith(".freelancer.com"):
        return "individual" if re.match(r"^/projects/[^/]+/[^/]+", p) else "listing"
    if re.search(r"/(missions?|jobs?|offres?|projects?)/[^/]+", p):
        return "individual"
    if p in ("", "/jobs", "/missions", "/offres", "/freelance-jobs") or re.search(
        r"\b\d+\s+(jobs|missions|offres)\b", fold(row.get("title", ""))
    ):
        return "listing"
    return "web_lead"


def qualify(row):
    # No inference from the query, the platform, or the language of the page.
    text = " ".join(str(row.get(k, "")) for k in ("title", "description", "contract"))
    segments = re.split(r"[.!?\n]+", text)
    rules = {
        "freelance": (
            r"no freelanc|not (?:a )?freelanc|pas de freelance|permanent employee|\bcdi\b",
            r"\bfreelance\b|\bcontractor\b|\bindependant\b",
        ),
        "remote": (
            r"hybrid|hybride|on[- ]site|sur site|presentiel|not (?:fully |100% )?remote|pas (?:de teletravail|entierement a distance)",
            r"100\s*%\s*(?:a distance|remote|teletravail)|fully remote|full remote|entierement a distance",
        ),
        "travel": (
            r"(?<!no )travel required|occasional travel|deplacements? (?:obligatoires?|requis|ponctuels)|visites? (?:client|sur site)",
            r"no travel(?: required)?|sans deplacement|aucun deplacement",
        ),
        "language": (
            r"fluent english|native english|english (?:fluency|required)|anglais (?:courant|bilingue|obligatoire)|no translation|translation tools? (?:not accepted|not allowed)|traduction interdite",
            r"translation tools? (?:are )?(?:accepted|allowed)|outils? de traduction (?:acceptes?|autorises?)|french[- ]only|francais uniquement",
        ),
        "availability": (r"\bclosed\b|\bexpired\b|offre expiree|mission pourvue", r"(?!)"),
    }
    conditions = {}
    for key, (negative, positive) in rules.items():
        bad = next((s.strip() for s in segments if re.search(negative, fold(s))), None)
        good = next((s.strip() for s in segments if re.search(positive, fold(s))), None)
        conditions[key] = {
            "state": "conflict" if bad else "mentioned" if good else "unknown",
            "evidence": (bad or good or "")[:300],
            "source": "extrait de recherche, page non vérifiée",
        }
    return {"result_kind": kind(row), "conditions": conditions, "verification": "snippet_only"}


def checks(row, c):
    q = qualify(row)
    for key in ("freelance", "remote", "travel", "language"):
        requested = (
            c.get("freelance")
            if key == "freelance"
            else c.get("remote")
            if key == "remote"
            else False
        )
        if not requested and q["conditions"][key]["state"] == "conflict":
            q["conditions"][key]["state"] = "mentioned"
    if row.get("collection_method") == "brightdata_scraper":
        q["verification"] = "platform_data"
        for condition in q["conditions"].values():
            condition["source"] = "annonce collectée via Bright Data, conditions à confirmer"
    labels = {
        "individual": "Annonce individuelle probable · à vérifier",
        "listing": "Page de recherche / annuaire",
        "web_lead": "Piste web · annonce non identifiée",
    }
    notes = [labels[q["result_kind"]]]
    names = {
        "freelance": "Freelance",
        "remote": "100 % à distance",
        "travel": "Sans déplacement",
        "language": "Langue / traduction",
        "availability": "Disponibilité",
    }
    for key, val in q["conditions"].items():
        if key == "freelance" and not c.get("freelance"):
            continue
        if key in ("remote", "travel") and not c.get("remote"):
            continue
        if key == "availability" and val["state"] == "unknown":
            continue
        notes.append(
            names[key]
            + (
                " : contradiction dans l’extrait"
                if val["state"] == "conflict"
                else " : mention dans l’extrait, à confirmer"
                if val["state"] == "mentioned"
                else " : à vérifier"
            )
        )
    if c.get("min_tjm"):
        notes.append(f"TJM ≥ {c['min_tjm']} € à vérifier")
    q["checks"] = notes
    return q
