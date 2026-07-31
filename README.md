# PeerForge

AI-powered academic peer review. A researcher uploads their work, describes it
in conversation, and a panel of AI reviewers with distinct specialisms
critiques it — grounded in the document, not in generalities.

Built for institutions: a university runs courses, professors enrol students,
and the cohort's progress is visible in one place.

---

## Quick start

Requires Docker, Node 20+, and Python 3.11+.

```bash
git clone https://github.com/RW2523/peerforge.git
cd peerforge
./run_app.sh
```

That script brings up Postgres, Redis and MinIO, applies migrations, installs
dependencies, and starts the API, the Celery worker, and the web app.

- Web app — http://localhost:3001
- API — http://localhost:8000
- API docs — http://localhost:8000/docs

You will need an [OpenRouter](https://openrouter.ai/) key to run a review. Add
it in Settings; it is not required to start the application.

To check what is configured and what is not:

```bash
curl http://localhost:8000/readiness
```

---

## What it does

**Set up by describing your work.** Rather than filling in a form, say what you
have and what kind of scrutiny you want. Each reply reads your uploaded
document and proposes a panel; the proposal on screen is always exactly what
will be created.

**Six reviewer specialisms** — advisor, methodology professor, domain expert,
skeptical reviewer, friendly professor, external examiner. They are given
different remits so the critiques complement rather than repeat each other,
and that differentiation is measured rather than assumed.

**Grounded in your document.** Uploaded material is chunked, retrieved per
turn, and cited. Every reply reports whether a document was consulted and how
many passages were read — if nothing was uploaded, it says so instead of
inventing detail.

**Institutional structure.** A university, its courses, and its people:
invitations with seats, bulk enrolment from a pasted roster, role-scoped
visibility, and a cohort view showing who is progressing and who has not
started — including those invited who never signed in.

**Evidence you can check.** Assessments track ten dimensions over time, and a
Review-Readiness Certificate is signed and independently verifiable.

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) — the hierarchy, how authentication
decides access, what happens during a turn, and the sharp edges worth knowing
before changing anything.

## Deploying

See [GOING-LIVE.md](GOING-LIVE.md).

**The application ships with authentication disabled.** In that state every
visitor is the same user in the same workspace, which is fine locally and not
fine in front of real people. `GET /readiness` reports it as blocking, and the
API refuses to start with authentication on and a placeholder secret.

## Development

```bash
# Backend tests
cd apps/api && .venv/bin/python -m pytest tests/ -q

# Frontend gates
cd apps/web && npx tsc --noEmit && npm run lint && npm run build

# Apply migrations (both directories, infra first)
make db-migrate
```

CI runs all of the above. Accessibility rules are part of lint, so a
regression there fails the build.

## Repository layout

```
apps/web        Next.js app
apps/api        FastAPI service
apps/workers    Celery tasks
infra           Docker compose, database migrations
packages        Shared contracts and generated types
docs/history    How past bugs were fixed — historical, several superseded
```
