# Saved review sessions

The review engine can pause when it needs one piece of context and continue
after an answer. A session has a stable ID. Reading it does not run the model.
An answer resumes the saved review rather than starting from the first step.

```python
from pathlib import Path
from aiact.rag.sessions import start_review_session, get_review_session, resume_review_session
from aiact.rag.retriever import HybridRetriever

retriever = HybridRetriever(settings, rag_release_id)
session = start_review_session(Path("examples/recruitment/ranker.py"), provider, retriever)
print(session.id, session.status, session.context_question)

saved = get_review_session(session.id)
# Reopen the saved release, even if a newer release is active.
pinned = HybridRetriever(settings, saved.rag_release_id)
session = resume_review_session(session.id, Path("examples/recruitment/ranker.py"),
    provider, pinned, "A recruiter checks every score before making a decision.")
```

Install the engine with `python -m pip install -e './engine[dev]'`. SQLite is
the default and stores checkpoints in `.aiact-workbench/aiact.db`, which is
local and gitignored. Set `DATABASE_URL` in the private `.env` file to choose a
different file, for example `sqlite:////tmp/aiact-reviews.db`. PostgreSQL is
optional: install `./engine[postgres]` and set a `postgresql://` URL.

Each checkpoint keeps the bounded evidence, retrieved legal passages, model
identity, source fingerprint, RAG release ID and answer history needed to
resume. It does not store provider credentials or the full source file. If the
source or original scenario context changes, resume returns `stale_source`; start
a new review to use changed code. Reopen the session's saved RAG release to
resume; newer active releases do not replace its passages.

SQLite is intended for one local process. Its writes are serialized within
that process. Use PostgreSQL before running multiple workers against the same
sessions. The dashboard does not expose saved sessions yet; that API is another
M2 task.
