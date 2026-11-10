# GEC Lighting Specifications Web App — v0.3.0

A source-code MVP for GEC engineering teams. Architecture **B**: Next.js/TypeScript on Vercel, Python FastAPI separately hosted in Docker, Supabase Auth/Postgres/private Storage, GitHub Actions CI. Python PDF/Excel/PPTX processors are adapted from Desktop v0.1.

## Current features

- Supabase Auth email/password, private owner-scoped projects (shared project memberships are not implemented).
- Upload PDF Datasheets directly from the browser to Supabase Storage, then ingest via FastAPI (no PDF file through Vercel request body).
- Import `.xlsx` BOQ/Schedule using project code and Excel mapping. Deduplicate by code.
- Match subsequent PDF ingestion to existing BOQ code, preserve existing engineer-entered values and quantities; flag conflicting fields under Notes for review.
- Parse explicit model, W/lm/CCT/CRI/beam/IP/IK/voltage and largest embedded raster image. **No OCR** and no verified ordering-code logic. The PDF filename cannot accidentally become the model.
- Review/edit, view short-lived signed source PDF, export `.xlsx` and `.pptx` in batches with optional templates.
- Input validation against invalid storage paths and duplicate mapping columns; generated spreadsheets escape formula-like cells.
- Offline sandbox test preview and full API test coverage; see [VERIFICATION.md](VERIFICATION.md).

## Architecture

```
Employee browser → Next.js / Vercel
    ↕ authenticated API bearer tokens
FastAPI / Docker (Render, Railway, VPS)
    ↕ service-role account (SERVER ONLY)
Supabase Auth + PostgreSQL + private Storage
    ↕ PyMuPDF / openpyxl / python-pptx
Datasheets → reviewed specifications → Excel / PPTX
```

## Deploy to GitHub, Vercel and Python host

1. Create a **private GitHub repo** and push the unpacked `gec-specifications` directory. Never commit `.env` or actual project PDFs.
2. Create a Supabase project, run `supabase/migrations/001_init.sql` in SQL Editor. The SQL enforces owner-only RLS and creates private `project-files` Storage. Add company users through Supabase Auth.
3. Backend (Python 3.12+):

   ```bash
   cd backend
   cp .env.example .env
   python -m pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   Set `SUPABASE_URL`, **server-only** `SUPABASE_SERVICE_ROLE_KEY`, `CORS_ORIGINS`. Or deploy `backend/Dockerfile` to Render/Railway/VPS, configuring these secrets there. Force HTTPS and limit ingress.
4. Frontend (Node 22+):

   ```bash
   cd frontend
   cp .env.example .env.local
   npm install
   npm run lint
   npm run build
   npm run dev
   ```

   Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL=https://<your-python-backend>` (never use the service-role key in a public variable).
5. In Vercel, import the GitHub private repo. Set **Root Directory `frontend`**, Next.js framework and the same frontend environment variables. Link `main` to production; Vercel will auto-deploy on new commits. GitHub Actions checks Python tests + Next typecheck/build on pushes and PRs. Backend deployment requires setting up the selected host's own auto-deploy from GitHub.
6. Add your Vercel host to Supabase Auth allowed redirects, including `/auth/callback`. Confirm actual login and storage permissions on a staging URL before adding staff users.

## Template contracts

- Excel: optional `.xlsx`; default sheet/header layout and fields A–Q. Mapping via UI (`code:A,model:B,...`), first row is header for BOQ imports; advanced export start-row/sheet options are available in the API.
- PPTX: **one** design slide; named text shapes `SPEC_code`, `SPEC_model`, `SPEC_power`, `SPEC_flux`, etc., plus optional image frame `SPEC_IMAGE`. One copied slide per selected light code. Templates not matching contract return an actionable error.
- Source PDF: reads text from first two pages and selects a qualifying raster image; scanned-only PDFs are rejected with an OCR-required message. Manufacturer model variants, table rows and conflicting power must be verified by a qualified engineer.

## Production gaps / non-claims

- This is not deployed to live GitHub, Vercel, Supabase or an external Python backend; no credentials were provided.
- Next.js **production build not yet checked**, npm installation blocked by sandbox network restrictions (see VERIFICATION.md). The browser tests target a local **test-only preview**, not Next.js.
- Shared project membership/roles, job queue, large batch OCR, malware scanning, audit history, retention policies, and formal engineering approval/sign-off need further work before company-wide rollout.
- Work with test or non-sensitive data until a security review and staging verification are complete.

## Repository

```
frontend/              Next.js frontend
backend/app/           FastAPI and document extraction/generation
backend/tests/         20-cycle API test and browser sandbox preview
supabase/migrations/   Database and Storage policies
.github/workflows/     GitHub CI
verification/          Browser run results and screenshot
```
