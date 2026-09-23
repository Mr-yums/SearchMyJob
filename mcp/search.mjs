// [Sol] One bounded search through the official MCP; token arrives over stdin.
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {fileURLToPath} from 'node:url';
let input='';for await(const chunk of process.stdin)input+=chunk;
const {token,query,budget,geo}=JSON.parse(input);
const here=fileURLToPath(new URL('.',import.meta.url));
const transport=new StdioClientTransport({command:process.execPath,args:['--import',here+'guard.mjs',here+'node_modules/@brightdata/mcp/server.js'],env:{PATH:process.env.PATH,HOME:process.env.HOME,API_TOKEN:token,SEARCHMYJOB_BRIGHT_BUDGET:budget,SEARCHMYJOB_BRIGHT_STRICT_SERP:'1',BASE_MAX_RETRIES:'0',BASE_TIMEOUT:'45',PRO_MODE:'false',GROUPS:'',TOOLS:'',WEB_UNLOCKER_ZONE:'mcp_unlocker'},stderr:'ignore'});
const client=new Client({name:'SearchMyJob-Sol',version:'1.0.0'});
try {
  await client.connect(transport);
  const result=await client.callTool({name:'search_engine',arguments:{query,engine:'google',geo_location:/^[a-z]{2}$/.test(geo)?geo:'fr'}},undefined,{timeout:60000});
  if(result.isError){const detail=result.content.filter(x=>x.type==='text').map(x=>x.text).join(' ');const status=detail.match(/HTTP \d{3}/)?.[0];throw Error(status||'MCP search failed');}
  const data=JSON.parse(result.content.filter(x=>x.type==='text').map(x=>x.text).join('\n'));
  if(!Array.isArray(data.organic))throw Error('Invalid results');
  process.stdout.write(JSON.stringify(data));
} catch(e) {const status=/^HTTP \d{3}$/.test(e.message)?' ('+e.message+')':'';process.stdout.write(JSON.stringify({error:'Bright Data : recherche MCP refusée ou indisponible'+status+'. Vérifie le jeton, le quota et le compteur.'}));process.exitCode=1;}
finally {await client.close();await transport.close();}
