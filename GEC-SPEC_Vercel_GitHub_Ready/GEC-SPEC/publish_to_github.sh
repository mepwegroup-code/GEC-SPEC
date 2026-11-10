#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
repo='mepwegroup-code/GEC-SPEC'
command -v git >/dev/null || { echo 'Install git'; exit 1; }
command -v gh >/dev/null || { echo 'Install GitHub CLI (gh)'; exit 1; }
gh auth status
[[ -f frontend/package.json && -f backend/app/main.py ]] || { echo 'Missing GEC Specifications source'; exit 1; }
login="$(gh api user --jq .login)"
[[ "$login" == 'mepwegroup-code' ]] || { echo "Connected as $login, expected mepwegroup-code"; exit 1; }
if [[ ! -d .git ]]; then git init -b main; fi
branch="$(git branch --show-current)"
[[ -z "$branch" || "$branch" == main ]] || { echo "Refusing from branch $branch"; exit 1; }
git config --local user.name "$(git config --local user.name || echo "$login")"
git config --local user.email "$(git config --local user.email || echo "${login}@users.noreply.github.com")"
git add .
if ! git diff --cached --quiet; then git commit -m 'Initial import: GEC Specifications Web App v0.3'; fi
if ! gh repo view "$repo" --json name --jq .name >/dev/null 2>&1; then
  gh repo create "$repo" --private --source . --remote origin --push
else
  if ! git remote get-url origin >/dev/null 2>&1; then git remote add origin "https://github.com/${repo}.git"; fi
  origin="$(git remote get-url origin)"
  [[ "$origin" =~ (^|[:/])mepwegroup-code/GEC-SPEC(\.git)?$ ]] || { echo "Refusing unexpected origin $origin"; exit 1; }
  git push -u origin main
fi
printf '\nRepository: https://github.com/%s\n' "$repo"
echo 'Check Actions before importing Vercel project.'
