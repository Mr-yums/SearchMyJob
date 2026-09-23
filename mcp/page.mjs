import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {fileURLToPath} from 'node:url';
let input='';for await(const chunk of process.stdin)input+=chunk;
const {token,url,budget}=JSON.parse(input),here=fileURLToPath(new URL('.',import.meta.url));
const transport=new StdioClientTransport({command:process.execPath,args:['--import',here+'guard.mjs',here+'node_modules/@brightdata/mcp/server.js'],env:{PATH:process.env.PATH,HOME:process.env.HOME,API_TOKEN:token,SEARCHMYJOB_BRIGHT_BUDGET:budget,BASE_MAX_RETRIES:'0',BASE_TIMEOUT:'45',PRO_MODE:'false',GROUPS:'',TOOLS:'scrape_as_markdown',WEB_UNLOCKER_ZONE:'mcp_unlocker'},stderr:'ignore'});
const client=new Client({name:'SearchMyJob',version:'1.0.0'});
try{
 await client.connect(transport);
 const result=await client.callTool({name:'scrape_as_markdown',arguments:{url}},undefined,{timeout:60000});
 if(result.isError)throw Error();
 const text=result.content.filter(c=>c.type==='text').map(c=>c.text).join('\n');
 if(!text.trim()||text.length>1000000)throw Error();
 process.stdout.write(JSON.stringify({text}));
}catch{process.stdout.write(JSON.stringify({error:'Page inaccessible via Bright Data. Aucun nouvel essai automatique.'}));process.exitCode=1;}
finally{await client.close();await transport.close();}
