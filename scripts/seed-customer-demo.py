"""Seed synthetic repository findings in the configured demo account."""
from aiact.settings import load_settings
from aiact.workbench.identity import IdentityStore
from aiact.workbench.reviews import ReviewJobRepository
from aiact.workbench.findings import CustomerFindings

settings = load_settings()
if not settings.demo_mode:
    raise SystemExit("Enable demo mode before seeding synthetic examples.")
identity = IdentityStore(settings.database_url.get_secret_value())
user = identity.find_user_by_email(settings.demo_user_email)
if not user:
    raise SystemExit("Start the app once to create the demo account.")
jobs = ReviewJobRepository(settings.database_url.get_secret_value())
store = CustomerFindings(jobs.engine)
store.bind(user["tenant_id"], "demo-recruitment", "demo-installation", "example/recruitment")
store.bind(user["tenant_id"], "demo-chatbot", "demo-installation", "example/chatbot")
store.bind(user["tenant_id"], "demo-unreviewed", "demo-installation", "example/unreviewed")
for repository, priority, title in [
    ("demo-recruitment", "high", "Explain human oversight in candidate ranking"),
    ("demo-chatbot", "medium", "Explain how users identify automated replies"),
]:
    store.ingest("demo-installation", repository, 1, "synthetic-head", [{
        "id": "demo-finding", "priority": priority, "title": title,
        "explanation": "Synthetic example for exploring the review workflow.",
        "context_question": title,
        "evidence": {"path": "example.py", "quote": "model.predict(input)"},
        "citations": [],
    }])
print("Synthetic repositories and findings ready.")
jobs.close()
identity.close()
