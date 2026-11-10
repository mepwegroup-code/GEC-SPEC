# GEC-SPEC — Vercel Deployment (Frontend Only)

## 1. Repository

**Target:** `mepwegroup-code/GEC-SPEC` (**Private**)  
Repository creation link: https://github.com/new?name=GEC-SPEC

Once authenticated in GitHub CLI (`gh auth login`), run `publish_to_github.bat` on Windows. It **creates the private repo** if missing, commits the current source, and pushes `main` without force. It does not touch `mepwegroup-code/GEC`.

GitHub App integration in this conversation cannot create a new repository directly, so repository creation/push needs GitHub CLI authorization on your computer. Do not upload real project PDFs or `.env` files.

## 2. Connect the new repo to Vercel

Vercel Git connections are **per project/repository**. If the existing Vercel project currently watches the website repo `GEC`, it will not automatically watch `GEC-SPEC`.

- On Vercel: **Add New → Project → Import Git Repository → `mepwegroup-code/GEC-SPEC`**.
- If GitHub integration cannot see the repo, open Vercel GitHub integration and grant repo access.
- **Framework Preset:** Next.js.
- **Root Directory:** `frontend` (important).
- **Install Command:** `npm install --no-audit --no-fund` (or Vercel default).
- **Build Command:** `npm run build` (or default `next build`).
- **Output Directory:** leave at Next.js default; do not set `out` or static export.
- **Production branch:** `main`. Future commits to `main` will automatically trigger Vercel deployments.

### Vercel Environment Variables

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY
NEXT_PUBLIC_API_URL=https://YOUR_FASTAPI_BACKEND
```

These `NEXT_PUBLIC_*` variables are browser-visible. **Never** set `SUPABASE_SERVICE_ROLE_KEY` in Vercel frontend. Enter actual values in Vercel project settings, not source control.

## 3. Backend — separately deployed (Architecture B)

Deploy `backend/Dockerfile` to Render, Railway, VPS or an internal server exposed via HTTPS.

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SECRET
CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
```

Only configure the service-role secret on the backend host. Deploy migration `supabase/migrations/001_init.sql`, configure Supabase Auth redirect URL `https://YOUR-VERCEL-DOMAIN.vercel.app/auth/callback`, and allow user logins. For custom domains, adjust `CORS_ORIGINS` and allowed redirects.

## 4. Verification checklist

1. GitHub Actions frontend typecheck/build and backend tests are green.
2. Vercel deployment finishes with the correct Root Directory.
3. Test Supabase login and session refresh on staging.
4. Upload sample PDF, review extracted fields, export `.xlsx` and `.pptx` through HTTPS backend.
5. Test access controls with two distinct employees; **v0.3 owner-scoped projects are not shared**.
6. Scan for exposed credentials, enable backups and determine document retention rules before company-wide rollout.

**Status:** This package is deployment-ready in structure, not proof of a working production deployment. External GitHub/Vercel/Supabase credentials and live integration tests are still required.
