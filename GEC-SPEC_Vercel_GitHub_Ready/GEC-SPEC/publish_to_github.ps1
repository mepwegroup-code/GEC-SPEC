# GEC Specifications - one-time private GitHub repo creation and push.
# Requirements: Git (git-scm.com), GitHub CLI (cli.github.com).
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$target = 'mepwegroup-code/GEC-SPEC'
function Run([string]$command, [string[]]$arguments) {
    & $command @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $command $($arguments -join ' ')" }
}
foreach ($cmd in @('git','gh')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd was not found. Install Git and GitHub CLI before running this script."
    }
}
Run 'gh' @('auth','status')
# Prevent accidental publishing as a public repository or pushing to a different remote.
if (-not (Test-Path 'frontend/package.json') -or -not (Test-Path 'backend/app/main.py')) {
    throw 'GEC Specifications source files were not found in the current folder.'
}
if (-not (Test-Path '.git')) { Run 'git' @('init','-b','main') }
# Ensure the local branch is main, without overwriting unrelated work.
$branch = (& git branch --show-current).Trim()
if ($branch -and $branch -ne 'main') { throw "Current Git branch is $branch; use a clean source checkout." }
$login = (& gh api user --jq .login).Trim()
if ($LASTEXITCODE -ne 0 -or -not $login) { throw 'Could not read authenticated GitHub account.' }
if ($login -ne 'mepwegroup-code') { throw "Connected as $login. Authenticate with mepwegroup-code before continuing." }
# Local per-repo identity only; do not overwrite global Git settings.
if (-not (& git config --local user.name)) { Run 'git' @('config','--local','user.name',$login) }
if (-not (& git config --local user.email)) { Run 'git' @('config','--local','user.email',"$login@users.noreply.github.com") }
Run 'git' @('add','.')
& git diff --cached --quiet
if ($LASTEXITCODE -eq 1) { Run 'git' @('commit','-m','Initial import: GEC Specifications Web App v0.3') }
elseif ($LASTEXITCODE -ne 0) { throw 'Git staging check failed.' }
& gh repo view $target --json name --jq .name *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating private repository $target" -ForegroundColor Cyan
    Run 'gh' @('repo','create',$target,'--private','--source','.','--remote','origin','--push')
} else {
    Write-Host "Repository $target already exists; checking remote." -ForegroundColor Cyan
    & git remote get-url origin *> $null
    if ($LASTEXITCODE -ne 0) { Run 'git' @('remote','add','origin',"https://github.com/$target.git") }
    $actual = (& git remote get-url origin).Trim()
    if ($actual -notmatch '(^|[:/])mepwegroup-code/GEC-SPEC(\.git)?$') {
        throw "Refusing to push to unexpected origin: $actual"
    }
    # A non-fast-forward push fails safely. Never force-push or delete an existing branch.
    Run 'git' @('push','-u','origin','main')
}
Run 'gh' @('repo','view',$target,'--web')
Write-Host 'Repository created/updated. Verify GitHub Actions status before Vercel deployment.' -ForegroundColor Green
