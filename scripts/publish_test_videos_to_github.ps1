# Publish verified maritime MP4 inputs from the local test-media package to the connected private GitHub repository.
param([string]$Repository = 'https://github.com/msamie-elec/FPGA-maritime-motion-audio-dsp.git',[string]$Branch='main')
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifest=Get-Content (Join-Path $root 'videos/VIDEO_TEST_MANIFEST.json') -Raw | ConvertFrom-Json
if(-not (Get-Command git -ErrorAction SilentlyContinue)){throw 'Install Git for Windows and authenticate with GitHub first.'}
$dest=Join-Path $env:TEMP ('maritime-videos-' + (Get-Date -Format yyyyMMddHHmmss))
& git clone --branch $Branch --single-branch $Repository $dest
if($LASTEXITCODE -ne 0){throw 'Git clone failed; no data uploaded.'}
foreach($f in $manifest.files){
  $src=Join-Path $root ('videos/'+$f.filename)
  if(-not (Test-Path $src)){throw "Missing: $src"}
  if((Get-FileHash $src -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256){throw "Checksum mismatch: $($f.filename)"}
  Copy-Item -LiteralPath $src -Destination (Join-Path $dest ('videos/'+$f.filename)) -Force
}
Push-Location $dest
try {
  & git add -- videos/00_Maritime_Short_Original.mp4 videos/01_Maritime_Short_Original.mp4 videos/02_Maritime_Long_30s_With_Audio.mp4 videos/03_Unified_Quick_Test_3s.mp4
  & git diff --cached --check
  if($LASTEXITCODE -ne 0){throw 'Staging check failed.'}
  if(-not ((& git diff --cached --name-only) -join '')){Write-Host 'All four videos already published.';return}
  & git commit -m 'Add AI-generated maritime test MP4 input videos'
  if($LASTEXITCODE -ne 0){throw 'Git commit failed.'}
  & git push origin $Branch
  if($LASTEXITCODE -ne 0){throw 'Git push failed; retry from the preserved checkout: '+$dest}
  Write-Host 'MARITIME_TEST_VIDEOS_GITHUB_PUSH_COMPLETE'
} finally {Pop-Location}
