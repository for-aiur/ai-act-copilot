"""Project AI inventory and immutable release evidence packages."""
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, String, Table, Text, UniqueConstraint, delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from .findings import metadata, projects, repositories


def _table(name, *columns):
    return Table("aiact_customer_" + name, metadata,
        Column("id", String(36), primary_key=True),
        Column("tenant_id", String(36), nullable=False),
        Column("project_id", String(36), nullable=False, index=True), *columns)


systems = _table("ai_systems", Column("payload", Text, nullable=False))
links = _table("ai_system_links", Column("source", String(36), nullable=False),
    Column("target", String(36), nullable=False), Column("kind", String(32), nullable=False),
    UniqueConstraint("project_id", "source", "target", "kind"))
packages = _table("release_evidence", Column("system_id", String(36), nullable=False),
    Column("created_at", String(40), nullable=False), Column("payload", Text, nullable=False))


class SystemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=1000)
    owner: str = Field(default="", max_length=100)
    role: Literal["unknown", "provider", "deployer", "model_provider"] = "unknown"
    risk: Literal["unassessed", "needs_review", "potential_high", "potential_prohibited", "no_high_signal"] = "unassessed"
    rationale: str = Field(default="", max_length=1000)
    repository_id: str | None = Field(default=None, max_length=100)


class LinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=36)
    target: str = Field(min_length=1, max_length=36)
    kind: Literal["supplies_output", "calls", "monitors"]


class EvidenceItems(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    model_card: str = Field(default="", max_length=2000)
    validation: str = Field(default="", max_length=2000)
    oversight: str = Field(default="", max_length=2000)
    event_log: str = Field(default="", max_length=2000)
    technical_docs: str = Field(default="", max_length=2000)


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    release: str = Field(min_length=1, max_length=100)
    commit: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    model_version: str = Field(default="", max_length=100)
    items: EvidenceItems


def _scope(table, tenant, project):
    return (table.c.tenant_id == tenant, table.c.project_id == project)


def _project(db, tenant, project):
    row = db.execute(select(projects).where(
        projects.c.id == project, projects.c.tenant_id == tenant)).mappings().first()
    if row is None:
        raise LookupError("Project not found.")
    return row


def _system(db, tenant, project, identity):
    payload = db.execute(select(systems.c.payload).where(
        *_scope(systems, tenant, project), systems.c.id == identity)).scalar_one_or_none()
    if payload is None:
        raise LookupError("AI system not found in this project.")
    return json.loads(payload)


class AiInventory:
    def __init__(self, engine):
        self.engine = engine

    def view(self, tenant, project):
        with self.engine.connect() as db:
            item = _project(db, tenant, project)
            repo_ids = json.loads(item["repository_ids"])
            repos = db.execute(select(repositories.c.id, repositories.c.name).where(
                repositories.c.tenant_id == tenant, repositories.c.id.in_(repo_ids))).mappings()
            entries = db.execute(select(systems).where(*_scope(systems, tenant, project))).mappings()
            return {
                "systems": sorted(({"id": row["id"], **json.loads(row["payload"])} for row in entries),
                                  key=lambda entry: (entry["name"].casefold(), entry["id"])),
                "repositories": [dict(row) for row in repos],
                "links": [dict(row) for row in db.execute(select(
                    links.c.id, links.c.source, links.c.target, links.c.kind
                ).where(*_scope(links, tenant, project)).order_by(links.c.id)).mappings()],
            }

    def save_system(self, tenant, project, body, identity=None):
        with self.engine.begin() as db:
            item = _project(db, tenant, project)
            if body.repository_id and body.repository_id not in json.loads(item["repository_ids"]):
                raise ValueError("Choose a repository in this project.")
            data = body.model_dump()
            payload = json.dumps(data)
            if identity is None:
                identity = str(uuid4())
                db.execute(insert(systems).values(id=identity, tenant_id=tenant, project_id=project, payload=payload))
            else:
                _system(db, tenant, project, identity)
                db.execute(update(systems).where(*_scope(systems, tenant, project),
                    systems.c.id == identity).values(payload=payload))
        return {"id": identity, **data}

    def add_link(self, tenant, project, body):
        if body.source == body.target:
            raise ValueError("Choose two different systems.")
        data = {"id": str(uuid4()), **body.model_dump()}
        try:
            with self.engine.begin() as db:
                _system(db, tenant, project, body.source)
                _system(db, tenant, project, body.target)
                db.execute(insert(links).values(tenant_id=tenant, project_id=project, **data))
        except IntegrityError:
            raise ValueError("This relationship already exists.") from None
        return data

    def remove_link(self, tenant, project, identity):
        with self.engine.begin() as db:
            result = db.execute(delete(links).where(*_scope(links, tenant, project), links.c.id == identity))
            if not result.rowcount:
                raise LookupError("Relationship not found.")

    def evidence(self, tenant, project, identity):
        with self.engine.connect() as db:
            _system(db, tenant, project, identity)
            return [{"id": row["id"], "created_at": row["created_at"], **json.loads(row["payload"])}
                for row in db.execute(select(packages).where(*_scope(packages, tenant, project),
                    packages.c.system_id == identity).order_by(packages.c.created_at.desc(), packages.c.id)).mappings()]

    def save_evidence(self, tenant, project, identity, body, source, *, demo=False, package_id=None, db=None):
        if db is None:
            with self.engine.begin() as connection:
                return self.save_evidence(tenant, project, identity, body, source, db=connection)
        system = _system(db, tenant, project, identity)
        project_row = _project(db, tenant, project)
        repo = db.execute(select(repositories.c.name).where(repositories.c.tenant_id == tenant,
            repositories.c.id == system["repository_id"])).scalar_one_or_none()
        data = {"schema_version": 1, "project": project_row["name"], "system": {"id": identity, **system},
                "repository": repo, "source": source, "demo": demo, **body.model_dump()}
        record = {"id": package_id or str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat()}
        db.execute(insert(packages).values(**record, tenant_id=tenant, project_id=project,
            system_id=identity, payload=json.dumps(data)))
        return record | data

    def seed_demo(self, tenant, source):
        def identity(key):
            return str(uuid5(NAMESPACE_URL, f"aiact:systems-demo:{tenant}:{key}"))

        project, repo, pricing_repo = (identity(key) for key in ("project", "repository", "pricing-repository"))
        score, wellness, pricing = (identity(key) for key in ("score", "wellness", "pricing"))
        try:
            with self.engine.begin() as db:
                exists = db.execute(select(projects.c.id).where(
                    projects.c.id == project, projects.c.tenant_id == tenant)).scalar_one_or_none()
                if not exists:
                    db.execute(insert(repositories), [
                        {"id": repo, "tenant_id": tenant, "name": "example/nutrition-score",
                         "installation_id": "demo-ai-systems"},
                        {"id": pricing_repo, "tenant_id": tenant, "name": "example/health-pricing",
                         "installation_id": "demo-ai-systems"},
                    ])
                    db.execute(insert(projects).values(id=project, tenant_id=tenant,
                        name="Nutrition & Insurance Demo", repository_ids=json.dumps([repo, pricing_repo])))
                    for system_id, body in [
                        (score, SystemInput(name="Nutrition scoring service", owner="ML team", role="provider",
                            repository_id=repo, risk="needs_review",
                            purpose="Produces a score from meal records and supplies it to two downstream systems.",
                            rationale="Review each downstream use separately.")),
                        (wellness, SystemInput(name="Wellness app", owner="Product team", role="provider",
                            risk="no_high_signal", purpose="Uses the score to give users personal nutrition suggestions.",
                            rationale="This example does not use the score for insurance decisions.")),
                        (pricing, SystemInput(name="Health insurance pricing", owner="Insurance team", role="deployer",
                            risk="potential_high", repository_id=pricing_repo,
                            purpose="Uses the score in individual health insurance pricing.",
                            rationale="Review under Article 6 and Annex III 5(c). Confirm the role and decision process with Legal.")),
                    ]:
                        db.execute(insert(systems).values(id=system_id, tenant_id=tenant,
                            project_id=project, payload=body.model_dump_json()))
                    for target in (wellness, pricing):
                        db.execute(insert(links).values(id=identity(target), tenant_id=tenant,
                            project_id=project, source=score, target=target, kind="supplies_output"))
                    self.save_evidence(tenant, project, pricing, EvidenceInput(
                        release="v2.1.0", commit="d27d831ac6b4288f4381d4e2b963bc8ec8b06842", model_version="Nutrition score v2.1",
                        items=EvidenceItems(
                            model_card="Example model card: score informs underwriting review. Automatic premium decisions are out of scope for this example.",
                            oversight="Example runbook: an underwriter reviews the score and can override it before a price is issued.",
                            event_log="Example event EVT-1042 records release v2.1.0, model v2.1, input reference meal-418 and manual review requested.",
                        )), source, demo=True, package_id=identity("package"), db=db)
        except IntegrityError:
            with self.engine.connect() as db:
                _project(db, tenant, project)
        return {"project_id": project, "system_id": pricing, "package_id": identity("package")}
