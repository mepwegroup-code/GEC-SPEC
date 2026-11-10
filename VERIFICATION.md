# GEC Specifications v0.3 — Verification report

## Completed sandbox tests (2026-10-31, Asia/Ho_Chi_Minh)

- **27/27** Python `pytest` tests passed. **20 of those** are parameterized, isolated HTTP API end-to-end workflows: create project, upload mock Supabase PDF, PyMuPDF extraction, edit, Excel/PPTX default export, Excel/PPTX custom template export, inspect generated Office files, delete. Each round creates its own project and data.
- **20/20** headless Chromium interface workflow passes. Each browser round: create project, select PDF, upload, extract, review model/values, edit, download Excel, download PPTX, delete, assert no page JavaScript errors.
- See `verification/browser_20_runs.json` and `verification/browser_preview.png`.
- Additional backend cases cover path traversal, foreign-user storage paths, malformed files, duplicate Excel column mapping, formula-injection safety, BOQ import and conflict-preserving merge.
- TypeScript/TSX parsing: **5/5** source files passed the locally available TypeScript `transpileModule` syntax check.

### Exact sandbox test boundary

Tests exercise the **real FastAPI endpoint functions**, document extraction/generation libraries, actual generated XLSX/PPTX bytes, and a functional **static local sandbox preview** of the UI. Supabase PostgreSQL/Auth/Storage are **replaced with an in-memory test double**. Chromium has a machine-enforced `URLBlocklist=["*"]`, so browser fetch requests were bridged through Playwright to the local API, not made directly from Chromium. The preview is test-only and **is not the deployed Next.js/React frontend**.

The Next.js production build, login against real Supabase, Vercel deploy, and production HTTPS operation **were not verified**. NPM registry DNS resolution returned `EAI_AGAIN`, so `npm install` could not complete in the sandbox; full `npm run lint && npm run build` still must run in GitHub Actions or a connected local development environment. This report **must not be used as a claim of production readiness**.

### Reproduce backend tests

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
```

### Reproduce browser preview tests

On a machine with Chromium and Python Playwright installed:

```bash
cd backend
python -m pip install -r requirements-dev.txt
uvicorn tests.preview_server:app --host 127.0.0.1 --port 8765
# in a second terminal
python -m tests.run_browser_20
```

`tests.preview_server` bypasses production authentication using a fake test user and test storage; **never deploy it publicly**. In the restricted sandbox, the Playwright bridge is used to relay HTTP without accessing the blocked Chromium network stack.
