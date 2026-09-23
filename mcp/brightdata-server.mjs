// [OXIO · Opus 5 · 16/09/2026] Serveur MCP Bright Data exposé aux agents natifs.
// Lancé par agents.py avec `--import guard.mjs` : le garde HTTP et le plafond local
// s'appliquent donc à tous les outils du catalogue, sans exception.
// Le jeton arrive par fichier (0600) et n'apparaît ni dans la ligne de commande,
// ni dans l'environnement transmis au client agent.
import {readFileSync} from 'node:fs';
const tokenFile=process.env.SEARCHMYJOB_BRIGHT_TOKEN_FILE;
if(!tokenFile){console.error('SEARCHMYJOB_BRIGHT_TOKEN_FILE manquant');process.exit(2);}
const token=readFileSync(tokenFile,'utf8').trim();
if(!token){console.error('Jeton Bright Data vide');process.exit(2);}
process.env.API_TOKEN=token;
delete process.env.SEARCHMYJOB_BRIGHT_TOKEN_FILE;
// Full pinned catalog, explicitly requested by Yums on 2026-09-17.
process.env.PRO_MODE='true';
process.env.GROUPS='';
process.env.TOOLS='';
process.env.SEARCHMYJOB_BRIGHT_BROWSER='1';
process.env.BROWSER_ZONE='mcp_browser';
process.env.WEB_UNLOCKER_ZONE='mcp_unlocker';
process.env.BASE_MAX_RETRIES='0';
// Une recherche Google via l'unlocker rend en général en quelques secondes, mais a été vue
// dépasser 45 s ; un échec consomme le plafond comme un succès. Marge prise sous le
// tool_timeout de 150 s du client.
process.env.BASE_TIMEOUT=process.env.SEARCHMYJOB_BRIGHT_TIMEOUT||'110';
// Le polling d'une collecte dataset est gratuit mais long : borné pour ne pas bloquer un tour d'agent.
process.env.POLLING_TIMEOUT=process.env.SEARCHMYJOB_BRIGHT_POLLING||'120';
const {tools}=await import('./node_modules/@brightdata/mcp/browser_tools.js');
const {Browser_session}=await import('./node_modules/@brightdata/mcp/browser_session.js');
const {installBrowserGuard}=await import('./browser-guard.mjs');
installBrowserGuard(tools,Browser_session);
await import('./node_modules/@brightdata/mcp/server.js');
