from searchmyjob.config import PROJECT_ROOT

"""[Sol] No network: durable budget, concurrent reservations and MCP HTTP guard."""

import asyncio
import json
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest
from searchmyjob.infrastructure import bright_budget as bright_budget
from searchmyjob.integrations.search import providers as providers

ROOT = PROJECT_ROOT


@pytest.fixture
def budget(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCHMYJOB_STATE", str(tmp_path))
    bright_budget.initialize()
    return bright_budget.budget_path()


def node(code):
    return subprocess.run(
        ["node", "--input-type=module", "-e", code], cwd=ROOT, capture_output=True, text=True
    )


def test_concurrent_cap_and_restart(budget):
    # [OXIO] Le plafond est désormais une donnée : le test le fixe au lieu de le supposer.
    with sqlite3.connect(budget) as db:
        db.execute("UPDATE budget SET used=48,max_calls=50")
    code = f"import {{reserve}} from './mcp/guard.mjs';reserve({json.dumps(str(budget))},'test');"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: node(code), range(8)))
    assert sum(r.returncode == 0 for r in results) == 2
    assert bright_budget.status() == dict(used=50, limit=50, remaining=0, blocked=True)
    bright_budget.initialize()
    assert bright_budget.status()["used"] == 50
    assert node(code).returncode != 0


def test_http_guard_counts_failure_blocks_paid_and_redirects(budget):
    code = """import assert from 'node:assert/strict';
import axios from './mcp/node_modules/axios/index.js';
let sent=0;
axios.defaults.adapter=async c=>{sent++;assert.equal(c.maxRedirects,0);throw Error('simulated network failure');};
process.env.SEARCHMYJOB_BRIGHT_BUDGET=BUDGET;
await import('./mcp/guard.mjs');
await assert.rejects(axios.get('https://api.brightdata.com/zone/get_active_zones'));
await assert.rejects(axios.post('https://api.brightdata.com/request',{zone:'paid',url:'https://www.google.com/search?q=test'}));
await assert.rejects(axios.post('https://api.brightdata.com/zone',{zone:{name:'mcp_browser',type:'browser_api'}}));
await assert.rejects(axios.post('https://api.brightdata.com/request',{zone:'mcp_unlocker',url:'https://www.google.com/search?q=test'},{headers:{'x-mcp-tool':'search_engine'}}));
assert.equal(sent,2);
""".replace("=BUDGET;", "=" + json.dumps(str(budget)) + ";")
    result = node(code)
    assert result.returncode == 0, result.stderr
    # [OXIO] Seul l'appel facturant est décompté ; get_active_zones part sans consommer le plafond.
    assert bright_budget.status()["used"] == 1


def test_provider_stops_before_process(budget, monkeypatch):
    with sqlite3.connect(budget) as db:
        db.execute("UPDATE budget SET used=50,max_calls=50")
    monkeypatch.setattr(providers, "read", lambda: {"bright_key": "test"})
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", lambda *a, **k: pytest.fail("MCP started after limit")
    )
    with pytest.raises(providers.ProviderError, match="Stop-loss"):
        asyncio.run(providers.bright({"keywords": "test"}))
    budget.unlink()
    with pytest.raises(providers.ProviderError, match="Stop-loss"):
        asyncio.run(providers.bright({"keywords": "test"}))


# [Sol] Regression: valid Google /goto links must not disappear as zero results.
def test_google_result_links_and_no_destination_fetch():
    import httpx
    from searchmyjob.integrations.search.results import resolve_results

    seen = []

    def transport(request):
        seen.append(str(request.url))
        assert request.url.host == "www.google.com"
        assert "authorization" not in request.headers
        return httpx.Response(302, headers={"Location": "https://example.com/mission"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as c:
            return await resolve_results(
                [
                    {"title": "Mission IA", "link": "/goto?url=opaque"},
                    {"title": "Même lien", "link": "/goto?url=opaque"},
                    {"title": "Direct", "link": "https://jobs.example/1"},
                    {"title": "Unsafe", "link": "javascript:alert(1)"},
                    {"title": "Foreign relative", "link": "//127.0.0.1/secret"},
                ],
                c,
            )

    rows = asyncio.run(run())
    assert len(rows) == 3
    assert rows[0]["link"] == "https://example.com/mission" and not rows[0]["google_redirect"]
    assert seen == ["https://www.google.com/goto?url=opaque"]


def test_google_redirect_failure_keeps_usable_wrapper():
    import httpx
    from searchmyjob.integrations.search.results import normalize_link, resolve_results

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(429))
        ) as c:
            return await resolve_results([{"title": "Mission", "link": "/goto?url=opaque"}], c)

    row = asyncio.run(run())[0]
    assert row["link"] == "https://www.google.com/goto?url=opaque" and row["google_redirect"]
    assert normalize_link("/url?q=https%3A%2F%2Fexample.com%2Fjob") == "https://example.com/job"
    assert normalize_link("https://user:secret@example.com") == ""


def test_invalid_results_are_not_reported_as_empty(monkeypatch):
    async def none(items):
        return []

    monkeypatch.setattr(providers, "resolve_results", none)
    with pytest.raises(providers.ProviderError, match="format"):
        asyncio.run(providers.normalize_bright_results({"bad": "shape"}))
    with pytest.raises(providers.ProviderError, match="liens inexploitables"):
        asyncio.run(
            providers.normalize_bright_results(
                {"organic": [{"title": "x", "link": "javascript:x"}]}
            )
        )
    assert asyncio.run(providers.normalize_bright_results({"organic": []})) == []


def test_short_query_preserves_alternatives():
    from searchmyjob.domain.search_quality import search_plan
    from searchmyjob.integrations.search.results import search_query

    plans = search_plan(
        {
            "keywords": "automatisation IA, applications web, intégration API, dashboards",
            "freelance": True,
            "remote": True,
        }
    )
    assert len(plans) == 4
    assert "API integration" in search_query(plans[2])
    assert "site:fr.linkedin.com/jobs/view/" in search_query(plans[0])
    assert "site:fr.indeed.com/viewjob" in search_query(plans[0])
    assert "dashboards" == plans[3]["keywords"]


def test_guard_page_tool_is_bounded_and_does_not_expect_serp_json(budget):
    code = """import assert from 'node:assert/strict';
import axios from './mcp/node_modules/axios/index.js';
let sent=0;axios.defaults.adapter=async c=>{sent++;return {data:'Contenu public de la mission',status:200,headers:{},config:c};};
process.env.SEARCHMYJOB_BRIGHT_BUDGET=BUDGET;
await import('./mcp/guard.mjs');
const headers={'x-mcp-tool':'scrape_as_markdown'};
for(const url of ['https://127.0.0.1/','https://localhost/','https://host.internal/','https://user:pass@example.org/'])await assert.rejects(axios.post('https://api.brightdata.com/request',{zone:'mcp_unlocker',url,data_format:'markdown'},{headers}));
const r=await axios.post('https://api.brightdata.com/request',{zone:'mcp_unlocker',url:'https://example.org/jobs/1',data_format:'markdown'},{headers});
assert.equal(sent,1);assert.equal(r.data,'Contenu public de la mission');
""".replace("=BUDGET;", "=" + json.dumps(str(budget)) + ";")
    result = node(code)
    assert result.returncode == 0, result.stderr
    assert bright_budget.status()["used"] == 1


# [OXIO · Opus 5 · 16/09/2026] Catalogue complet ouvert aux agents : le garde reste la frontière.
def test_guard_opens_dataset_catalog_without_counting_polling(budget):
    code = """import assert from 'node:assert/strict';
import axios from './mcp/node_modules/axios/index.js';
let sent=0;axios.defaults.adapter=async c=>{sent++;return {data:{snapshot_id:'s_1'},status:200,headers:{},config:c};};
process.env.SEARCHMYJOB_BRIGHT_BUDGET=BUDGET;
await import('./mcp/guard.mjs');
const headers={'x-mcp-tool':'web_data_linkedin_company_profile'};
// Collecte déclenchée : facturée une fois.
await axios.post('https://api.brightdata.com/datasets/v3/trigger',[{url:'https://www.linkedin.com/company/acme'}],{headers});
// Attente du résultat : gratuite chez le fournisseur, donc jamais décomptée.
for(let i=0;i<40;i++)await axios.get('https://api.brightdata.com/datasets/v3/snapshot/s_1',{headers});
await axios.get('https://api.brightdata.com/datasets/gd_1',{headers});
// Recherche dans un dataset : facturée.
await axios.post('https://api.brightdata.com/datasets/search/gd_1',{query:'acme'},{headers});
assert.equal(sent,43);
""".replace("=BUDGET;", "=" + json.dumps(str(budget)) + ";")
    result = node(code)
    assert result.returncode == 0, result.stderr
    assert bright_budget.status()["used"] == 2


def test_guard_still_refuses_browser_zone_private_targets_and_unknown_routes(budget):
    code = """import assert from 'node:assert/strict';
import axios from './mcp/node_modules/axios/index.js';
let sent=0;axios.defaults.adapter=async c=>{sent++;return {data:{},status:200,headers:{},config:c};};
process.env.SEARCHMYJOB_BRIGHT_BUDGET=BUDGET;
await import('./mcp/guard.mjs');
const headers={'x-mcp-tool':'web_data_linkedin_person_profile'};
// Le mot de passe de zone ne sert qu'au navigateur distant, hors compteur : route fermée.
await assert.rejects(axios.get('https://api.brightdata.com/zone/passwords'));
// Une collecte ne peut pas viser le réseau privé ni transporter des identifiants.
for(const url of ['https://192.168.0.1/','https://10.0.0.5/','https://172.16.3.2/','https://user:pass@example.org/','http://example.org/'])
    await assert.rejects(axios.post('https://api.brightdata.com/datasets/v3/trigger',[{url}],{headers}));
await assert.rejects(axios.post('https://api.brightdata.com/datasets/v3/trigger',[{url:'https://ok.example/a'},{url:'https://127.0.0.1/b'}],{headers}));
// Un domaine étranger à Bright Data reste hors de portée.
await assert.rejects(axios.post('https://example.com/collect',{}));
assert.equal(sent,0);
""".replace("=BUDGET;", "=" + json.dumps(str(budget)) + ";")
    result = node(code)
    assert result.returncode == 0, result.stderr
    assert bright_budget.status()["used"] == 0


def test_local_budget_limit_and_reset(budget):
    with sqlite3.connect(budget) as db:
        db.execute("UPDATE budget SET used=45")
    assert bright_budget.status() == {"used": 45, "limit": 200, "remaining": 155, "blocked": False}
    assert bright_budget.set_limit(45)["blocked"] is True
    assert bright_budget.set_limit(500) == {
        "used": 45,
        "limit": 500,
        "remaining": 455,
        "blocked": False,
    }
    with pytest.raises(bright_budget.BrightError):
        bright_budget.set_limit(0)
    with pytest.raises(bright_budget.BrightError):
        bright_budget.set_limit(9000)
    assert bright_budget.reset() == {"used": 0, "limit": 500, "remaining": 500, "blocked": False}


def test_legacy_fifty_call_schema_is_migrated_keeping_the_counter(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCHMYJOB_STATE", str(tmp_path))
    path = bright_budget.budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE budget (id INTEGER PRIMARY KEY CHECK(id=1), used INTEGER NOT NULL CHECK(used BETWEEN 0 AND 50))"
        )
        db.execute("INSERT INTO budget VALUES (1,45)")
    bright_budget.initialize()
    # Le compteur consommé est conservé ; seul le plafond devient réglable.
    assert bright_budget.status() == {"used": 45, "limit": 200, "remaining": 155, "blocked": False}
    bright_budget.initialize()
    assert bright_budget.status()["used"] == 45


def test_full_browser_guard_counts_actions_refuses_private_and_closes(budget):
    code = """import assert from 'node:assert/strict';
process.env.SEARCHMYJOB_BRIGHT_BUDGET=BUDGET;
const {installBrowserGuard}=await import('./mcp/browser-guard.mjs');
let executed=0,closed=0,route;
const browser={close:async()=>{closed++}};
const page={route:async(pattern,fn)=>{route=fn}};
class Session{async get_browser(){return browser} async get_page(){return page}}
const tools=[{name:'scraping_browser_navigate',execute:async()=>{executed++;return 'ok'}}];
const cleanup=installBrowserGuard(tools,Session,{ttl:20});
await assert.rejects(tools[0].execute({url:'https://127.0.0.1/'}));
assert.equal(executed,0);
await tools[0].execute({url:'https://example.org/'});
assert.equal(executed,1);
const session=new Session();await session.get_browser();await session.get_page();
let aborted=false;
await route({request:()=>({isNavigationRequest:()=>true,url:()=> 'http://localhost/'}),abort:()=>{aborted=true},continue:()=>{throw Error('private navigation allowed')}});
assert.ok(aborted);
await new Promise(r=>setTimeout(r,40));assert.equal(closed,1);
const {DatabaseSync}=await import('node:sqlite');
const db=new DatabaseSync(process.env.SEARCHMYJOB_BRIGHT_BUDGET);db.exec('UPDATE budget SET used=max_calls');db.close();
await assert.rejects(tools[0].execute({url:'https://example.org/'}));
assert.equal(executed,1);await cleanup();
""".replace("=BUDGET;", "=" + json.dumps(str(budget)) + ";")
    result = node(code)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(budget) as db:
        assert db.execute("SELECT operation FROM calls").fetchall() == [
            ("scraping_browser_navigate",)
        ]


def test_full_catalog_browser_credentials_and_discover_polling(budget):
    code = """import assert from 'node:assert/strict';
import axios from './mcp/node_modules/axios/index.js';
let sent=0;axios.defaults.adapter=async c=>{sent++;return {data:{},status:200,headers:{},config:c}};
process.env.SEARCHMYJOB_BRIGHT_BUDGET=BUDGET;
process.env.SEARCHMYJOB_BRIGHT_BROWSER='1';
await import('./mcp/guard.mjs');
await axios.get('https://api.brightdata.com/zone/passwords?zone=mcp_browser');
await axios.post('https://api.brightdata.com/zone',{zone:{name:'mcp_browser',type:'browser_api'}});
await axios.get('https://api.brightdata.com/discover',{params:{task_id:'test'}});
await assert.rejects(axios.get('https://api.brightdata.com/zone/passwords?zone=other'));
await assert.rejects(axios.post('https://api.brightdata.com/zone',{zone:{name:'other',type:'browser_api'}}));
assert.equal(sent,3);
""".replace("=BUDGET;", "=" + json.dumps(str(budget)) + ";")
    result = node(code)
    assert result.returncode == 0, result.stderr
    assert bright_budget.status()["used"] == 0
