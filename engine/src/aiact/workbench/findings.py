"""Tenant repository inventory and durable finding decisions."""
import json
import re
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4
from threading import Lock

from sqlalchemy import Column, MetaData, String, Table, Text, insert, select, update, inspect

metadata = MetaData()
_schema_lock = Lock()
repositories = Table("aiact_customer_repositories", metadata,
    Column("id", String, primary_key=True), Column("tenant_id", String, nullable=False, index=True),
    Column("installation_id", String, nullable=False), Column("name", String, nullable=False),
    Column("latest_review_at", String), Column("latest_review_outcome", String))
projects = Table("aiact_customer_projects", metadata,
    Column("id", String, primary_key=True), Column("tenant_id", String, nullable=False, index=True),
    Column("name", String(100), nullable=False), Column("repository_ids", Text, nullable=False))
findings = Table("aiact_customer_findings", metadata,
    Column("id", String, primary_key=True), Column("tenant_id", String, nullable=False, index=True),
    Column("repository_id", String, nullable=False), Column("pr", String, nullable=False),
    Column("head", String, nullable=False), Column("priority", String, nullable=False),
    Column("state", String, nullable=False), Column("payload", Text, nullable=False),
    Column("created_at", String, nullable=False), Column("updated_at", String, nullable=False))
fp_settings = Table("aiact_customer_fp_settings", metadata,
    Column("tenant_id", String, primary_key=True), Column("mode", String, nullable=False),
    Column("approver", String, nullable=False))
decisions = Table("aiact_customer_decisions", metadata,
    Column("id", String, primary_key=True), Column("finding_id", String, nullable=False),
    Column("actor", String, nullable=False), Column("action", String, nullable=False),
    Column("reason", Text, nullable=False), Column("category", String), Column("head", String, nullable=False),
    Column("created_at", String, nullable=False), Column("sync_status", String, nullable=False))


def finding_policies(payload):
    """Group validated citation identifiers by provision, counting each finding once."""
    groups = set()
    for citation in payload.get("citations") or []:
        section = citation.get("section_id") or ""
        match = re.match(r"^(article-[0-9]+[a-z]?|annex-[ivxlcdm]+|(?:amendment-)?recital-[0-9]+)(?:[-:#._]|$)", section.lower())
        if match:
            groups.add(match.group(1))
    return sorted(groups) or ["uncategorized"]


def policy_counts(rows):
    total, opened = Counter(), Counter()
    for row in rows:
        groups = finding_policies(row["payload"])
        total.update(groups)
        if row["state"] == "open":
            opened.update(groups)
    return [
        {"id": group, "total": count, "open": opened[group]}
        for group, count in sorted(total.items(), key=lambda item: (-item[1], item[0]))
    ]


class CustomerFindings:
    def __init__(self, engine):
        self.engine = engine
        with _schema_lock:
            metadata.create_all(engine)
            columns = {column["name"] for column in inspect(engine).get_columns(repositories.name)}
            decision_columns = {column["name"] for column in inspect(engine).get_columns(decisions.name)}
            with engine.begin() as db:
                if "category" not in decision_columns:
                    db.exec_driver_sql("ALTER TABLE aiact_customer_decisions ADD COLUMN category VARCHAR")
                if "latest_review_at" not in columns:
                    db.exec_driver_sql("ALTER TABLE aiact_customer_repositories ADD COLUMN latest_review_at VARCHAR")
                if "latest_review_outcome" not in columns:
                    db.exec_driver_sql("ALTER TABLE aiact_customer_repositories ADD COLUMN latest_review_outcome VARCHAR")

    def bind(self, tenant_id, repository_id, installation_id, name):
        """Called only by trusted installation setup, never from public input."""
        with self.engine.begin() as db:
            old = db.execute(select(repositories).where(repositories.c.id == str(repository_id))).mappings().first()
            values = dict(id=str(repository_id), tenant_id=tenant_id,
                installation_id=str(installation_id), name=name)
            if old:
                if old["tenant_id"] != tenant_id or old["installation_id"] != str(installation_id):
                    raise ValueError("Repository already belongs to another installation.")
                db.execute(update(repositories).where(repositories.c.id == str(repository_id)).values(name=name))
            else:
                db.execute(insert(repositories).values(**values))

    def ingest(self, installation_id, repository_id, pr, head, records):
        now = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as db:
            repo = db.execute(select(repositories).where(repositories.c.id == str(repository_id),
                repositories.c.installation_id == str(installation_id))).mappings().first()
            if not repo:
                raise ValueError("Unknown repository installation.")
            db.execute(update(repositories).where(repositories.c.id == str(repository_id)).values(
                latest_review_at=now, latest_review_outcome="complete"))
            for record in records:
                identity = f'{repository_id}:{pr}:{record["id"]}'
                old = db.execute(select(findings).where(findings.c.id == identity)).mappings().first()
                values = dict(tenant_id=repo["tenant_id"], repository_id=str(repository_id), pr=str(pr),
                    head=head, priority=record["priority"], payload=json.dumps(record),
                    updated_at=now)
                if old:
                    if old["head"] != head:
                        values["state"] = "open"
                    db.execute(update(findings).where(findings.c.id == identity).values(**values))
                else:
                    db.execute(insert(findings).values(id=identity, state="open", created_at=now, **values))

    def list(self, tenant_id):
        with self.engine.connect() as db:
            rows = db.execute(select(findings, repositories.c.name).join(repositories,
                findings.c.repository_id == repositories.c.id).where(findings.c.tenant_id == tenant_id)).mappings()
            return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    def projects(self, tenant_id):
        with self.engine.connect() as db:
            rows = db.execute(select(projects).where(projects.c.tenant_id == tenant_id)
                              .order_by(projects.c.name, projects.c.id)).mappings()
            return [{"id": row["id"], "name": row["name"],
                     "repository_ids": json.loads(row["repository_ids"])} for row in rows]

    def project_repository_ids(self, tenant_id, project_id):
        with self.engine.connect() as db:
            value = db.execute(select(projects.c.repository_ids).where(
                projects.c.tenant_id == tenant_id, projects.c.id == project_id)).scalar_one_or_none()
            return set(json.loads(value)) if value is not None else None

    def save_project(self, tenant_id, name, repository_ids, project_id=None):
        repo_ids = sorted(set(repository_ids))
        with self.engine.begin() as db:
            allowed = set(db.execute(select(repositories.c.id).where(
                repositories.c.tenant_id == tenant_id,
                repositories.c.installation_id != "local-workspace",
            )).scalars())
            if not set(repo_ids) <= allowed:
                raise ValueError("Choose repositories in this workspace.")
            values = {"name": name, "repository_ids": json.dumps(repo_ids)}
            if project_id:
                changed = db.execute(update(projects).where(
                    projects.c.id == project_id, projects.c.tenant_id == tenant_id).values(**values))
                if not changed.rowcount:
                    raise LookupError("Project not found.")
            else:
                project_id = str(uuid4())
                db.execute(insert(projects).values(id=project_id, tenant_id=tenant_id, **values))
        return {"id": project_id, "name": name, "repository_ids": repo_ids}

    def inventory(self, tenant_id):
        with self.engine.connect() as db:
            return [dict(row) for row in db.execute(select(repositories).where(
                repositories.c.tenant_id == tenant_id,
                repositories.c.installation_id != "local-workspace")).mappings()]

    def local_review_repository(self, tenant_id):
        installation = "local-workspace"
        with self.engine.connect() as db:
            legacy = db.execute(select(repositories.c.id).where(
                repositories.c.id == "local-reviews", repositories.c.tenant_id == tenant_id,
                repositories.c.installation_id == installation)).scalar_one_or_none()
        identity = legacy or f"local-reviews:{tenant_id}"
        self.bind(tenant_id, identity, installation, "Local code reviews")
        return identity, installation

    def record_review(self, tenant_id, repository_id, outcome, reviewed_at=None):
        if outcome not in {"complete", "partial", "failed"}:
            raise ValueError("Unknown review outcome.")
        with self.engine.begin() as db:
            row = db.execute(select(repositories).where(repositories.c.id == repository_id,
                repositories.c.tenant_id == tenant_id)).mappings().first()
            if not row:
                raise LookupError("Repository not found.")
            db.execute(update(repositories).where(repositories.c.id == repository_id).values(
                latest_review_at=reviewed_at or datetime.now(timezone.utc).isoformat(),
                latest_review_outcome=outcome))

    def fp_policy(self, tenant_id):
        with self.engine.connect() as db:
            row = db.execute(select(fp_settings).where(fp_settings.c.tenant_id == tenant_id)).mappings().first()
        return {"mode": row["mode"], "approver": row["approver"]} if row else {"mode": "immediate", "approver": None}

    def set_fp_policy(self, tenant_id, mode, actor):
        with self.engine.begin() as db:
            existing = db.execute(select(fp_settings).where(fp_settings.c.tenant_id == tenant_id)
                                  .with_for_update()).mappings().first()
            if existing:
                if existing["approver"] != actor:
                    raise PermissionError("Only the configured reviewer can change this setting.")
                db.execute(update(fp_settings).where(fp_settings.c.tenant_id == tenant_id).values(mode=mode))
            else:
                db.execute(insert(fp_settings).values(tenant_id=tenant_id, mode=mode, approver=actor))
        return {"mode": mode, "approver": actor}

    def fp_marks(self, tenant_id):
        with self.engine.connect() as db:
            rows = db.execute(select(decisions, findings.c.state).join(findings,
                decisions.c.finding_id == findings.c.id).where(
                findings.c.tenant_id == tenant_id, decisions.c.head == findings.c.head,
                decisions.c.action.not_in(("context", "unsure"))
            ).order_by(decisions.c.created_at, decisions.c.id)).mappings()
            marks = {}
            for row in rows:
                if row["action"] in {"false_positive", "fp_approve"} and row["state"] == "false_positive":
                    marks[row["finding_id"]] = dict(row) | {"pending": False}
                elif row["action"] == "fp_pending":
                    marks[row["finding_id"]] = dict(row) | {"pending": True}
                else:
                    marks.pop(row["finding_id"], None)
            return marks

    def legal_requests(self, tenant_id):
        with self.engine.connect() as db:
            rows = db.execute(select(decisions.c.finding_id, decisions.c.action, decisions.c.actor,
                decisions.c.reason, decisions.c.created_at).join(findings, decisions.c.finding_id == findings.c.id)
                .where(findings.c.tenant_id == tenant_id, findings.c.state == "open",
                    findings.c.head == decisions.c.head, decisions.c.action.not_in(("context", "fp_pending")))
                .order_by(decisions.c.created_at, decisions.c.id)).mappings()
            latest = {row["finding_id"]: dict(row) for row in rows}
        return {key: row for key, row in latest.items() if row["action"] == "unsure"}

    def fp_submissions(self, tenant_id):
        with self.engine.connect() as db:
            rows = db.execute(select(decisions.c.finding_id, decisions.c.head, decisions.c.category,
                decisions.c.created_at).join(findings, decisions.c.finding_id == findings.c.id).where(
                    findings.c.tenant_id == tenant_id, decisions.c.action.in_(["false_positive", "fp_pending"])
                )).mappings()
            return [dict(row) for row in rows]

    def decide(self, tenant_id, finding_id, head, action, actor, reason, event_id, category=None):
        if action not in {"acknowledged", "false_positive", "resolved", "open", "context", "fp_approve", "unsure"}:
            raise ValueError("Unknown decision.")
        if action == "resolved" and not reason.strip():
            raise ValueError("Add a reason.")
        now = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as db:
            row = db.execute(select(findings).where(findings.c.id == finding_id,
                findings.c.tenant_id == tenant_id).with_for_update()).mappings().first()
            if not row:
                raise LookupError("Finding not found.")
            if row["head"] != head:
                raise ValueError("This finding changed. Reload before deciding.")
            old = db.execute(select(decisions).where(decisions.c.id == event_id)).mappings().first()
            if old:
                requested = "false_positive" if old["action"] == "fp_pending" else old["action"]
                if (old["finding_id"], old["actor"], requested, old["head"]) != (finding_id, actor, action, head):
                    raise ValueError("Decision key already used.")
                if action != "fp_approve" and (old["reason"], old["category"]) != (reason, category):
                    raise ValueError("Decision key already used.")
                return dict(old)
            policy = db.execute(select(fp_settings).where(fp_settings.c.tenant_id == tenant_id)).mappings().first()
            if action == "unsure" and row["state"] != "open":
                raise ValueError("Reopen this finding before requesting legal review.")
            next_state = None if action == "unsure" else action
            if action in {"false_positive", "fp_approve"}:
                last = db.execute(select(decisions).where(decisions.c.finding_id == finding_id,
                    decisions.c.head == head, decisions.c.action.not_in(("context", "unsure")))
                    .order_by(decisions.c.created_at.desc(), decisions.c.id.desc()).limit(1)).mappings().first()
                pending = last if last and last["action"] == "fp_pending" else None
                if action == "fp_approve":
                    if not pending:
                        raise ValueError("No pending false-positive mark.")
                    if not policy or policy["approver"] != actor or pending["actor"] == actor:
                        raise PermissionError("A different authorized reviewer must approve this mark.")
                    next_state = "false_positive"
                    category, reason = pending["category"], pending["reason"]
                elif pending or row["state"] == "false_positive":
                    raise ValueError("This finding already has a false-positive mark.")
                elif policy and policy["mode"] == "approval":
                    action, next_state = "fp_pending", None
            payload = json.loads(row["payload"])
            sync_status = "not_required" if action == "fp_pending" or payload.get("source_type") == "local_review" else "pending"
            values = dict(id=event_id, finding_id=finding_id, actor=actor, action=action,
                reason=reason, category=category, head=head, created_at=now, sync_status=sync_status)
            db.execute(insert(decisions).values(**values))
            if next_state and next_state != "context":
                db.execute(update(findings).where(findings.c.id == finding_id).values(state=next_state, updated_at=now))
            return values

    def history(self, tenant_id, finding_id):
        if not any(row["id"] == finding_id for row in self.list(tenant_id)):
            raise LookupError("Finding not found.")
        with self.engine.connect() as db:
            return [dict(row) for row in db.execute(select(decisions).where(
                decisions.c.finding_id == finding_id).order_by(decisions.c.created_at)).mappings()]

    def sync(self, tenant_id, event_id, client):
        """Retry a persisted decision using an installation-authenticated GitHub client."""
        with self.engine.begin() as db:
            row = db.execute(select(decisions, findings.c.repository_id, findings.c.pr,
                repositories.c.name).join(findings, decisions.c.finding_id == findings.c.id)
                .join(repositories, findings.c.repository_id == repositories.c.id)
                .where(decisions.c.id == event_id, findings.c.tenant_id == tenant_id)
                .with_for_update()).mappings().first()
            if not row:
                raise LookupError("Decision not found.")
            if row["sync_status"] == "synced":
                return
            current = client.current_head(row["name"], int(row["pr"]))
            if current != row["head"]:
                raise ValueError("Pull request changed before synchronization.")
            client.apply_decision(dict(row), idempotency_key=event_id)
            db.execute(update(decisions).where(decisions.c.id == event_id).values(sync_status="synced"))


class DemoGitHub:
    """Deterministic GitHub boundary for synthetic repositories only."""
    def __init__(self, store, tenant_id):
        self.store, self.tenant_id = store, tenant_id

    def current_head(self, repo, pr):
        rows = [row for row in self.store.list(self.tenant_id) if row["name"] == repo and int(row["pr"]) == pr]
        if not rows or not all(row["repository_id"].startswith("demo-") for row in rows):
            raise ValueError("Only synthetic repositories support simulated GitHub.")
        return rows[0]["head"]

    def apply_decision(self, decision, idempotency_key):
        # The persisted decision is the local receipt. Its identity survives retries.
        if not decision["repository_id"].startswith("demo-"):
            raise ValueError("Only synthetic repositories support simulated GitHub.")


def seed_demo(store, tenant_id):
    examples = [
        ("recruitment", "Candidate ranking can affect hiring decisions", "high",
         "def rank_candidates(candidates):\n    scores = model.predict(candidates)\n    return sorted(zip(candidates, scores), key=lambda row: row[1], reverse=True)",
         "scores = model.predict(candidates)", "A model score affects candidate ranking. Confirm how a human reviewer can understand and override the result before it is used.",
         "Annex III 4(a) covers certain recruitment or selection systems. Check the system's intended purpose and the actual role of the score.",
         "annex-iii-4-a", "AI systems intended to be used for the recruitment or selection of natural persons"),
        ("chatbot", "Check whether users know they are speaking with AI", "medium",
         "def respond(message):\n    answer = model.generate(message)\n    return answer", "answer = model.generate(message)",
         "This function returns a generated answer directly. Check where the interface tells users that they are interacting with an AI system.",
         "Article 50(1) addresses informing people who interact directly with an AI system, subject to its stated exception.",
         "article-50-1", "AI systems intended to interact directly with natural persons"),
    ]
    citations = _demo_citations()
    variants = [
        (examples[0], 1, "feature/candidate-ranking", "synthetic-head", "open_pr", None),
        (examples[1], 1, "feature/support-assistant", "synthetic-head", "open_pr", None),
        (examples[0], 14, "experiment/batch-scoring", "a14c92e", "released", "v1.8.0"),
        (examples[1], 27, "feature/chat-preview", "b27d831", "merged", None),
        (examples[1], 31, "feature/support-widget", "c31da80", "open_pr", None),
    ]
    for example, pr, branch, head, stage, release in variants:
        repo, title, priority, code, quote, explanation, question, citation_id, _ = example
        if pr == 14:
            title = "Check human review in batch candidate scoring"
        if pr == 27:
            title, priority = "Check the AI notice in the chat preview", "low"
        if pr == 31:
            title = "Check the AI notice in the support widget"
        store.bind(tenant_id, "demo-" + repo, "demo-installation", "example/" + repo)
        store.ingest("demo-installation", "demo-" + repo, pr, head, [{
            "id": "demo-finding", "title": title, "priority": priority, "source_type": "simulated_github", "branch": branch,
            "explanation": explanation, "context_question": question,
            "code_stage": stage, "release_tag": release,
            "evidence": {"path": "src/" + repo + ".py", "start_line": 2, "end_line": 2, "quote": quote},
            "code_sample": code,
            "review_status": "complete",
            "citations": [{"section_id": citation_id, "quote": citations[citation_id], "url": citations[citation_id + "_url"]}]
                + ([{"section_id": "article-14-1", "quote": citations["article-14-1"], "url": citations["article-14-1_url"]}] if repo == "recruitment" else []),
        }])
    store.bind(tenant_id, "demo-unreviewed", "demo-installation", "example/unreviewed")


def _demo_citations():
    import json
    from importlib.resources import files
    corpus = json.loads(files("aiact").joinpath("data/corpus.json").read_text())
    result = {}
    for identity in ("annex-iii-4-a", "article-14-1", "article-50-1"):
        section = next(item for item in corpus["sections"] if item["id"] == identity)
        result[identity] = (section.get("supporting_quotes") or [section["text"]])[0]
        result[identity + "_url"] = section["url"]
    return result


def add_review_findings(store, tenant_id, job_id, session, reviewed_at):
    """Expose completed scan findings in the tenant inbox without pretending they came from GitHub."""
    repo_id, install_id = store.local_review_repository(tenant_id)
    scan = session.scan_result if session else None
    outcome = scan.status if scan and scan.status in {"complete", "partial", "failed"} else "failed"
    store.record_review(tenant_id, repo_id, outcome, reviewed_at)
    if not scan or scan.status not in {"complete", "partial"}:
        return
    records = []
    for finding in scan.findings:
        payload = finding.model_dump(mode="json")
        payload.update(source_type="local_review", source_review_id=job_id, review_status=scan.status,
            source_snapshot_id=scan.metadata.corpus_checksum, source_version=scan.metadata.corpus_version,
            model_id=scan.metadata.model_id, rag_release_id=session.rag_release_id)
        records.append(payload)
    if records:
        store.ingest(install_id, repo_id, "review-" + job_id, job_id[:64], records)
        store.record_review(tenant_id, repo_id, outcome, reviewed_at)
