import {useState} from 'react'
import {ExternalLink,LoaderCircle,Play,ShieldCheck} from 'lucide-react'
import {request} from './api'
import type {Versions} from './rag'
import type {ScanResult} from '../../extensions/vscode/src/contracts'

type Review = {id:string;scan_result:ScanResult;rag_release_id:string;trace_id:string;trace_url:string|null;steps:{stage:string;elapsed_ms:number;status:string}[]}

export default function ReviewPanel({versions,context}:{versions:Versions|null;context:string}){
 const [code,setCode]=useState('def rank_applicants(model, candidates):\n    return model.predict(candidates)\n')
 const [consent,setConsent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const [result,setResult]=useState<Review|null>(null)
 const cloud=versions?.provider==='gemini'
 async function review(){
  setBusy(true);setError('');setResult(null)
  try{setResult(await request<Review>('/api/rag/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,filename:'review.py',context,cloud_consent:consent})}))}
  catch(e){setError(e instanceof Error?e.message:'Review unavailable.')}
  finally{setBusy(false)}
 }
 return <section className="annotation-panel"><div className="section-header"><div><h2>Grounded Python review <span>Optional inference</span></h2><p>{cloud?'Gemini receives the selected code, context and retrieved official passages.':'Ollama runs locally without a cloud fallback.'}</p></div><span className="draft-pill">{versions?.model||'PROVIDER SETUP'}</span></div><div className="review-input"><label>Python source<textarea aria-label="Python source" value={code} onChange={e=>{setCode(e.target.value);setResult(null)}} spellCheck={false} maxLength={24000} rows={8}/></label><p>The initial snippet is synthetic. Scanned code is never executed. Saving a review retains its evidence and result locally.</p>{cloud&&<label className="cloud-consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I allow this code and the current scenario context to be sent to Google for this review.</label>}{cloud&&!versions?.cloud_key_configured&&<div className="trace-note">Set GEMINI_API_KEY in the private .env file and restart the API. Do not paste keys into this page.</div>}<button className="primary" disabled={busy||!code.trim()||!versions?.active||(cloud&&(!consent||!versions.cloud_key_configured))} onClick={()=>void review()}>{busy?<LoaderCircle size={16} className="spin"/>:<Play size={16}/>}Review & save result locally</button></div>{error&&<div className="alert error" role="alert">{error}</div>}{result&&<div className="review-output"><h3>Review {result.scan_result.status}</h3><p className="trace-note">RAG {result.rag_release_id.slice(0,12)} · {result.scan_result.metadata.elapsed_ms} ms · Zero findings does not certify compliance.</p>{result.scan_result.errors.map((e,i)=><div className="alert error" key={i}>{e.code}: {e.message}</div>)}{result.scan_result.findings.map(f=><article className="review-finding" key={f.id}><span className="draft-pill">{f.kind==='context_question'?'NEEDS CONTEXT':'POTENTIAL CONCERN'} · {f.priority}</span><h3>{f.title}</h3><p>{f.explanation}</p><pre>{f.evidence.path}:{f.evidence.start_line}-{f.evidence.end_line}{'\n'}{f.evidence.quote}</pre>{f.citations.map(c=><blockquote key={c.section_id+c.quote}><p>{c.quote}</p><a href={c.url} target="_blank" rel="noreferrer">{c.section_id}<ExternalLink size={12}/></a></blockquote>)}<p><strong>Next action:</strong> {f.suggested_next_action}</p><p className="context-question">{f.context_question}</p></article>)}<div className="stage-strip">{result.steps.map((s,i)=><span key={i}>{s.stage}: {s.elapsed_ms} ms · {s.status}</span>)}</div>{result.trace_url&&<a className="official-link" href={result.trace_url} target="_blank" rel="noreferrer"><ShieldCheck size={14}/>Open metadata-only Langfuse trace<ExternalLink size={13}/></a>}</div>}</section>
}
