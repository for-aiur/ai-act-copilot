import ast

from aiact.rag.benchmark import fixture_cases


def test_ten_local_demo_samples_have_code_and_clear_label_provenance():
    version, cases = fixture_cases("ai-act", "snapshot-test", "release-test")

    assert version == "sample-set-2"
    assert len(cases) == 10
    assert len({case.request.scenario for case in cases}) == 10
    for case in cases:
        assert case.code_fixture is not None
        assert case.code_fixture.text.strip()
        assert case.code_fixture.filename.endswith(".py")
        assert len(case.code_fixture.text.encode("utf-8")) <= 24_000
        ast.parse(case.code_fixture.text, filename=case.code_fixture.filename)
        assert any(label.label == "must_retrieve" for label in case.labels)

    workspace_accepted = [case for case in cases if case.id in {
        "prohibited-practices-1", "classification-1", "data-governance-1",
        "transparency-1", "general-purpose-1",
    }]
    synthetic_smoke = [case for case in cases if case.id not in {c.id for c in workspace_accepted}]
    assert len(workspace_accepted) == 5
    assert all(case.status == "approved" for case in workspace_accepted)
    assert all(case.approved_by == "Workspace owner (approved in chat)" for case in workspace_accepted)
    assert len(synthetic_smoke) == 5
    assert all(case.status == "draft" and case.approved_by is None for case in synthetic_smoke)
