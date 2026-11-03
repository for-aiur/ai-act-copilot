import json
import pytest
pytest.importorskip("sqlalchemy")
from aiact.rag.releases import build_release, verify_bundle
from aiact.settings import Settings


def test_rebuild_is_immutable_and_mixed_artifacts_rejected(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///" + str(tmp_path / "db.sqlite"))
    first = build_release(settings, "workbench-api", lexical_only=True)
    assert first == build_release(settings, "workbench-api", lexical_only=True)
    directory = tmp_path / "releases" / first["rag_release_id"]
    manifest, snapshot, vectors = verify_bundle(directory)
    assert snapshot.domain_id == "workbench-api" and vectors == []
    assert manifest["quality_status"] == "not_evaluated"
    (directory / "snapshot.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(directory)
