// [Sol] Guard every HTTP request in the pinned Bright Data MCP, including startup.
// Garde HTTP et compteur partagé des connecteurs de recherche et de lecture.
// contrôle d'URL conservé, comptage restreint aux appels facturants (le polling snapshot ne compte pas).
import axios from './node_modules/axios/index.js';
import {DatabaseSync} from 'node:sqlite';
import {writeFileSync,renameSync} from 'node:fs';
import {dirname,join} from 'node:path';
const UNLOCKER=process.env.WEB_UNLOCKER_ZONE||'mcp_unlocker';
const STRICT_SERP=process.env.SEARCHMYJOB_BRIGHT_STRICT_SERP==='1';
function privateHost(host){
    if(/^\[?::1\]?$/.test(host))return true;
    const v4=host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    if(!v4)return false;
    const [a,b]=v4.slice(1).map(Number);
    return a===10||a===127||a===0||(a===172&&b>=16&&b<=31)||(a===192&&b===168)||(a===169&&b===254)||(a===100&&b>=64&&b<=127);
}
export function publicPage(value){
    try{
        const u=new URL(value);
        return u.protocol==='https:'&&!u.username&&!u.password&&(!u.port||u.port==='443')
            &&/[a-z]/i.test(u.hostname)&&u.hostname.includes('.')
            &&!/(:|\.(local|localhost|internal|test|invalid)$)/i.test(u.hostname)
            &&!privateHost(u.hostname);
    }catch{return false;}
}
// [OXIO] Les collectes de datasets reçoivent un tableau d'entrées ; une entrée peut cibler une URL.
function bodyUrlsAllowed(body){
    const entries=Array.isArray(body)?body:[body];
    return entries.every(entry=>{
        if(!entry||typeof entry!=='object')return true;
        return Object.entries(entry).every(([key,value])=>
            !/^(url|link|page_url|profile_url|post_url)$/i.test(key)||typeof value!=='string'||publicPage(value));
    });
}
// Retourne null si l'opération est refusée, sinon {billable}.
function classify(method,url,body,tool){
    if(url.origin!=='https://api.brightdata.com')return null;
    const path=url.pathname;
    if(method==='GET'&&path==='/zone/get_active_zones')return {billable:false};
    if(method==='GET'&&path==='/status')return {billable:false};
    if(method==='GET'&&path==='/discover')return {billable:false};
    if(process.env.SEARCHMYJOB_BRIGHT_BROWSER==='1'){
        if(method==='GET'&&path==='/zone/passwords'&&url.searchParams.get('zone')==='mcp_browser')return {billable:false};
        if(method==='POST'&&path==='/zone'&&body?.zone?.name==='mcp_browser'&&body?.zone?.type==='browser_api')return {billable:false};
    }
    // Les clients recherche/page restent limités à unlocker ; le serveur complet ouvre aussi mcp_browser.
    if(method==='POST'&&path==='/zone')
        return body?.zone?.name===UNLOCKER&&body?.zone?.type==='unblocker'?{billable:false}:null;
    if(method==='POST'&&path==='/request')
        return body?.zone===UNLOCKER&&publicPage(body?.url)?{billable:true}:null;
    if(method==='POST'&&path==='/datasets/v3/trigger')
        return bodyUrlsAllowed(body)?{billable:true}:null;
    // Attente du résultat d'une collecte déjà facturée : jusqu'à 600 appels, jamais comptés.
    if(method==='GET'&&/^\/datasets\/v3\/(snapshot|progress)\/[\w.-]+$/.test(path))return {billable:false};
    if(method==='GET'&&/^\/datasets\/[\w.-]+$/.test(path))return {billable:false};
    if(method==='POST'&&/^\/datasets\/search\/[\w.-]+$/.test(path))return {billable:true};
    if(method==='POST'&&path==='/discover')
        return bodyUrlsAllowed(body)?{billable:true}:null;
    return null;
}
const adapter=axios.getAdapter(axios.defaults.adapter);
export function reserve(path, operation) {
    const db=new DatabaseSync(path,{open:true});
    try {
        db.exec('PRAGMA busy_timeout=10000; BEGIN IMMEDIATE');
        const changed=db.prepare('UPDATE budget SET used=used+1 WHERE id=1 AND used<max_calls').run().changes;
        if(changed!==1) throw Error('Stop-loss Bright Data : plafond local atteint');
        db.prepare('INSERT INTO calls(operation) VALUES (?)').run(operation);
        db.exec('COMMIT');
    } catch(e) { try {db.exec('ROLLBACK');} catch {} throw e; }
    finally {db.close();}
}
axios.defaults.adapter=async config=>{
    const url=new URL(config.url);
    const method=(config.method||'get').toUpperCase();
    let body=config.data;
    if(typeof body==='string'){try{body=JSON.parse(body);}catch{body=null;}}
    const tool=config.headers?.get?.('x-mcp-tool')||'';
    const verdict=classify(method,url,body,tool);
    if(!verdict)throw Error('Opération Bright Data bloquée par SearchMyJob');
    if(verdict.billable)reserve(process.env.SEARCHMYJOB_BRIGHT_BUDGET,(tool||method)+' '+url.pathname);
    config.maxRedirects=0;
    config.timeout=Math.max(config.timeout||0,45000);
    const response=await adapter(config);
    if(STRICT_SERP&&url.pathname==='/request'&&tool==='search_engine'){
        // [Sol] Retain one private response for diagnosis; never headers or credentials.
        const raw=typeof response.data==='string'?response.data:JSON.stringify(response.data);
        const redacted=process.env.API_TOKEN?raw.split(process.env.API_TOKEN).join('[REDACTED]'):raw;
        if(redacted.length<=2000000){
            const dest=join(dirname(process.env.SEARCHMYJOB_BRIGHT_BUDGET),'bright-last-response.json');
            const tmp=dest+'.'+process.pid+'.tmp';
            writeFileSync(tmp,JSON.stringify({received:new Date().toISOString(),query:new URL(body.url).searchParams.get('q'),body:redacted}),{mode:0o600});
            renameSync(tmp,dest);
        }
        // [Sol] The upstream MCP otherwise converts unknown JSON shapes into organic: [].
        const data=typeof response.data==='string'?JSON.parse(response.data):response.data;
        if(!data||!Array.isArray(data.organic))throw Error('Bright Data: invalid SERP response');
        if(data.organic.length&&!data.organic.some(x=>x&&typeof x.title==='string'&&x.title.trim()&&typeof x.link==='string'&&x.link.trim()))throw Error('Bright Data: unusable SERP entries');
    }
    return response;
};
