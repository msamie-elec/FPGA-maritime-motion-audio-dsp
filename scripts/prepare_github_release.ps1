# Reproducible, conservative GitHub source-only staging. NEVER pushes by default.
param(
  [string]$RepositoryUrl='https://github.com/msamie-elec/FPGA-maritime-motion-audio-dsp.git',
  [string]$BaseBranch='feature/maritime-adaptive-av-v1.1',
  [string]$ReleaseBranch='release/maritime-av-evidence-2026-11-23',
  [string]$StageDirectory='',
  [switch]$Push
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (!(Get-Command git -ErrorAction SilentlyContinue)) {throw 'Install Git for Windows first.'}
if (!$StageDirectory) {$StageDirectory=Join-Path (Split-Path $root -Parent) 'maritime_github_release_stage'}
if (!(Test-Path (Join-Path $StageDirectory '.git'))) {
    if ((Test-Path $StageDirectory) -and @(Get-ChildItem $StageDirectory -Force).Count -gt 0) {
        throw "Staging directory exists but is not a Git checkout: $StageDirectory"
    }
    # The staging branch may already exist (created through the GitHub connector).
    # Clone that remote branch rather than creating a divergent local branch.
    $remoteBranch=(& git ls-remote --heads $RepositoryUrl "refs/heads/$ReleaseBranch")
    if ($LASTEXITCODE -ne 0) {throw 'Cannot inspect release branch on GitHub.'}
    if ($remoteBranch) {
        & git clone --single-branch --branch $ReleaseBranch $RepositoryUrl $StageDirectory
        if ($LASTEXITCODE -ne 0) {throw 'Could not clone existing release branch'}
    } else {
        & git clone --single-branch --branch $BaseBranch $RepositoryUrl $StageDirectory
        if ($LASTEXITCODE -ne 0) {throw 'Git clone failed; check private-repo access.'}
        Push-Location $StageDirectory
        try {
            & git switch -c $ReleaseBranch
            if ($LASTEXITCODE -ne 0) {throw 'Could not create new release branch'}
        } finally {Pop-Location}
    }
}
Push-Location $StageDirectory
try {
    $onBranch=(& git branch --show-current).Trim()
    if ($onBranch -ne $ReleaseBranch) {throw "Unexpected branch '$onBranch'; expected '$ReleaseBranch'"}
    # Clean tracked legacy files from staging only, never user project or origin repo.
    & git rm -r -q --ignore-unmatch .
    if ($LASTEXITCODE -ne 0) {throw 'Failed to clear obsolete tracked branch files'}
    # Git checkout can retain old ignored artefacts. Remove non-.git entries ONLY in staging.
    Get-ChildItem -Force | Where-Object {$_.Name -ne '.git'} | Remove-Item -Recurse -Force
    $files=@('.gitignore','.gitattributes','LICENSE','README.md','START_HERE_WINDOWS.txt',
             'OPEN_VIVADO_PROJECT_WINDOWS.ps1','RELEASE_MANIFEST.json','.github/workflows/maritime-ci.yml',
             'hardware/build/maritime_a7.xpr','hardware/build/README.md',
             'videos/README.md','media_sources/README.md',
             'evidence/owner_2026-11-23_revd/report_summary.json',
             'evidence/owner_2026-11-23_revd/owner_console_observations.json',
             'evidence/quality_2026-11-23_reference/quality_assessment.json',
             'evidence/quality_2026-11-23_reference/quality_assessment.md',
             'evidence/quality_2026-11-23_reference/normal_strong_reference.json',
             'evidence/xadc_2026-11-23/xadc_snapshots.csv',
             'evidence/xadc_2026-11-23/summary.json',
             'evidence/xadc_2026-11-23/README.md')
    $dirs=@('hardware/rtl','hardware/constraints','hardware/sim','hardware/vivado',
            'host','scripts','verification/model/tests','verification/system/tests',
            'docs/figures')
    $files+=@('verification/model/industrial_filter_assessment.py',
             'verification/system/media_quality_assessment.py',
             'verification/system/maritime_reliability.py')
    # Only current/docs needed for a standalone project; exclude superseded
    # screenshots and any report containing raw personal absolute paths.
    $files+=@('docs/BOARD_INTEGRATION.md','docs/FIR_M1_IMPLEMENTATION.md',
             'docs/MARITIME_ADAPTIVE_AUDIO_V11.md','docs/PROTOCOL.md',
             'docs/REAL_FOOTAGE_VALIDATION.md','docs/VIDEO_STABILISATION_DIAGNOSTICS.md',
             'docs/REVC_RESET_IO_REVIEW.md',
             'docs/PROJECT_STRUCTURE_AND_VERIFICATION.md',
             'docs/ENGINEERING_RELEASE_2026-11-23.md',
             'docs/MEDIA_QUALITY_2026-11-23.md','docs/GUI_REVG_PROGRESS_AND_PROFILE_COMPARISON.md','docs/GITHUB_RELEASE_CHECKLIST.md',
             'docs/XADC_DIE_TEMPERATURE.md',
             'docs/TEST_AND_VERIFICATION_COMMANDS.md')
    foreach ($relative in $files) {
        $from=Join-Path $root $relative
        if (!(Test-Path $from -PathType Leaf)) {throw "Missing release source: $from"}
        $to=Join-Path $StageDirectory $relative
        New-Item -ItemType Directory -Force -Path (Split-Path $to -Parent) | Out-Null
        Copy-Item $from $to -Force
    }
    foreach ($folder in $dirs) {
        $from=Join-Path $root $folder
        $to=Join-Path $StageDirectory $folder
        if (!(Test-Path $from -PathType Container)) {throw "Missing release directory: $from"}
        New-Item -ItemType Directory -Force -Path $to | Out-Null
        Copy-Item (Join-Path $from '*') $to -Recurse -Force
    }
    # All temporary and generated artefacts are ignored, including videos.
    & git add -A
    if ($LASTEXITCODE -ne 0) {throw 'Git stage failed'}
    $bad=(& git diff --cached --name-only | Where-Object {$_ -match '\.(mp4|bit|dcp|wdb|jou|log)$' -or $_ -match '^hardware/build/(?!maritime_a7.xpr|README.md)'})
    if ($bad) {throw ('Forbidden generated/media files staged: '+($bad -join ', '))}
    Write-Host 'GITHUB_RELEASE_STAGED — REVIEW THIS DIFF BEFORE PUSH:'
    & git diff --cached --stat
    & git status --short
    if ($Push) {
        & git -c core.editor=true commit -m 'Consolidate maritime FPGA AV source and evidence-led 2026-11-23 release'
        if ($LASTEXITCODE -ne 0) {throw 'Commit failed; configure git user.name and user.email'}
        & git push -u origin $ReleaseBranch
        if ($LASTEXITCODE -ne 0) {throw 'GitHub push failed; check authentication and remote branch'}
        Write-Host 'RELEASE_BRANCH_PUSHED — verify remote files and CI before merging/tagging.'
    } else {
        Write-Host 'NO FILES PUSHED. To publish, rerun with -Push after reviewing.'
    }
} finally {Pop-Location}
