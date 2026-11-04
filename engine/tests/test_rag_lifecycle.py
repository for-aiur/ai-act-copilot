import json
import pytest
pytest.importorskip('sqlalchemy')
from aiact.settings import Settings
from aiact.rag.releases import build_release, verify_bundle, release_identity
from aiact.rag.store import Store
from aiact.workbench.api import create_app
from fastapi.testclient import TestClient


def test_git_only_change_reuses_immutable_candidate(tmp_path, monkeypatch):
    settings=Settings(data_dir=tmp_path,database_url='sqlite:///'+str(tmp_path/'db.sqlite'))
    import aiact.rag.releases as module
    class Result:
        stdout='commit-one'
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:Result())
    first=build_release(settings,'workbench-api',lexical_only=True)
    Result.stdout='commit-two'
    second=build_release(settings,'workbench-api',lexical_only=True)
    assert first==second
    assert len(list((tmp_path/'releases').iterdir()))==1
    assert verify_bundle(tmp_path/'releases'/first['rag_release_id'])[0]==first
    changed=first|{'embedding':first['embedding']|{'model':'another-model'}}
    assert release_identity(changed)!=first['rag_release_id']


def test_remove_protects_active_and_every_saved_revision(tmp_path):
    settings=Settings(data_dir=tmp_path,database_url='sqlite:///'+str(tmp_path/'db.sqlite'))
    manifest=build_release(settings,'workbench-api',lexical_only=True)
    identity=manifest['rag_release_id'];store=Store(settings.database_url.get_secret_value())
    store.activate('workbench-api',identity)
    with pytest.raises(ValueError,match='Active RAG'):store.remove_release(identity,'workbench-api')
    store.put_release(manifest|{'rag_release_id':'other'})
    store.activate('workbench-api','other')
    store.append('case','old-case','workbench-api',{'rag_release_id':identity},1)
    store.append('case','old-case','workbench-api',{'rag_release_id':'other'},2)
    with pytest.raises(ValueError,match='saved case'):store.remove_release(identity,'workbench-api')
    store.close()


def test_api_removes_only_unused_candidate_and_rebuild_restores(tmp_path):
    settings=Settings(data_dir=tmp_path,database_url='sqlite:///'+str(tmp_path/'db.sqlite'))
    manifest=build_release(settings,'workbench-api',lexical_only=True);identity=manifest['rag_release_id']
    with TestClient(create_app(tmp_path/'legacy.db',settings=settings)) as client:
        base='/api/rag/versions/'+identity
        assert client.delete(base,params={'domain':'ai-act'}).status_code==409
        assert client.delete(base,params={'domain':'workbench-api'}).status_code==200
        assert client.get('/api/rag/versions',params={'domain':'workbench-api'}).json()['releases']==[]
        assert client.post('/api/rag/activate/'+identity,params={'domain':'workbench-api'}).status_code==422
        assert build_release(settings,'workbench-api',lexical_only=True)==manifest
        assert len(client.get('/api/rag/versions',params={'domain':'workbench-api'}).json()['releases'])==1
        assert client.post('/api/rag/activate/'+identity,params={'domain':'workbench-api'}).status_code==200
        blocked=client.delete(base,params={'domain':'workbench-api'})
        assert blocked.status_code==409 and 'Active RAG' in blocked.json()['detail']


def test_legacy_manifest_stays_readable(tmp_path):
    import shutil
    from aiact.rag.official import checksum
    settings=Settings(data_dir=tmp_path,database_url='sqlite:///'+str(tmp_path/'db.sqlite'))
    current=build_release(settings,'workbench-api',lexical_only=True)
    legacy={k:v for k,v in current.items() if k!='rag_release_id'}
    legacy['schema_version']='1'
    legacy['rag_release_id']=checksum(legacy)
    directory=tmp_path/'releases'/legacy['rag_release_id']
    shutil.copytree(tmp_path/'releases'/current['rag_release_id'],directory)
    (directory/'manifest.json').write_text(json.dumps(legacy))
    assert verify_bundle(directory)[0]==legacy
