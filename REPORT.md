# ResumeLens — Senior Cloud Architect & Technical Lead Review

**Prepared for:** Aswin Panengal (MCA Graduate, 2026)  
**Goal:** Live portfolio deployment + Global AI/Backend Engineering job search  
**Review Date:** June 27, 2026  
**Reviewer Role:** Senior Cloud Architect & Technical Lead

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Deep Stack Analysis](#2-deep-stack-analysis)
3. [What You Are Doing Well](#3-what-you-are-doing-well)
4. [What Reads as "Local Student" Setup](#4-what-reads-as-local-student-setup)
5. [Critical Security Audit](#5-critical-security-audit)
6. [The Stick or Switch Verdict](#6-the-stick-or-switch-verdict)
7. [Strategic Recommendation](#7-strategic-recommendation)
8. [Deployment Roadmap](#8-deployment-roadmap)
9. [How to Present This on Your Resume](#9-how-to-present-this-on-your-resume)

---

## 1. Executive Summary

ResumeLens is a **genuinely impressive capstone project**. You have built a working, end-to-end AI placement management system with a real RAG pipeline, role-based access control, and two LLM integrations. Most MCA graduates present CRUD apps; you built a product with an AI-native architecture.

However, the project has a **hard wall between "impressive demo on localhost" and "live link I can send a recruiter."** The blockers are not architectural complexity — they are deployment plumbing: no container, local-only databases, and a critical `.env` security breach that must be fixed *today*.

**The path forward is clear: Option A — Containerise and swap local DBs for managed cloud services.** Estimated time to a live link: **3–5 focused days.**

---

## 2. Deep Stack Analysis

### 2.1 Full Technology Inventory

| Layer | Technology | Version | Classification |
|---|---|---|---|
| Web Framework | Django | 6.0.2 | Production-grade |
| Language | Python | 3.x | Production-grade |
| Primary Database | SQLite | 3 | ⚠️ Local-only |
| Vector Database | ChromaDB | 1.5.0 (local) | ⚠️ Local-only |
| Embedding Model | all-MiniLM-L6-v2 | via SentenceTransformers | ⚠️ Memory-heavy |
| LLM: Scoring | Google Gemini 2.5 Flash | via google-generativeai | Production-grade |
| LLM: RAG Chat | Groq (Llama 3.3 70B) | via groq SDK | Production-grade |
| PDF Parsing | PyPDF2 | 3.0.1 | Adequate |
| ML Ops | scikit-learn, NumPy | 1.8.0, 2.4.2 | Production-grade |
| Deep Learning Backend | PyTorch | 2.1.0 | ⚠️ 1GB+ dependency |
| Frontend | Django Templates + Bootstrap 5 | — | Functional, monolithic |
| Charts | Chart.js (radar) | — | Production-grade |
| App Server | Gunicorn / Uvicorn | in requirements | Ready, unconfigured |
| Static Files | Django DEBUG server | — | ⚠️ Dev-only |
| File Storage | Local `/media/` directory | — | ⚠️ Local-only |
| Email | Gmail SMTP | — | ⚠️ Credentials exposed |
| CI/CD | None | — | ⚠️ Missing |
| Containerisation | None | — | ⚠️ Missing |

### 2.2 Architecture Pattern

```
Browser
  │
  ▼
Django MTV (Monolith)
  │
  ├── core/views.py       ← Business logic + view rendering (tightly coupled)
  ├── core/utils.py       ← AI/RAG service layer (good separation)
  ├── core/models.py      ← ORM models (SQLite backend)
  │
  ├── LLM APIs (external)
  │     ├── Google Gemini  ← ATS scoring, radar chart, sandbox feedback
  │     └── Groq API       ← RAG recruiter chat
  │
  ├── Local ML (in-process)
  │     ├── SentenceTransformers (all-MiniLM-L6-v2)
  │     └── ChromaDB (local persistence at /chroma_db/)
  │
  └── File System
        ├── /media/        ← Uploaded PDFs
        └── /db.sqlite3    ← All relational data
```

This is a **classic Django monolith** — which is not a bad word. It is fast to build, easy to reason about, and straightforward to containerise. The AI logic in `utils.py` is already correctly isolated from views, which is the most important architectural decision you made.

### 2.3 RAG Pipeline Deep Dive

Your RAG implementation in `core/utils.py` is architecturally sound. Here is the full pipeline annotated:

```
Student uploads PDF resume
        │
        ▼
  PyPDF2 extracts raw text
        │
        ▼
  scrub_pii() — regex removes emails, phones, LinkedIn URLs   ← Good privacy practice
        │
        ▼
  Chunking: 150-word windows, 30-word overlap                 ← Correct chunking strategy
        │
        ▼
  SentenceTransformer encodes each chunk → 384-dim vectors
        │
        ▼
  ChromaDB stores chunks + metadata (application_id, job_id)  ← Local persistence
        │
        ▼
  ATS Score: cosine_similarity(resume_vec, job_context_vec)
        │
        ▼
  Gemini 2.5 Flash → structured JSON feedback (temp=0.0)

━━━━━━━━━━━━━━━━━━━━━━━━━━ RAG QUERY PATH ━━━━━━━━━━━━━━━━━━━━━━━━

Recruiter types query
        │
        ▼
  SentenceTransformer encodes query
        │
        ▼
  ChromaDB: top-7 semantically similar resume chunks (job-scoped)
        │
        ▼
  Anonymise: replace names with DB IDs in context
        │
        ▼
  Groq (Llama 3.3 70B) with strict no-hallucination system prompt
        │
        ▼
  Rendered Markdown response with leaderboard links
```

**Verdict on RAG:** This is not a tutorial copy-paste. The chunking strategy, privacy-first anonymisation, job-scoped retrieval, and dual-LLM architecture show real design thinking. This is your strongest technical asset.

### 2.4 Database Model Assessment

Your Django models in `core/models.py` are well-designed:

- **Custom AbstractUser** with role flags (`is_student`, `is_placement_admin`) instead of Groups — simpler for this scale
- **Application** model uses `SET_NULL` on job foreign key (prevents orphaned records when a job is deleted) — a production-level data safety decision
- **Unique constraint** on `(job, student)` prevents duplicate applications
- **Migration history is clean** — 7 linear migrations, no conflicts

**One concern:** The `placement/` app contains duplicate models (`JobPosting`, `Application`) that appear to be an unused legacy schema. This is dead code that could confuse a recruiter reading your codebase.

---

## 3. What You Are Doing Well

These are the things a senior engineer would look at and nod:

### 3.1 Privacy-First RAG Architecture
`scrub_pii()` runs before any text hits the LLM. The RAG context uses database IDs, not candidate names — the AI sees `"Candidate #42"`, not `"Aswin Panengal"`. Name de-anonymisation happens only in the Django view layer before rendering. This is production-level PII handling that most tutorials skip entirely.

### 3.2 Dual-LLM Strategy with Correct Temperature Settings
- **Gemini at `temperature=0.0`** for structured JSON scoring — deterministic, auditable
- **Groq at `temperature=0.1`** for conversational RAG — low variability, factual
This is not accidental. These are the correct temperature settings for these use cases, and using two LLMs with distinct roles is a strong portfolio signal.

### 3.3 Three-Tier RBAC
Students → Placement Admins (approval-gated) → Super Admin. The `@user_passes_test` decorator pattern is correctly applied throughout `views.py`. The approval gate on placement admins (`is_approved=False` until a superadmin approves) is a real-world enterprise pattern.

### 3.4 Data Safety in the ORM
`SET_NULL` on job foreign keys with `null=True` means deleting a job does not cascade-delete applications. This is the correct decision for an ATS — you want to preserve historical application data even after a job closes. This is a decision a senior engineer would validate in code review.

### 3.5 Semantic Chunking with Overlap
150-word chunks with 30-word overlap is a correct chunking strategy. Most beginner RAG implementations either use fixed character splits or no overlap, losing context at boundaries. You have implemented sliding window chunking, which improves retrieval quality at chunk boundaries.

### 3.6 PDF Security Validation
Magic byte check + MIME type verification + file size limit on upload. This prevents MIME spoofing (uploading a `.php` file renamed to `.pdf`) and server-side storage abuse.

---

## 4. What Reads as "Local Student" Setup

These are the signals that tell a hiring manager this has never been deployed:

### 4.1 SQLite as the Production Database
SQLite does not support concurrent writes. With two simultaneous resume uploads, you will get `database is locked` errors. No hosted cloud platform treats SQLite as a production database. **This must be replaced.**

### 4.2 ChromaDB Running Locally on Disk
Your vector store lives at `y:\ResumeLensProject\chroma_db\` — a Windows filesystem path. This data is completely non-portable. Containerised, the moment the container restarts, all stored resume vectors are gone unless you configure a persistent volume (complex). **This must be externalised.**

### 4.3 PyTorch (~1 GB) as a Runtime Dependency
`all-MiniLM-L6-v2` via `sentence-transformers` pulls in PyTorch as a dependency. This results in a Docker image of 2–3 GB. Free cloud tiers (Render, Railway) have RAM and storage limits. A 2 GB image will hit those limits and cause slow cold starts. **This is a significant deployment constraint.**

### 4.4 No Dockerfile, No Procfile, No CI/CD
There is no `Dockerfile`, no `Procfile`, no `render.yaml`, no `.github/workflows/`. The project cannot be deployed anywhere without first writing these files. A recruiter clicking "View Demo" and getting a 404 is worse than having no demo at all.

### 4.5 `DEBUG=True` and `ALLOWED_HOSTS = ['*']`
In `settings.py`, `DEBUG=True` means Django will print full stack traces (including local file paths and environment variables) to the browser on any 500 error. `ALLOWED_HOSTS = ['*']` means the application accepts requests for any hostname, enabling HTTP Host header attacks. These are the first two things any security scanner flags.

### 4.6 Static Files Served by Django's Dev Server
There is no `whitenoise` configuration and `STATIC_ROOT` is not collected. In production (non-DEBUG), Django does not serve static files at all — your entire UI (Bootstrap CSS, Chart.js) would be missing. Your deployed site would be a naked HTML page.

### 4.7 `BYPASS_OTP = True` in `views.py:88`
The email OTP verification flow is hardcoded to bypass. This is fine for local development but means any email address (fake or real) can register and be verified instantly. This is a test mode flag that was never removed.

### 4.8 The `placement/` App with Dead Code
The `placement/` Django app contains `JobPosting` and `Application` models that are never used anywhere in `views.py` or `urls.py`. This is an abandoned first attempt that was superseded by `core/`. Dead code in a portfolio project signals incomplete cleanup.

### 4.9 Media Files Served via `DEBUG`-only URL
In `config/urls.py`, the line `urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` only activates when `DEBUG=True`. In production, uploaded resumes would return 404. **Uploaded PDFs would be completely inaccessible.**

---

## 5. Critical Security Audit

> **STOP. Do these before any other task. Your API keys are public.**

### 5.1 CRITICAL — Exposed Secrets in Git

Your `.env` file has been committed to the git repository. The following credentials are currently public if your repository is or has ever been public:

| Secret | Status |
|---|---|
| `DJANGO_SECRET_KEY` | **COMPROMISED — Rotate immediately** |
| `GEMINI_API_KEY` | **COMPROMISED — Revoke in Google Cloud Console** |
| `GROQ_API_KEY` | **COMPROMISED — Revoke in Groq Console** |
| `EMAIL_HOST_PASSWORD` | **COMPROMISED — Revoke Gmail App Password** |

**Action:** Go to each provider's console NOW and revoke/rotate these credentials. Git history does not forget — even if you delete the `.env` file, the keys remain in the commit history and can be extracted with `git log -p`.

**Fix:** Use `git filter-repo` or BFG Repo Cleaner to purge the file from git history after rotating all keys.

### 5.2 HIGH — No Rate Limiting on LLM Endpoints

The `/job/<id>/chat/` endpoint calls Groq on every request with no rate limiting. A single malicious user could loop-call this endpoint and exhaust your Groq free tier in minutes. The same applies to the `/sandbox/` endpoint calling Gemini.

**Fix:** Add `django-ratelimit` — 5 lines of code.

### 5.3 MEDIUM — Media Files Without Authentication

Uploaded resumes at `/media/resumes/<uuid>.pdf` are publicly accessible to anyone who knows the URL. There is no authentication check on file access. A student could guess another student's resume URL.

**Fix:** Serve media files through a Django view that validates `request.user` before returning the file. In production, use signed S3 URLs.

### 5.4 LOW — `is_superuser` Reliance Without Explicit Superadmin Guard

The superadmin dashboard uses `@user_passes_test(lambda u: u.is_superuser)`. This is correct but means anyone granted Django superuser status (including via `manage.py createsuperuser`) gets full access. Acceptable for current scale.

---

## 6. The Stick or Switch Verdict

### Option A: Stick with Django, Containerise, Swap Local DBs

**What changes:** SQLite → PostgreSQL (managed), ChromaDB local → ChromaDB Cloud or Pinecone, add Dockerfile, gunicorn, whitenoise, fix security issues.

**What stays the same:** Every line of business logic, the entire RAG pipeline, all views, all templates, all models, all AI integrations.

| Factor | Assessment |
|---|---|
| Time to live link | 3–5 days |
| Risk of breaking features | Very low |
| Portfolio value change | High (same project, now demonstrably production-ready) |
| Learning signal to recruiters | Django + containerisation + managed cloud DBs + LLM APIs |
| Complexity | Medium |

### Option B: Rewrite Backend to FastAPI + Frontend to Next.js

**What changes:** Literally everything. New framework, new ORM (SQLAlchemy/Tortoise), new frontend, new routing, new authentication, new templating.

**What stays the same:** The RAG concept and the LLM API calls (but these need to be rewritten too).

| Factor | Assessment |
|---|---|
| Time to live link | 6–10 weeks minimum |
| Risk of breaking features | Very high — RAG pipeline, RBAC, and file handling all need reimplementation |
| Portfolio value change | Marginal — you are still building the same product |
| Learning signal to recruiters | FastAPI + Next.js (hype stack) but no working demo for 2 months |
| Complexity | Very high |

### The Hidden Truth About Option B

Recruiters for AI/Backend roles are not hiring you because you used FastAPI instead of Django. They are hiring you because you built a working RAG pipeline with PII scrubbing, dual-LLM architecture, and a real user management system. That value is in the LOGIC, not the framework.

Rewriting to FastAPI does not make your RAG pipeline more impressive — it just risks breaking it while spending 6 weeks on plumbing instead of on features. A Django monolith with a live URL beats a "coming soon" FastAPI project every time.

**The only scenario where Option B makes sense:** If you already have a live demo from Option A and want to build a *second* version as a learning exercise to add FastAPI to your resume. Do not do this at the cost of getting your live link.

---

## 7. Strategic Recommendation

### Verdict: Option A — Containerise and Ship

**Your priority is a live URL in the next week. Every day without it is a missed opportunity.**

Here is the honest trade-off table:

| | Option A (Recommended) | Option B |
|---|---|---|
| **Time to live demo** | 3–5 days | 6–10 weeks |
| **Stack on resume** | Django, PostgreSQL, ChromaDB Cloud, Docker, Railway, Gemini, Groq | FastAPI, Next.js, PostgreSQL, Pinecone, Vercel, Groq |
| **Risk** | Low | High |
| **Portfolio completeness** | Full working product | Incomplete rewrite |
| **"Hype" factor** | Medium | High |
| **Actual signal to AI recruiter** | Strong (working RAG, live demo) | Weak (no demo) |

### Why the "Hype Stack" Argument Loses Here

Yes, FastAPI + Next.js looks better on a bullet point. But:

1. A hiring manager clicking your live demo and seeing a working AI product will rank you higher than a resume listing FastAPI with no live link.
2. Your RAG pipeline quality, PII handling, and dual-LLM architecture are more impressive than your choice of web framework.
3. Django 6.x is not "old" — it is the framework behind Instagram, Pinterest, and Disqus at scale. Being able to deploy a Django project correctly is itself a marketable skill.
4. Once you have a live URL, you can call out the architecture in interviews: *"I containerised a Django monolith with a local ChromaDB and migrated to a managed vector DB on Railway. The main constraint was the 1.5GB ML dependency footprint, which I addressed by..."* — that is a real engineering story.

### What to Add to Your Resume AFTER Deployment

```
ResumeLens — AI Placement Management System (Live: resumelens.railway.app)
• Built a privacy-first RAG pipeline using ChromaDB + SentenceTransformers,
  serving as a semantic recruiter assistant across 384-dim resume embeddings
• Integrated dual-LLM architecture: Google Gemini 2.5 Flash (ATS scoring at temp=0)
  and Groq Llama 3.3 70B (conversational RAG at temp=0.1)
• Implemented PII scrubbing pre-LLM and ID-anonymised RAG context to prevent
  candidate data leakage to the model layer
• Containerised Django monolith with PostgreSQL (Supabase) + ChromaDB Cloud,
  deployed on Railway with Gunicorn + WhiteNoise
• Three-tier RBAC: Student → Recruiter (approval-gated) → Super Admin
```

---

## 8. Deployment Roadmap

This is your step-by-step action plan, ordered by dependency. Estimated total time: **3–5 days working 4–6 hours/day.**

---

### Phase 0: Security Emergency (Day 0 — Do This Now, ~2 hours)

> Do not push any code, create any PR, or share any links until Phase 0 is complete.

**Step 0.1 — Rotate All Exposed Credentials**

| Credential | Where to Rotate |
|---|---|
| Gemini API Key | [Google AI Studio](https://aistudio.google.com/) → API Keys → Delete old, create new |
| Groq API Key | [Groq Console](https://console.groq.com/) → API Keys → Delete old, create new |
| Django Secret Key | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| Gmail App Password | Google Account → Security → 2-Step → App Passwords → Delete old, create new |

**Step 0.2 — Purge .env from Git History**

```bash
# Install BFG Repo Cleaner (one-time)
# Download bfg.jar from rtyley.github.io/bfg-repo-cleaner

# Add .env to .gitignore FIRST
echo ".env" >> .gitignore

# Remove .env from git tracking (keeps local file)
git rm --cached .env
git commit -m "chore: remove .env from tracking"

# Use BFG to purge from all history
java -jar bfg.jar --delete-files .env --no-blob-protection
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

**Step 0.3 — Create .env.example for the Repository**

```bash
# .env.example (commit this)
DJANGO_SECRET_KEY=your-secret-key-here
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=your-groq-api-key
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEBUG=False
DATABASE_URL=postgresql://user:pass@host:5432/dbname
CHROMA_HOST=https://api.trychroma.com
CHROMA_API_KEY=your-chroma-cloud-key
```

---

### Phase 1: Code Fixes (Day 1, ~4 hours)

**Step 1.1 — Remove Dead Code**

Delete the `placement/` app entirely (it is never used):
```bash
# Remove the app directory
rm -rf placement/

# Remove from INSTALLED_APPS in config/settings.py
# Remove any imports from config/urls.py
```

**Step 1.2 — Fix Static Files (WhiteNoise)**

```bash
pip install whitenoise
```

In `config/settings.py`:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add SECOND, right after Security
    # ... rest of middleware
]

STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

**Step 1.3 — Fix Media Files (Production Serving)**

In `config/settings.py`, add a cloud storage backend. Use Cloudinary (free tier, 25GB):
```bash
pip install cloudinary django-cloudinary-storage
```

```python
# config/settings.py
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
```

This means uploaded PDFs survive container restarts and are served from Cloudinary's CDN — not from your server's disk.

**Step 1.4 — Configure Production Settings**

```python
# config/settings.py — production guards

import os
import dj_database_url

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

# Database: auto-detect PostgreSQL in production
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR}/db.sqlite3',
        conn_max_age=600
    )
}

# Security headers (production only)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
```

```bash
pip install dj-database-url
```

**Step 1.5 — Remove BYPASS_OTP and Test Flags**

In `core/views.py` line 88, remove or make the bypass conditional:
```python
# Before
BYPASS_OTP = True

# After
BYPASS_OTP = os.getenv('BYPASS_OTP', 'False') == 'True'  # False in production
```

**Step 1.6 — Add Rate Limiting to LLM Endpoints**

```bash
pip install django-ratelimit
```

In `core/views.py`:
```python
from ratelimit.decorators import ratelimit

@login_required
@ratelimit(key='user', rate='20/h', method='POST', block=True)
def job_chat(request, job_id):
    ...

@login_required
@ratelimit(key='user', rate='10/h', method='POST', block=True)
def resume_sandbox(request):
    ...
```

**Step 1.7 — Update requirements.txt**

```bash
pip freeze > requirements.txt
```

---

### Phase 2: Database Migration (Day 2, ~3 hours)

**Step 2.1 — Set Up PostgreSQL on Supabase (Free)**

1. Go to [supabase.com](https://supabase.com) → New Project
2. Choose a region close to your target audience (Singapore for South/Southeast Asia)
3. Copy the **Connection String** (URI format): `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`
4. Add to your `.env` as `DATABASE_URL`

**Step 2.2 — Migrate Your Schema**

```bash
# With DATABASE_URL pointing to Supabase:
python manage.py migrate

# Create your superadmin user
python manage.py createsuperuser
```

**Step 2.3 — Verify Migration**

Log in to the Supabase dashboard → Table Editor → Confirm `core_user`, `core_job`, `core_application`, `core_studentprofile` tables exist with the correct schema.

> **Note:** SQLite data will not transfer automatically. For a portfolio project, starting fresh in production is fine. Document this in your README: "Production DB is pre-seeded with demo data."

---

### Phase 3: Vector Database Migration (Day 2, ~2 hours)

This is the most technically interesting migration. You have two good options:

**Option 3A: ChromaDB Cloud (Easiest — Same SDK)**

ChromaDB now offers a managed cloud service with a free tier.

1. Sign up at [trychroma.com](https://trychroma.com)
2. Create a new collection
3. Get your API key and host URL

Update `core/utils.py`:
```python
import chromadb
import os

def get_chroma_client():
    chroma_host = os.getenv('CHROMA_HOST')
    chroma_api_key = os.getenv('CHROMA_API_KEY')
    
    if chroma_host and chroma_api_key:
        # Production: ChromaDB Cloud
        return chromadb.HttpClient(
            host=chroma_host,
            headers={"X-Chroma-Token": chroma_api_key}
        )
    else:
        # Development: local persistence
        return chromadb.PersistentClient(path="chroma_db")

# Replace the current client initialisation with:
chroma_client = get_chroma_client()
```

**Option 3B: Pinecone (More Resume-Worthy, Still Free)**

Pinecone has a free tier (1 index, 100K vectors) and is more widely recognised on resumes.

```bash
pip install pinecone-client
```

This requires refactoring `save_to_vector_db()` and `chat_with_resumes()` to use the Pinecone SDK instead of ChromaDB. More work (~2 hours), but Pinecone is more visible on a resume than ChromaDB Cloud.

**Recommendation: Start with Option 3A (ChromaDB Cloud) to get live fast. Add Pinecone to a v2 branch.**

---

### Phase 4: Containerisation (Day 3, ~3 hours)

**Step 4.1 — Write the Dockerfile**

Create `Dockerfile` in project root:

```dockerfile
# Build stage — install Python deps
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system deps for PyPDF2 and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

# Collect static files
RUN python manage.py collectstatic --no-input

EXPOSE 8000

# Gunicorn: 2 workers (fit within 512MB RAM on free tier)
CMD gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

> **Important:** The `--timeout 120` flag is critical. Your Gemini and Groq calls can take 15–30 seconds. Without this, gunicorn will kill the request at the default 30-second timeout.

**Step 4.2 — Write .dockerignore**

```
venv/
__pycache__/
*.pyc
*.pyo
db.sqlite3
chroma_db/
media/
.env
.git/
*.md
```

**Step 4.3 — Write docker-compose.yml (for local testing)**

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - PORT=8000
    volumes:
      - .:/app  # remove in production build
```

**Step 4.4 — Test the Container Locally**

```bash
docker build -t resumelens .
docker run -p 8000:8000 --env-file .env resumelens
# Visit http://localhost:8000 and verify the app works
```

---

### Phase 5: Cloud Deployment (Day 4, ~3 hours)

**Recommended Platform: Railway.app**

Why Railway over alternatives:
- $5 free credit monthly (no credit card for signup)
- Persistent containers (unlike Render's free tier which sleeps)
- Supports Docker natively
- Built-in PostgreSQL add-on (or use your Supabase URL)
- No cold starts (unlike Vercel serverless)
- CLI-driven deployment

**Why not Render (free tier):** Render's free tier spins down after 15 minutes of inactivity. A recruiter clicking your demo link and waiting 30 seconds for a cold start is a bad first impression.

**Why not Vercel/Netlify:** These are frontend/serverless platforms. Django is a WSGI app with file uploads and ML dependencies — it does not fit the serverless model without significant refactoring.

**Why not Heroku:** The free tier was removed. Paid plans start at $7/month.

**Step 5.1 — Deploy to Railway**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialise project in your repo
railway init

# Link to a new project
railway new

# Deploy
railway up
```

Or use the Railway dashboard:
1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub Repo
2. Select your ResumeLens repository
3. Railway auto-detects the Dockerfile

**Step 5.2 — Set Environment Variables in Railway**

In Railway dashboard → Your Service → Variables, add:
```
DJANGO_SECRET_KEY=<your-new-key>
GEMINI_API_KEY=<your-new-key>
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=<your-new-key>
EMAIL_HOST_USER=<your-gmail>
EMAIL_HOST_PASSWORD=<your-app-password>
DEBUG=False
ALLOWED_HOSTS=<your-app>.up.railway.app
DATABASE_URL=<your-supabase-uri>
CHROMA_HOST=<your-chroma-cloud-host>
CHROMA_API_KEY=<your-chroma-api-key>
CLOUDINARY_CLOUD_NAME=<name>
CLOUDINARY_API_KEY=<key>
CLOUDINARY_API_SECRET=<secret>
```

**Step 5.3 — Run Database Migrations in Production**

```bash
# Via Railway CLI
railway run python manage.py migrate
railway run python manage.py createsuperuser
```

**Step 5.4 — Set Up Custom Domain (Optional but Recommended)**

Railway provides a free `.up.railway.app` subdomain. For a portfolio, a custom domain like `resumelens.dev` (~$10/year on Namecheap) looks significantly more professional than `resumelens-production.up.railway.app`.

---

### Phase 6: Polish and Monitoring (Day 5, ~2 hours)

**Step 6.1 — Seed Demo Data**

Write a Django management command that creates:
- 3 demo recruiters (pre-approved)
- 5 demo students (with uploaded resumes)
- 3 demo job postings
- Applications with AI scores already calculated

This ensures any recruiter visiting your demo sees a populated, active-looking platform — not an empty database.

**Step 6.2 — Add Basic Health Check**

In `core/views.py`:
```python
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok", "version": "1.0"})
```

In `config/urls.py`:
```python
path('health/', views.health_check, name='health_check'),
```

Railway (and any uptime monitor) can ping `/health/` to confirm the service is alive.

**Step 6.3 — Set Up Free Uptime Monitoring**

Sign up at [UptimeRobot](https://uptimerobot.com) (free) and add a monitor for your Railway URL. You will get email alerts if the service goes down. You can also display an uptime badge in your README.

**Step 6.4 — README Overhaul**

Your README should now include:
- Live demo link (prominent, at the top)
- Architecture diagram (the pipeline flow from Section 2.3)
- Demo credentials (recruiter and student login for evaluators)
- Technology stack table
- Local development setup
- Deployment instructions (how you got it live)

---

### Deployment Architecture Final State

```
                        ┌─────────────────────────────────────┐
                        │           Railway.app               │
                        │                                     │
                        │  Django (Gunicorn, 2 workers)       │
                        │  + WhiteNoise (static files CDN)    │
                        │  + Port: $PORT (auto-assigned)      │
                        └──────────────┬──────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
   ┌──────────────────┐   ┌─────────────────────┐  ┌──────────────────────┐
   │  Supabase        │   │  ChromaDB Cloud     │  │  Cloudinary          │
   │  (PostgreSQL)    │   │  (Vector Store)     │  │  (PDF Storage, CDN)  │
   │  Free tier       │   │  Free tier          │  │  Free tier 25GB      │
   │  500MB           │   │  Managed embeddings │  │                      │
   └──────────────────┘   └─────────────────────┘  └──────────────────────┘
              │                        │
              │              ┌─────────┴──────────┐
              │              │                    │
              ▼              ▼                    ▼
   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
   │ Google Gemini │  │  Groq API     │  │  Gmail SMTP   │
   │ 2.5 Flash     │  │  Llama 3.3 70B│  │  (OTP email)  │
   │ (ATS + RAG)   │  │  (RAG chat)   │  │               │
   └───────────────┘  └───────────────┘  └───────────────┘
```

**Estimated Monthly Cost at Zero Traffic:** $0
**Estimated Monthly Cost at Light Traffic (50 users/day):** $0–$2 (LLM API calls only)

---

### Summary Checklist

```
Phase 0 — Security Emergency
  [ ] Rotate Gemini API key
  [ ] Rotate Groq API key
  [ ] Rotate Django secret key
  [ ] Revoke Gmail app password, create new
  [ ] Purge .env from git history (BFG)
  [ ] Add .env to .gitignore, commit .env.example

Phase 1 — Code Fixes
  [ ] Delete placement/ app (dead code)
  [ ] Install + configure WhiteNoise
  [ ] Install + configure Cloudinary for media
  [ ] Add dj-database-url, update DATABASES setting
  [ ] Add production security headers
  [ ] Remove BYPASS_OTP hardcode
  [ ] Add rate limiting to /sandbox/ and /chat/ views
  [ ] pip freeze > requirements.txt

Phase 2 — PostgreSQL Migration
  [ ] Create Supabase project, copy DATABASE_URL
  [ ] python manage.py migrate (against Supabase)
  [ ] python manage.py createsuperuser (in production)

Phase 3 — Vector DB Migration
  [ ] Sign up for ChromaDB Cloud
  [ ] Update get_chroma_client() in utils.py
  [ ] Test resume upload + RAG query against cloud ChromaDB

Phase 4 — Containerisation
  [ ] Write Dockerfile (multi-stage)
  [ ] Write .dockerignore
  [ ] Write docker-compose.yml
  [ ] docker build + docker run locally — verify all features work
  [ ] Push Dockerfile to GitHub

Phase 5 — Deploy to Railway
  [ ] Create Railway project from GitHub repo
  [ ] Set all environment variables in Railway dashboard
  [ ] railway run python manage.py migrate
  [ ] railway run python manage.py createsuperuser
  [ ] Visit live URL, test all features end-to-end
  [ ] (Optional) Add custom domain

Phase 6 — Polish
  [ ] Write seed data management command, run it
  [ ] Add /health/ endpoint
  [ ] Set up UptimeRobot monitor
  [ ] Update README with live demo link and architecture diagram
  [ ] Update resume and LinkedIn with live URL
```

---

## 9. How to Present This on Your Resume

### The Bullet Points That Will Get You Interviews

```
ResumeLens — AI Placement Management Platform
GitHub: github.com/[you]/ResumeLens | Live: resumelens.up.railway.app

• Designed and deployed a privacy-first RAG pipeline using ChromaDB + SentenceTransformers
  (all-MiniLM-L6-v2, 384-dim), enabling semantic recruiter queries across resume vector stores

• Implemented PII scrubbing pre-embedding and ID-anonymised RAG context windows to prevent
  candidate data leakage to the LLM layer — a production data governance pattern

• Integrated dual-LLM architecture: Google Gemini 2.5 Flash (deterministic ATS scoring
  at temperature=0.0) and Groq Llama 3.3 70B (RAG chat at temperature=0.1)

• Built three-tier RBAC (Student → Recruiter [approval-gated] → Super Admin) with OTP email
  verification using Django's custom AbstractUser model

• Containerised Django monolith with Gunicorn + WhiteNoise, migrated from SQLite + local
  ChromaDB to Supabase PostgreSQL + ChromaDB Cloud; deployed on Railway with zero downtime

Tech stack: Python, Django 6, PostgreSQL (Supabase), ChromaDB Cloud, Cloudinary,
            Google Gemini, Groq, SentenceTransformers, Docker, Railway
```

### The Story for Your Interview

When they ask "tell me about a project you're proud of":

> *"I built ResumeLens, a full AI placement system. The part I'm most proud of technically is the RAG pipeline. I faced a real data privacy problem — the recruiter assistant needed to reference candidate resumes to answer questions, but I didn't want the LLM to learn candidate names or contact details. So I built a two-layer anonymisation: first, I scrub PII before embedding. Second, the RAG context that goes to Groq uses database IDs instead of names — the model sees 'Candidate 42 has 3 years of Python experience,' and only the Django view layer translates that back to the real name for the UI. Deploying it taught me the hard way that a 1.5GB ML dependency footprint is a real constraint on free-tier cloud — I had to write a multi-stage Dockerfile to keep the final image under 2GB."*

That answer demonstrates: system design thinking, privacy/data governance awareness, LLM integration experience, and real deployment experience. That is the answer that gets callbacks.

---

*End of Report — ResumeLens Architectural Review, June 2026*
