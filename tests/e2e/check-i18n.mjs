import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||new URL('../../ui/node_modules/playwright/index.mjs',import.meta.url).href);
const base=process.env.SEARCHMYJOB_TEST_URL||'http://127.0.0.1:18936';
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,headless:true});
const errors=[],writes=[];
const state={token:'fixture-only',profile:'',conversation_id:'main',conversations:[{id:'main',title:'Mon profil',archived:false}],
 messages:[],offers:[],runs:[],documents:[],emails:[],imports:[],tool_calls:[],models:{},connections:{},
 criteria:{country:'fr',response_language:'fr',objectif:'emploi',axes:[],platforms:[],international:false,keywords:'Python',department:'',location:'',contract:'',remote:true,freelance:true,min_tjm:0,exclude:'',source:'france'},
 settings:{enabled:false,interval_hours:4,start_hour:8,end_hour:20,max_daily:3,provider:'openai',cache_hours:24,instructions:''},
 bright_budget:{used:0,limit:200,remaining:200,blocked:false},agent_usage:{total_tokens:1234,providers:{}},
 mail:{connected:false,address:'',pending:false,auth_url:'',error:''},next_heartbeat:null};
let activated=false,configured=false;
const context=await browser.newContext({locale:'fr-FR',viewport:{width:1440,height:1000}});
await context.route('**/api/**',async route=>{
 const req=route.request(),path=new URL(req.url()).pathname;
 const body=req.method()==='POST'?req.postDataJSON():null;
 if(body)writes.push({path,body});
 let result={};let status=200;
 if(path==='/api/state')result=state;
 else if(path==='/api/activation'){
  if(body){activated=true;state.profile=body.profile;}
  result={completed:activated};
 }else if(path==='/api/workspace-memory')result={preferences:null,heartbeat_draft:null};
 else if(path==='/api/ai')result={openai:{configured,model:'fixture-model'}};
 else if(path==='/api/ai/models')result={models:['fixture-model']};
 else if(path==='/api/ai/test'){
  if(body.key==='bad'){status=422;result={detail:'Clé API refusée (HTTP 401).'};}
  else{configured=true;result={ok:true};}
 }else if(path==='/api/connections')result={france:true,bright:true};
 else if(path==='/api/search/options')result={countries:['fr','de','be','it']};
 else if(path==='/api/bright/usage')result={status:'ok',used:1234,period_start:'2026-09-01',checked_at:1789690000};
 else if(path==='/api/criteria')state.criteria=body;
 else if(!['/api/preferences','/api/heartbeat-draft'].includes(path))errors.push('Unexpected API request: '+path);
 await route.fulfill({status,json:result});
});
const page=await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
const language=()=>page.getByLabel('Langue / Language');
const setLanguage=async value=>{await language().selectOption(value);assert.equal(await page.locator('html').getAttribute('lang'),value);};
try{
 await page.goto(base);await page.getByRole('heading',{name:'Connecte ton assistant IA'}).waitFor();
 await page.getByLabel('Clé API',{exact:true}).fill('bad');await page.getByLabel('Identifiant du modèle',{exact:true}).fill('fixture-model');
 await setLanguage('en');assert.equal(await page.getByLabel('API key',{exact:true}).inputValue(),'bad');
 await page.getByRole('button',{name:'Test and save',exact:true}).click();
 await page.getByRole('alert').filter({hasText:'API key rejected (HTTP 401).'}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Continue',exact:true}).isDisabled(),true);
 await setLanguage('fr');await page.getByRole('alert').filter({hasText:'Clé API refusée (HTTP 401).'}).waitFor();
 await setLanguage('en');await page.getByLabel('API key',{exact:true}).fill('fixture-key');
 await page.getByRole('button',{name:'Load models'}).click();await page.getByLabel('Available models',{exact:true}).selectOption('fixture-model');
 await page.getByRole('button',{name:'Test and save',exact:true}).click();
 await page.getByText('Connection and tool call verified. Configuration saved.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Continue',exact:true}).click();
 await page.getByRole('heading',{name:'Choose your search sources'}).waitFor();
 await page.getByLabel('Search country',{exact:true}).selectOption('fr');
 await page.getByLabel('Role / keywords',{exact:true}).fill('Comptable');
 await setLanguage('fr');await page.getByRole('heading',{name:'Choisis tes sources de recherche'}).waitFor();
 await page.getByRole('button',{name:'Continuer',exact:true}).click();
 await page.getByLabel('Ton parcours et tes compétences').fill('Mon profil');
 await page.getByLabel('Métier ou type de mission').fill('Python');
 await setLanguage('en');assert.equal(await page.getByLabel('Your background and skills').inputValue(),'Mon profil');
 await page.getByRole('button',{name:'Activate my workspace'}).click();
 await page.getByLabel('Your message',{exact:true}).waitFor();
 assert.equal(state.profile,'Mon profil');
 await page.getByLabel('Your message',{exact:true}).fill('Brouillon personnel à conserver');
 await setLanguage('fr');assert.equal(await page.getByLabel('Ton message',{exact:true}).inputValue(),'Brouillon personnel à conserver');
 await setLanguage('en');await page.reload();await page.getByLabel('Your message',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Your message',{exact:true}).inputValue(),'Brouillon personnel à conserver');
 assert.equal(await page.title(),'SearchMyJob — Career workspace');
 assert.equal(await page.locator('.guide-link').getAttribute('href'),'/guide-en.html');
 await page.getByRole('button',{name:'Find my next project',exact:true}).click();
 assert((await page.getByLabel('Your message',{exact:true}).inputValue()).includes('Based on my profile and criteria'));
 async function nav(name){
  const reveal=page.getByRole('button',{name:'Show navigation',exact:true});if(await reveal.isVisible())await reveal.click();
  await page.locator('.app-sidebar nav').getByRole('button',{name,exact:true}).click();
 }
 await nav('Opportunities');await page.getByRole('button',{name:'Advanced criteria',exact:true}).click();
 await page.getByLabel('France Travail contract',{exact:true}).selectOption('CDI');
 await page.getByLabel('Other professions to search (one per line, maximum 4)',{exact:true}).fill('Comptable');
 await page.getByLabel('Role / keywords',{exact:true}).fill('Un filtre conservé');
 await setLanguage('fr');assert.equal(await page.getByLabel('Métier / mots-clés',{exact:true}).inputValue(),'Un filtre conservé');
 await setLanguage('en');await page.getByRole('button',{name:'Save',exact:true}).click();
 const saved=writes.findLast(w=>w.path==='/api/criteria').body;
 assert.equal(saved.contract,'CDI');assert.deepEqual(saved.axes,['Comptable']);
 await nav('My profile');assert.equal(await page.locator('.profile-banner h2').innerText(),'Mon profil');
 await page.getByRole('button',{name:'Edit my profile',exact:true}).click();
 await page.getByLabel('Professional profile',{exact:true}).fill('Texte CV personnel');
 await setLanguage('fr');assert.equal(await page.getByLabel('Profil professionnel',{exact:true}).inputValue(),'Texte CV personnel');await setLanguage('en');
 await nav('Documents');await page.getByRole('heading',{name:'No documents',exact:true}).waitFor();
 await nav('Mail');await page.getByRole('heading',{name:'Connect your Gmail account'}).waitFor();
 assert((await page.locator('.mail-connection').innerText()).includes('Enable the Gmail API'));
 await nav('Monitoring & check-ups');await page.getByRole('heading',{name:'Choose your schedule'}).waitFor();
 await page.getByRole('tab',{name:'Scheduled tasks'}).click();await page.getByRole('heading',{name:'Next automatic run'}).waitFor();
 await page.getByRole('tab',{name:'Logs'}).click();await page.getByRole('heading',{name:'Run history'}).waitFor();
 await nav('Connections');await page.getByRole('heading',{name:'AI provider'}).waitFor();
 await page.getByText('1,234',{exact:true}).first().waitFor();
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});await page.waitForTimeout(200);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'Viewport overflow at '+width);
  await setLanguage('fr');await setLanguage('en');
 }
 const guide=await page.request.get(base+'/guide-en.html');assert.equal(guide.status(),200);assert((await guide.text()).includes('lang="en"'));
 const other=await browser.newContext({locale:'en-US'});const auto=await other.newPage();
 await auto.route('**/api/**',route=>route.fulfill({status:503,json:{}}));await auto.goto(base);
 assert.equal(await auto.locator('html').getAttribute('lang'),'en');await other.close();
 assert.deepEqual(errors,[]);
 console.log('PASS: FR/EN setup, provider errors, language persistence, drafts, unchanged business IDs, every workspace view, guide, formatting and mobile. All API writes mocked.');
}finally{await browser.close();}
