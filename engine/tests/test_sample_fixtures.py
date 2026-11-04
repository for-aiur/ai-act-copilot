import ast

from aiact.rag.benchmark import fixture_cases


def test_all_five_seeded_ai_act_samples_open_with_approved_labels_and_runnable_code():
    version, cases = fixture_cases("ai-act", "snapshot-test", "release-test")

    assert version == "sample-set-1"
    assert len(cases) == 5
    assert len({case.request.scenario for case in cases}) == 5
    for case in cases:
        assert case.status == "approved"
        assert case.approved_by == "Workspace owner (approved in chat)"
        assert case.code_fixture is not None
        assert case.code_fixture.text.strip()
        assert case.code_fixture.filename.endswith(".py")
        assert len(case.code_fixture.text.encode("utf-8")) <= 24_000
        ast.parse(case.code_fixture.text, filename=case.code_fixture.filename)
        assert any(label.label == "must_retrieve" for label in case.labels)
