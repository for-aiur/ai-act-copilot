const {test}=require('node:test');
const assert=require('node:assert/strict');
const Module=require('node:module');
const {parseHealth,localHost}=require('../dist/health-core.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

function payload(running=true,model='qwen2.5:3b',modelAvailable=true,provider='ollama'){
 const ready=running&&modelAvailable;
 return {provider,schema_version:'1.0',status:ready?'ready':'unavailable',engine_version:'0.1.0',python_version:'3.12',endpoint:provider==='gemini'?'https://generativelanguage.googleapis.com':'http://127.0.0.1:11434',model_id:model,
  checks:[{id:'engine',status:'ready',detail:'Engine installed'},{id:provider,status:running?'ready':'unavailable',detail:running?'Service running':'Service stopped'},
  {id:'model',status:!running?'unknown':modelAvailable?'ready':'unavailable',detail:model},{id:'corpus',status:'ready',detail:'Reviewed subset · 6 passages'}],
  errors:ready?[]:[{code:'model_unavailable',message:'Service or model unavailable',path:null}]};
}
function setup({trusted=true,running=false,endpoint='http://127.0.0.1:11434',choice,modelAvailable=true,autoReply=true,launchThrows=false,ollamaExecutable='ollama',provider='ollama',secret='test-only-secret',consent=false,keyInput='entered-test-key',storeFails=false}={}){
 const root='/tmp/Project with spaces $(never-executed)';
 const state={running,model:'qwen2.5:3b',provider,geminiModel:'gemini-3.1-flash-lite'};
 const saved=new Map(secret?[['aiact.geminiApiKey',secret]]:[]),workspaceValues=new Map([['aiact.geminiConsent',consent]]),inputs=[];
 const processes=[],terminals=[],commands=new Map(),prompts=[],listeners={},errors=[],opened=[];
 const disposable={dispose(){}};
 const view={message:'',description:'',onDidChangeVisibility:fn=>{listeners.visible=fn;return disposable;},dispose(){}};
 const workspace={isTrusted:trusted,workspaceFolders:[{name:'Example',uri:{fsPath:root}}],
  getWorkspaceFolder:()=>workspace.workspaceFolders[0],getConfiguration:()=>({update:async(key,value)=>{state[key]=value;},get:(key,fallback)=>({provider:state.provider,geminiModel:state.geminiModel,executable:'${workspaceFolder}/.venv/bin/aiact',endpoint,model:state.model,ollamaExecutable}[key]??fallback)}),
  onDidChangeConfiguration:fn=>{listeners.config=fn;return disposable;}};
 const vscode={workspace,ConfigurationTarget:{Workspace:2},Uri:{joinPath:(base,filename)=>({fsPath:base.fsPath+'/'+filename,with(options){return {...this,...options};}})},TreeItem:class{constructor(label){this.label=label;}},ThemeIcon:class{constructor(id){this.id=id;}},
  EventEmitter:class{event=()=>disposable;fire(){}dispose(){}},
  window:{terminals,createTreeView:()=>view,createTerminal:options=>{state.running=true;const t={...options,exitStatus:undefined,show(){}};terminals.push(t);return t;},
    onDidCloseTerminal:fn=>{listeners.close=fn;return disposable;},
    showInputBox:async options=>{inputs.push(options);return keyInput === null ? undefined : keyInput;},
    showWarningMessage:async(...args)=>{prompts.push(args);return choice;},showErrorMessage:message=>errors.push(message)},
  commands:{registerCommand:(key,fn)=>{commands.set(key,fn);return disposable;},executeCommand:async(...args)=>{opened.push(args);}}};
 const original=Module._load;
 Module._load=function(name,...args){
  if(name==='vscode')return vscode;
  if(name==='node:fs')return {existsSync:file=>file.endsWith('start-local-model.sh')};
  if(name==='node:child_process')return {execFile:(executable,args,options,callback)=>{
    if(launchThrows)throw new TypeError('Invalid executable configuration');
    const entry={executable,args,options,callback,kill(){}};processes.push(entry);
    if(autoReply)setImmediate(()=>callback(null,JSON.stringify(payload(state.provider==='gemini'?!!options.env.GEMINI_API_KEY:state.running,args[3],modelAvailable,state.provider))));return entry;
  }};
  return original.call(this,name,...args);
 };
 const file=require.resolve('../dist/health.js');delete require.cache[file];
 let panel;
 try{const {HealthPanel}=require(file);panel=new HealthPanel({subscriptions:[],extensionUri:{fsPath:'/tmp/installed-extension'},secrets:{get:async key=>saved.get(key),store:async(key,value)=>{if(storeFails)throw new Error(value);saved.set(key,value);},delete:async key=>saved.delete(key)},workspaceState:{get:(key,fallback)=>workspaceValues.has(key)?workspaceValues.get(key):fallback,update:async(key,value)=>workspaceValues.set(key,value)}});}finally{Module._load=original;}
 return {panel,state,processes,terminals,commands,prompts,listeners,view,errors,root,opened,saved,workspaceValues,inputs};
}

test('health parser rejects false readiness, duplicate checks and remote endpoints',()=>{
 assert.equal(parseHealth(JSON.stringify(payload())).status,'ready');
 const bad=payload();bad.checks[1].status='unavailable';assert.throws(()=>parseHealth(JSON.stringify(bad)));
 const dup=payload();dup.checks[1].id='engine';assert.throws(()=>parseHealth(JSON.stringify(dup)));
 for(const value of ['https://remote.test','http://localhost@remote.test','http://127.0.0.1/api','http://192.168.1.5:11434'])assert.throws(()=>localHost(value));
 assert.equal(localHost('http://localhost:11435'),'127.0.0.1:11435');
});
test('activation only checks health; corpus remains visible when Ollama is stopped',async()=>{
 const s=setup();await tick();await tick();
 assert.equal(s.terminals.length,0);assert.equal(s.processes.length,1);
 assert.equal(s.processes[0].args[0],'doctor');assert.equal(s.processes[0].options.shell,false);
 const rows=s.panel.getChildren();assert.ok(rows.find(r=>r.label==='Legal corpus').description.startsWith('Available'));
 assert.ok(rows.find(r=>r.label==='Ollama').description.startsWith('Unavailable'));
});
test('introduction and final roadmap open packaged local docs without starting a service or scan',async()=>{
 const s=setup();await tick();await tick();const before=s.processes.length;
 await s.commands.get('aiact.showIntroduction')();await s.commands.get('aiact.showRoadmap')();
 assert.equal(s.opened[0][0],'markdown.showPreviewToSide');
 assert.equal(s.opened[0][1].fsPath,'/tmp/installed-extension/readme.md');
 assert.equal(s.opened[1][1].fragment,'planned-next-steps');
 assert.equal(s.processes.length,before);assert.equal(s.terminals.length,0);
 assert.equal(s.panel.getChildren()[0].command.command,'aiact.showIntroduction');
});
test('invalid executable configuration is shown without an unhandled rejection or service start',async()=>{
 const s=setup({launchThrows:true});await tick();await tick();
 s.panel.getChildren();assert.ok(s.view.message.includes('CLI health check'));
 assert.equal(await s.panel.start(),false);assert.equal(s.terminals.length,0);
});
test('untrusted workspace never checks or starts executables',async()=>{
 const s=setup({trusted:false});assert.equal(await s.panel.start(),false);await tick();
 assert.equal(s.processes.length,0);assert.equal(s.terminals.length,0);
});
test('on-save unavailable setup never prompts or starts a service',async()=>{
 const s=setup();assert.equal(await s.panel.ensureReady({fsPath:s.root},true),false);
 assert.equal(s.prompts.length,0);assert.equal(s.terminals.length,0);
});
test('manual first review can start one integrated terminal using argument arrays',async()=>{
 const s=setup({choice:'Start local service'});
 const first=s.panel.ensureReady({fsPath:s.root},false);
 await tick();await tick();
 const second=s.panel.start();
 assert.equal(await first,true);assert.equal(await second,true);
 assert.equal(s.terminals.length,1);
 assert.equal(s.terminals[0].shellPath,'/bin/sh');
 assert.deepEqual(s.terminals[0].shellArgs,[s.root+'/scripts/start-local-model.sh','ollama']);
 assert.equal(s.terminals[0].env.OLLAMA_NO_CLOUD,'1');
 assert.equal(s.terminals[0].env.OLLAMA_HOST,'127.0.0.1:11434');
 assert.ok(s.view.message!==undefined);
});
test('running Ollama with a missing model is not solved by spawning duplicates',async()=>{
 const s=setup({running:true,modelAvailable:false});assert.equal(await s.panel.start(),false);
 assert.equal(s.terminals.length,0);assert.ok(s.panel.getChildren().find(r=>r.label==='Model').description.startsWith('Unavailable'));
});
test('explicit Ollama path and custom loopback port reach the helper unchanged',async()=>{
 const binary='/Applications/Local Models/Ollama binary';
 const s=setup({ollamaExecutable:binary,endpoint:'http://127.0.0.1:11435'});
 assert.equal(await s.panel.start(),true);
 assert.deepEqual(s.terminals[0].shellArgs,[s.root+'/scripts/start-local-model.sh',binary]);
 assert.equal(s.terminals[0].env.OLLAMA_HOST,'127.0.0.1:11435');
});
test('changed model configuration discards stale health responses',async()=>{
 const s=setup({running:true,autoReply:false});
 s.state.model='another-local-tag';const next=s.panel.refresh();
 assert.equal(s.processes.length,2);
 s.processes[1].callback(null,JSON.stringify(payload(true,'another-local-tag')));await next;
 s.processes[0].callback(null,JSON.stringify(payload(true,'qwen2.5:3b')));await tick();
 assert.ok(s.panel.getChildren().find(r=>r.label==='Model').description.includes('another-local-tag'));
});

test('Gemini health uses its fixed API endpoint, secure key and no Ollama terminal',async()=>{
 const s=setup({provider:'gemini',consent:true});await tick();await tick();
 assert.equal(await s.panel.ensureReady({fsPath:s.root},false),true);
 assert.ok(s.panel.getChildren().some(r=>r.label==='Gemini API'));
 assert.ok(!s.panel.getChildren().some(r=>r.command?.command==='aiact.startLocalService'));
 const p=s.processes[0];assert.equal(p.options.env.GEMINI_API_KEY,'test-only-secret');
 assert.ok(!p.args.join(' ').includes('test-only-secret'));
 assert.equal(await s.panel.start(),false);assert.equal(s.terminals.length,0);
 const bad=payload(true,'gemini-3.1-flash-lite',true,'gemini');bad.endpoint='https://evil.test';assert.throws(()=>parseHealth(JSON.stringify(bad)));
});
test('cloud on-save requires prior workspace consent and never prompts',async()=>{
 const s=setup({provider:'gemini'});await tick();await tick();
 assert.equal(await s.panel.ensureReady({fsPath:s.root},true),false);
 assert.equal(s.prompts.length,0);assert.equal(s.terminals.length,0);
});
test('manual cloud review can be declined without running inference',async()=>{
 const s=setup({provider:'gemini',choice:undefined});await tick();await tick();
 assert.equal(await s.panel.ensureReady({fsPath:s.root},false),false);
 assert.equal(s.workspaceValues.get('aiact.geminiConsent'),false);
 assert.equal(s.terminals.length,0);
});
test('Configure Gemini masks/stores the key and selects provider only after consent',async()=>{
 const s=setup({choice:'Use Gemini'});await tick();await tick();
 await s.commands.get('aiact.configureGemini')();
 assert.equal(s.inputs[0].password,true);assert.equal(s.saved.get('aiact.geminiApiKey'),'entered-test-key');
 assert.equal(s.state.provider,'gemini');assert.equal(s.workspaceValues.get('aiact.geminiConsent'),true);
 assert.equal(s.terminals.length,0);assert.ok(!s.view.message.includes('entered-test-key'));
 await s.commands.get('aiact.removeGeminiKey')();
 assert.equal(s.saved.has('aiact.geminiApiKey'),false);assert.equal(s.workspaceValues.get('aiact.geminiConsent'),false);
});
test('key entry cancellation and untrusted workspace never save a cloud key',async()=>{
 const s=setup({keyInput:null});await tick();await tick();
 await s.commands.get('aiact.configureGemini')();
 assert.equal(s.inputs.length,1);assert.equal(s.state.provider,'ollama');
 assert.equal(s.saved.get('aiact.geminiApiKey'),'test-only-secret');assert.equal(s.prompts.length,0);
 const u=setup({trusted:false});await u.commands.get('aiact.configureGemini')();
 assert.equal(u.inputs.length,0);assert.equal(u.processes.length,0);assert.equal(u.state.provider,'ollama');
});
test('secure storage failures never expose the entered key',async()=>{
 const s=setup({choice:'Use Gemini',storeFails:true});await tick();await tick();
 await s.commands.get('aiact.configureGemini')();
 assert.equal(s.state.provider,'ollama');assert.ok(s.errors.length);assert.ok(!s.errors.join(' ').includes('entered-test-key'));
});
