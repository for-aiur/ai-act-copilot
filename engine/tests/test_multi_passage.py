"""Cross-topic selection and validation; no live model responses are simulated as evidence."""
import copy
import json
from pathlib import Path
import pytest
from aiact.corpus import load_corpus
from aiact.pipeline import scan
from aiact.retrieval import retrieve

ROOT=Path(__file__).resolve().parents[2]
TRAINING=ROOT/'examples/recruitment/training_review.py'


class MultiTopic:
    model='test-only'
    def __init__(self, mutate=None): self.calls=0;self.mutate=mutate
    def generate_json(self,prompt,schema,timeout):
        self.calls+=1
        if self.calls==1:
            return dict(ai_use='evidenced',purpose='Recruitment training and candidate shortlisting',facts=[dict(evidence_id='E1',fact='Fits a model to historical hiring labels and predicts shortlist scores')],unknowns=['Dataset provenance','Independent evaluation','Human override process'])
        data=json.JSONDecoder().raw_decode(prompt.split('UNTRUSTED_DATA_JSON:\n')[1])[0]
        assert schema['properties']['findings']['maxItems']==4
        passages={p['section_id']:p for p in data['official_passages']}
        choices={q['id']:q for q in data['review_questions']}
        findings=[]
        for qid in ['recruitment_human_review','data_origin','oversight_override','accuracy_validation']:
            q=choices[qid];sid=q['legal_source']
            findings.append(dict(title=q['topic']+': check '+q['asks_about'],explanation='This hiring workflow warrants reviewing '+q['asks_about']+'; role and applicability remain unknown.',kind='context_question',priority='medium',evidence_id='E1',citations=[dict(section_id=sid,quote=passages[sid]['quote_options'][0])],suggested_next_action='Inspect and document the evidence for this specific workflow.',context_question=q['question']))
        result={'findings':findings}
        if self.mutate:self.mutate(result)
        return result


def test_training_workflow_has_four_independent_grounded_questions():
    provider=MultiTopic();result=scan(TRAINING,provider)
    assert result.status=='complete',result.errors
    assert provider.calls==2 and len(result.findings)==4
    assert len({f.id for f in result.findings})==4
    assert len({f.context_question for f in result.findings})==4
    assert {c.section_id for f in result.findings for c in f.citations}=={'annex-iii-4-a','article-10-2','article-14-4','article-15-1'}
    assert result.metadata.prompt_version=='poc-6'


@pytest.mark.parametrize('mutation,code',[
    (lambda r:r['findings'].append(copy.deepcopy(r['findings'][0])),'invalid_response'),
    (lambda r:r['findings'].__setitem__(1,copy.deepcopy(r['findings'][0])),'invalid_response'),
    (lambda r:r['findings'][1]['citations'][0].update(section_id='annex-iii-4-a'),'citation_invalid'),
    (lambda r:r['findings'][1]['citations'][0].update(quote='Invented legal text unsupported by the source'),'citation_invalid'),
])
def test_bad_multi_topic_results_fail_explicitly(mutation,code):
    result=scan(TRAINING,MultiTopic(mutation))
    assert result.status=='failed' and not result.findings and result.errors[0].code==code


def test_retrieval_separates_training_from_synthetic_content_and_privacy_scope():
    corpus=load_corpus()
    ids=lambda q:{s['id'] for s in retrieve(q,corpus)}
    assert 'article-50-2' not in ids('recruitment synthetic training dataset model fit labels')
    assert 'article-4a-1' not in ids('recruitment candidate email pii deletion predict scores')
    assert 'article-4a-1' in ids('recruitment bias audit sensitive ethnicity deletion model predict')
    assert 'annex-iv-2-b' in ids('recruitment hyperparameters parameters optimise learning depth')
    assert not {'article-10-2','article-14-4'} & ids('chatbot customer reply')
    for query in [TRAINING.read_text(),(ROOT/'examples/recruitment/bias_audit.py').read_text()]:
        passages=retrieve(query,corpus)
        assert len(passages)<=6 and sum(len(p['text'].encode()) for p in passages)<=12000


def test_same_passage_different_questions_keep_distinct_ids():
    def replace(r):
        bank=json.loads((ROOT/'engine/src/aiact/data/questions.json').read_text())
        question=next(q['question'] for q in bank['questions'] if q['id']=='data_bias')
        item=copy.deepcopy(r['findings'][1]);item['context_question']=question
        r['findings'][2]=item
    result=scan(TRAINING,MultiTopic(replace))
    assert result.status=='complete',result.errors
    assert len({f.id for f in result.findings})==4


def test_unverified_training_quality_guarantee_is_rejected():
    def guarantee(r):r['findings'][1]['explanation']='This model is ethically trained.'
    result=scan(TRAINING,MultiTopic(guarantee))
    assert result.status=='failed' and result.errors[0].code=='review_unsupported'
