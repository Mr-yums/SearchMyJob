"""[Sol] Synthetic evidence; no provider calls or claims of verified listings."""

from searchmyjob.domain.search_quality import checks, qualify, search_plan, targeted_query


def test_individual_vs_listing():
    for url, expected in [
        ("https://www.upwork.com/freelance-jobs/api/", "listing"),
        ("https://www.upwork.com/freelance-jobs/apply/api_~123/", "individual"),
        ("https://www.freelancer.com/jobs/automation", "listing"),
        ("https://www.freelancer.com/projects/automation/build-tool", "individual"),
        ("https://example.test/search?q=api", "listing"),
        ("https://example.test/jobs", "listing"),
        ("https://example.test/mission/developpeur", "individual"),
    ]:
        assert qualify({"url": url})["result_kind"] == expected


def test_conditions_are_not_inferred_from_query_or_platform():
    q = checks(
        {"url": "https://www.upwork.com/freelance-jobs/apply/test", "title": "Développeur remote"},
        {"remote": True, "freelance": True},
    )
    assert q["conditions"]["remote"]["state"] == "unknown"
    assert q["conditions"]["freelance"]["state"] == "unknown"
    assert q["conditions"]["language"]["state"] == "unknown"
    assert q["verification"] == "snippet_only"


def test_explicit_conditions_with_evidence():
    q = qualify(
        {"description": "Freelance. Fully remote. No travel required. Translation tools accepted."}
    )
    for k in ["freelance", "remote", "travel", "language"]:
        assert q["conditions"][k]["state"] == "mentioned"
        assert q["conditions"][k]["evidence"]


def test_conflicts_win_and_closed_jobs_are_flagged():
    q = qualify(
        {
            "description": "Freelance fully remote. Hybrid on-site visits. Travel required. Fluent English. Closed."
        }
    )
    for k in ["remote", "travel", "language", "availability"]:
        assert q["conditions"][k]["state"] == "conflict"


def test_four_axes_are_explicit_independent_and_bounded():
    plans = search_plan(
        {
            "keywords": "ignored",
            "axes": ["automatisation IA", "applications web", "intégration API", "dashboards"],
            "remote": True,
        }
    )
    assert len(plans) == 4 and all(p["axes"] == [] for p in plans)
    queries = [targeted_query(p) for p in plans]
    assert len(set(queries)) == 4
    assert len(search_plan({"keywords": "a,b,c,d,e"})) == 4


def test_negations_do_not_confirm_requirements():
    q = qualify(
        {"description": "Not fully remote. No freelancers. Translation tools not accepted."}
    )
    assert q["conditions"]["remote"]["state"] == "conflict"
    assert q["conditions"]["freelance"]["state"] == "conflict"
    assert q["conditions"]["language"]["state"] == "conflict"


def test_local_target_omits_international_platforms():
    query = targeted_query({"keywords": "applications web", "international": False})
    assert "upwork.com" not in query and "freelancer.com" not in query


def test_linkedin_indeed_individual_announcements_and_lists():
    for url, expected in [
        ("https://fr.linkedin.com/jobs/view/developpeur-123", "individual"),
        ("https://www.linkedin.com/jobs/search/?keywords=python", "listing"),
        ("https://fr.linkedin.com/jobs/python-freelance-emplois", "listing"),
        ("https://fr.indeed.com/viewjob?jk=123abc", "individual"),
        ("https://fr.indeed.com/rc/clk?jk=123abc", "individual"),
        ("https://fr.indeed.com/viewjob", "listing"),
        ("https://fr.indeed.com/jobs?q=freelance", "listing"),
    ]:
        assert qualify({"url": url})["result_kind"] == expected


def test_platform_selection_and_domain_exclusions():
    from searchmyjob.domain.search_quality import source_excluded

    c = {
        "keywords": "Python",
        "platforms": ["linkedin", "indeed"],
        "location": "International",
        "exclude": "Upwork, CDI",
        "freelance": True,
    }
    q = targeted_query(c)
    assert "site:fr.linkedin.com/jobs/view/" in q and "site:fr.indeed.com/viewjob" in q
    assert "inurl:mission" not in q and "International" not in q
    assert "-site:upwork.com" in q
    assert source_excluded({"url": "https://www.upwork.com/freelance-jobs/apply/123"}, c)
    assert not source_excluded({"url": "https://upwork.com.example.org/jobs/123"}, c)
    q = targeted_query({**c, "platforms": ["indeed"], "international": False})
    assert "linkedin" not in q and "site:fr.indeed.com/viewjob" in q


def test_off_target_domains_are_filtered_even_if_google_returns_them():
    from searchmyjob.domain.search_quality import platform_allowed

    c = {"platforms": ["linkedin", "indeed"]}
    assert platform_allowed(
        {"source": "Bright Data", "url": "https://fr.linkedin.com/jobs/view/123"}, c
    )
    assert platform_allowed(
        {"source": "Bright Data", "url": "https://fr.indeed.com/viewjob?jk=abc"}, c
    )
    assert not platform_allowed(
        {"source": "Bright Data", "url": "https://www.upwork.com/jobs/123"}, c
    )
    assert not platform_allowed(
        {"source": "Bright Data", "url": "https://example.org/mission/123"}, c
    )
    assert platform_allowed({"source": "France Travail", "url": "https://entreprise.org"}, c)
    assert qualify({"url": "https://arc.dev/hire-developers/python"})["result_kind"] == "listing"


# [OXIO · Opus 4.8 · 16/09/2026] Mode prospection : requête orientée entreprises, sans canaux d'emploi.
def test_prospection_query_targets_companies_not_job_boards():
    from searchmyjob.domain.guidance import guidance, report_format

    emploi = {
        "keywords": "automatisation IA",
        "platforms": ["linkedin", "indeed"],
        "international": True,
        "location": "Lyon",
    }
    prosp = {
        "keywords": "agence immobilière",
        "objectif": "prospection",
        "location": "Lyon",
        "international": False,
    }
    q_emploi = targeted_query(emploi)
    q_prosp = targeted_query(prosp)
    # Emploi inchangé : il vise toujours les fiches d'offres.
    assert "linkedin.com/jobs/view/" in q_emploi
    # Prospection : sites d'entreprises, canaux d'emploi et places de marché exclus.
    assert "agence immobilière" in q_prosp and "nous contacter" in q_prosp
    assert (
        "-site:indeed.com" in q_prosp
        and "-site:linkedin.com" in q_prosp
        and "-site:malt.fr" in q_prosp
    )
    assert "-inurl:emploi" in q_prosp
    assert "jobs/view" not in q_prosp
    # Les consignes basculent aussi.
    assert "PROSPECTION" in guidance("prospection") and "candidature" in guidance("emploi")
    assert (
        "prospect" in report_format("prospection").lower()
        and "mission" in report_format("emploi").lower()
    )


def test_default_objectif_keeps_job_mode():
    # Sans champ objectif, comportement d'origine (emploi).
    from searchmyjob.domain.guidance import guidance

    q = targeted_query({"keywords": "développeur", "platforms": ["direct"], "international": False})
    assert "inurl:mission" in q
    assert guidance() is not None and "candidature" in guidance()
