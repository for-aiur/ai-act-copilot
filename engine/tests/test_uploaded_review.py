import pytest
pytest.importorskip('sqlalchemy')
from aiact.rag.uploaded import collect_upload, validate_upload
from aiact.rag.review import review_python
from aiact.rag.releases import build_release, compatibility
from aiact.rag.retriever import HybridRetriever
from aiact.settings import Settings
from test_full_review import FixtureProvider


def test_explicit_python_upload_does_not_require_git(tmp_path,monkeypatch):
    import aiact.context as context_module

    source=tmp_path/'sample.py'
    source.write_text('def review(model):\n    return model.generate("sample")\n')

    def missing_git(*args,**kwargs):
        raise FileNotFoundError('git is not installed')

    monkeypatch.setattr(context_module.subprocess,'run',missing_git)
    collected=collect_upload(source)

    assert [item.path for item in collected.sources]==['sample.py']
    assert collected.coverage.scanned_files==['sample.py']

@pytest.mark.parametrize('extension', ['ts','js','java','go','rs','txt'])
def test_selected_script_has_exact_line_evidence(tmp_path,extension):
    source=tmp_path/('chat.'+extension)
    source.write_text('const answer = model.generate(message);\nreturn answer;\n')
    context=collect_upload(source)
    assert context.coverage.supported_languages==[extension]
    assert context.sources[0].text==source.read_text()
    assert context.sources[0].ranges==[(1,1),(2,2)]
    assert context.sources[0].potential_model_calls

@pytest.mark.parametrize('name,body', [('archive.zip','hello'),('../x.py','x=1'),('.env','KEY=value'),('x.ts','x\x00y'),('x.js','x'*24001)])
def test_unsupported_upload_is_rejected_before_inference(name,body):
    with pytest.raises(ValueError):validate_upload(name,body)

def test_non_python_review_reuses_grounded_validation(tmp_path):
    settings=Settings(data_dir=tmp_path,database_url='sqlite:///'+str(tmp_path/'db.sqlite'))
    manifest=build_release(settings,lexical_only=True)
    retriever=HybridRetriever(settings,manifest['rag_release_id'])
    source=tmp_path/'chat.ts';source.write_text('const answer = model.generate(message);\nreturn answer;\n')
    result=review_python(source,FixtureProvider(),retriever,uploaded=True)
    assert result['scan_result']['status']=='complete'
    evidence=result['scan_result']['findings'][0]['evidence']
    assert evidence['path']=='chat.ts' and evidence['quote']==source.read_text().splitlines()[0]
    retriever.close()

def test_compatibility_checks_search_code_not_bookkeeping(tmp_path):
    settings=Settings(data_dir=tmp_path,database_url='sqlite:///'+str(tmp_path/'db.sqlite'))
    manifest=build_release(settings,lexical_only=True)
    changed=manifest|{'implementation':manifest['implementation']|{'store.py':'old','evaluation.py':'old'}}
    assert compatibility(changed)['compatible']
    changed['implementation']['retriever.py']='old'
    assert not compatibility(changed)['compatible']


def test_saved_code_fixture_preserves_source_and_rejects_oversize():
    from aiact.rag.contracts import CodeFixture
    fixture=CodeFixture(filename='full script.ts',text='const answer = model.generate(message);')
    assert fixture.text.startswith('const')
    with pytest.raises(ValueError):CodeFixture(filename='secret.pem',text='secret')
    with pytest.raises(ValueError):CodeFixture(filename='script.ts',text='é'*13000)


def test_upload_and_context_share_byte_budget():
    with pytest.raises(ValueError,match='24 KB'):
        validate_upload('script.js','x'*23000,'y'*1001)

def test_upload_api_and_case_roundtrip_without_live_model(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from aiact.workbench.api import create_app
    from aiact.rag.store import Store
    import aiact.gemini
    settings=Settings(data_dir=tmp_path,database_url='sqlite:///'+str(tmp_path/'db.sqlite'),gemini_api_key='test-only-key')
    manifest=build_release(settings,lexical_only=True)
    store=Store(settings.database_url.get_secret_value());store.activate('ai-act',manifest['rag_release_id']);store.close()
    monkeypatch.setattr(aiact.gemini,'Gemini',lambda *a,**k:FixtureProvider())
    source='const answer = model.generate(message);\nreturn answer;\n'
    with TestClient(create_app(tmp_path/'legacy.db',settings=settings)) as client:
        invalid=client.post('/api/rag/review',json={'code':'x'*24000,'filename':'script.ts','context':'too much','cloud_consent':True})
        assert invalid.status_code==422
        response=client.post('/api/rag/review',json={'code':source,'filename':'full script.ts','context':'Customer chatbot','cloud_consent':True})
        assert response.status_code==200,response.text
        result=response.json()
        assert result['scan_result']['status']=='complete'
        assert result['retrieval_run_id']
        payload={'id':'uploaded-case','title':'Chatbot','author':'Local workspace','request':result['retrieval']['request'],
            'snapshot_id':result['retrieval']['snapshot_id'],'rag_release_id':manifest['rag_release_id'],
            'code_fixture':{'filename':'full script.ts','text':source}}
        assert client.post('/api/rag/cases',json=payload).status_code==201
        saved=client.get('/api/rag/cases').json()[0]
        assert saved['code_fixture']['text']==source
        assert client.get('/api/rag/runs').json()[0]['id']==result['retrieval_run_id']
