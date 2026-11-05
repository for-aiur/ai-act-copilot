"""Trusted bridge from an already verified GitHub bot installation."""
import json

from .findings import CustomerFindings


class GitHubFindingAdapter:
    def __init__(self, engine, bot_store, config, client):
        self.customer = CustomerFindings(engine)
        self.bot = bot_store
        self.config = config
        self.client = client

    def import_pr(self, installation_id, repository_id, repo, number, head):
        records = []
        for row in self.bot.findings(repo, number):
            record = json.loads(row["payload"])
            records.append(record | {"id": row["id"], "priority": row["priority"]})
        self.customer.ingest(installation_id, repository_id, number, head, records)

    def reply(self, tenant_id, finding_id, head, actor, action, reason, event_id):
        from aiact.github_bot.gate import can_decide
        rows = self.customer.list(tenant_id)
        row = next((row for row in rows if row["id"] == finding_id), None)
        if row is None:
            raise LookupError("Finding not found.")
        original = self.bot.finding(row["payload"]["id"])
        if original is None:
            raise LookupError("Bot finding not found.")
        permission = self.client.permission(row["name"], actor)
        if not can_decide(self.config, {"roles": json.loads(original["roles"])}, actor, permission):
            raise PermissionError("This actor cannot decide this finding.")
        return self.customer.decide(tenant_id, finding_id, head, action, actor, reason, event_id)
