const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {parseResult, fingerprint, isFresh, report} = require('../dist/core.js');
const root = path.resolve(__dirname, '../../..');
const failed = JSON.parse(fs.readFileSync(path.join(root, 'schemas/example-result.json'), 'utf8'));
const input = 'def f():\n    return model.predict(records)\n';
function complete() {
  const result = structuredClone(failed);
  result.status = 'complete'; result.errors = [];
  result.coverage.scanned_files = ['folder with spaces/x.py'];
  result.findings = [{id:'abc',title:'Potential <script> [open](command:evil)',explanation:'Review model purpose.',kind:'context_question',priority:'medium',
    evidence:{path:'folder with spaces/x.py',start_line:1,end_line:2,quote:input.trimEnd()},
    citations:[{section_id:'article-6-3',quote:'a real supporting quote',url:'https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6'}],
    suggested_next_action:'Document decision use.',context_question:'Which decisions use these predictions?'}];
  return result;
}
const target = path.join(root,'folder with spaces/x.py');

test('shared Python example parses and spaced paths are accepted', () => {
  parseResult(JSON.stringify(failed), root, target, input);
  assert.equal(parseResult(JSON.stringify(complete()),root,target,input).findings.length,1);
});
test('captured complete Python payload is consumed unchanged by the adapter', () => {
  const text=fs.readFileSync(path.join(root,'schemas/example-complete-result.json'),'utf8');
  const source=fs.readFileSync(path.join(root,'examples/recruitment/ranker.py'),'utf8');
  assert.equal(parseResult(text,root,path.join(root,'examples/recruitment/ranker.py'),source).status,'complete');
});
test('stale document version and content are discarded', () => {
  const hash = fingerprint(input);
  assert.equal(isFresh(1, hash, 1, input),true);
  assert.equal(isFresh(1, hash, 2, input),false);
  assert.equal(isFresh(1, hash, 1, input+'# change'),false);
});
test('untrusted source paths, stale quote and official URLs are rejected', () => {
  for (const mutation of [r=>r.findings[0].evidence.path='../escape.py',r=>r.findings[0].evidence.quote='invented',r=>r.findings[0].citations[0].url='command:evil',r=>r.findings[0].evidence.end_line=999]) {
    const value=complete(); mutation(value);
    assert.throws(()=>parseResult(JSON.stringify(value),root,target,input));
  }
});
test('report escapes HTML and command links while preserving deliberate source/legal links', () => {
  const value = report(complete(), line=>`file:///folder%20with%20spaces/x.py#L${line}`);
  assert.ok(value.includes('&lt;script&gt;'));
  assert.ok(!value.includes('[open](command:evil)'));
  assert.ok(value.includes('file:///folder%20with%20spaces/x.py#L1'));
  assert.ok(value.includes('https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6'));
});
test('malformed or misleading completed payload is rejected', () => {
  assert.throws(()=>parseResult('{}',root,target,input));
  const value=complete(); value.coverage.truncated=true;
  assert.throws(()=>parseResult(JSON.stringify(value),root,target,input));
});
