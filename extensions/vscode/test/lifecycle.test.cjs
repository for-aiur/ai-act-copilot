const {test}=require('node:test');
const assert=require('node:assert/strict');
const Module=require('node:module');
const path=require('node:path');

function setup(trusted=true,corpusPath='',cloud=false) {
  const root=path.resolve(__dirname,'../../..');
  const uri={fsPath:path.join(root,'folder with spaces/x.py'),scheme:'file',toString(){return 'file://'+this.fsPath;},with(){return this;}};
  const document={uri,languageId:'python',isDirty:false,isClosed:false,version:1,getText:()=> 'def f():\n    return model.predict(records)\n',lineAt:()=>({text:'    return model.predict(records)'})};
  const commands=new Map(), listeners={}, processes=[], sets=[], statuses=[];
  const disposable={dispose(){}};
  const workspace={isTrusted:trusted,getWorkspaceFolder:()=>({uri:{fsPath:root}}),getConfiguration:()=>({get:(key,fallback)=>key==='executable'?'${workspaceFolder}/.venv/bin/aiact':key==='corpusPath'?corpusPath:key==='provider'?(cloud?'gemini':'ollama'):fallback}),
    registerTextDocumentContentProvider:()=>disposable,openTextDocument:async()=>document,
    onDidChangeConfiguration:fn=>{listeners.config=fn;return disposable;},
    onDidChangeTextDocument:fn=>{listeners.change=fn;return disposable;},onDidSaveTextDocument:fn=>{listeners.save=fn;return disposable;}};
  const vscode={workspace,StatusBarAlignment:{Right:1},ProgressLocation:{Notification:1},DiagnosticSeverity:{Information:1,Warning:2},
    EventEmitter:class{event=()=>disposable;fire(){}dispose(){}},Uri:{parse:()=>({})},
    Range:class{constructor(...args){this.start=args.slice(0,2);this.end=args.slice(2);}},
    Diagnostic:class{constructor(range,message,severity){Object.assign(this,{range,message,severity});}},
    languages:{createDiagnosticCollection:()=>({delete(){},set:(...args)=>sets.push(args),dispose(){}}),registerHoverProvider:()=>disposable},
    window:{activeTextEditor:{document},createStatusBarItem:()=>({set text(value){statuses.push(value);},show(){},dispose(){}}),
      showInformationMessage(){},showWarningMessage(){},showErrorMessage(){},
      withProgress:async(_options,fn)=>fn({}, {onCancellationRequested:()=>disposable})},
    commands:{registerCommand:(key,fn)=>{commands.set(key,fn);return disposable;},executeCommand:async()=>{}}};
  const original=Module._load;
  Module._load=function(name,...args){
    if(name==='vscode')return vscode;
    if(name==='./health')return {HealthPanel:class{async ensureReady(){return true;}async refresh(){}}};
    if(name==='node:child_process')return {execFile:(executable,args,options,callback)=>{const p={executable,args,options,callback,kill(){}};processes.push(p);return p;}};
    return original.call(this,name,...args);
  };
  const modulePath=require.resolve('../dist/extension.js');delete require.cache[modulePath];
  try{require(modulePath).activate({subscriptions:[],secrets:{get:async()=> 'test-only-secret'},workspaceState:{get:()=>true}});}finally{Module._load=original;}
  return {root,document,commands,listeners,processes,sets,statuses};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('untrusted workspaces never execute the CLI',async()=>{
  const s=setup(false);await s.commands.get('aiact.review')();assert.equal(s.processes.length,0);
});
test('one active process, argument arrays for spaced paths, stale result discarded',async()=>{
  const s=setup();const pending=s.commands.get('aiact.review')();await tick();
  assert.equal(s.processes.length,1);
  const p=s.processes[0];assert.equal(p.options.shell,false);assert.equal(p.args[1],s.document.uri.fsPath);assert.equal(p.executable,path.join(s.root,'.venv/bin/aiact'));
  await s.commands.get('aiact.review')();assert.equal(s.processes.length,1);
  s.document.version++;s.listeners.change({document:s.document,contentChanges:[{}]});
  p.callback(null,'{"this":"stale payload must never be parsed"}');await pending;
  assert.equal(s.sets.length,0);assert.ok(s.statuses.at(-1).includes('Needs review'));
});
test('fresh failed results remain unavailable instead of reassuring completed diagnostics',async()=>{
  const s=setup();const pending=s.commands.get('aiact.review')();await tick();
  const result=require('../../../schemas/example-result.json');
  s.processes[0].callback(null,JSON.stringify(result));await pending;
  assert.ok(s.statuses.at(-1).includes('Unavailable'));
  assert.deepEqual(s.sets[0][1],[]);
});
test('workspace corpus path is resolved consistently for scan arguments',async()=>{
 const s=setup(true,'${workspaceFolder}/legal cache/corpus.json');
 const pending=s.commands.get('aiact.review')();await tick();
 const p=s.processes[0];assert.equal(p.args[p.args.indexOf('--corpus')+1],path.join(s.root,'legal cache/corpus.json'));
 s.document.version++;p.callback(null,'stale');await pending;
});

test('Gemini scan uses secure env and provider model, never key arguments',async()=>{
 const s=setup(true,'',true);const pending=s.commands.get('aiact.review')();await tick();
 const p=s.processes[0];assert.equal(p.args[p.args.indexOf('--provider')+1],'gemini');
 assert.equal(p.args[p.args.indexOf('--model')+1],'gemini-3.1-flash-lite');
 assert.equal(p.options.env.GEMINI_API_KEY,'test-only-secret');assert.ok(!p.args.join(' ').includes('test-only-secret'));
 s.document.version++;p.callback(null,'stale');await pending;
});
test('inference settings changing during a scan discard its results',async()=>{
 const s=setup();const pending=s.commands.get('aiact.review')();await tick();
 s.listeners.config({affectsConfiguration:()=>true});
 s.processes[0].callback(null,'must not parse stale configuration');await pending;
 assert.equal(s.sets.length,0);assert.ok(s.statuses.at(-1).includes('Needs review'));
});
