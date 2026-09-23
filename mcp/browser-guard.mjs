import {reserve,publicPage} from './guard.mjs';

// Browser traffic uses CDP, not Axios: count every tool before execution.
export function installBrowserGuard(tools,Session,{charge=name=>reserve(process.env.SEARCHMYJOB_BRIGHT_BUDGET,name),ttl=120000}={}){
    const browsers=new Map(),pages=new WeakSet();
    const close=async browser=>{
        clearTimeout(browsers.get(browser));browsers.delete(browser);
        await browser.close().catch(()=>{});
    };
    const getBrowser=Session.prototype.get_browser;
    Session.prototype.get_browser=async function(...args){
        const browser=await getBrowser.apply(this,args);
        if(!browsers.has(browser)){
            const timer=setTimeout(()=>void close(browser),ttl);timer.unref();
            browsers.set(browser,timer);
        }
        return browser;
    };
    const getPage=Session.prototype.get_page;
    Session.prototype.get_page=async function(...args){
        const page=await getPage.apply(this,args);
        if(!pages.has(page)){
            await page.route('**/*',route=>{
                const req=route.request();
                return req.isNavigationRequest()&&!publicPage(req.url())?route.abort():route.continue();
            });
            pages.add(page);
        }
        return page;
    };
    for(const tool of tools){
        const execute=tool.execute;
        tool.execute=async function(args,...rest){
            if(args?.url&&!publicPage(args.url))throw Error('Navigation publique HTTPS requise');
            try{charge(tool.name);}
            catch(error){await Promise.all([...browsers.keys()].map(close));throw error;}
            return execute.call(this,args,...rest);
        };
    }
    const cleanup=()=>Promise.all([...browsers.keys()].map(close));
    process.stdin.once('end',cleanup);
    for(const signal of ['SIGTERM','SIGINT'])process.once(signal,()=>void cleanup().finally(()=>process.exit(0)));
    return cleanup;
}
