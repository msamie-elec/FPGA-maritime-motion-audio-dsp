# ONE-source, TWO-filter processing; does not flash hardware automatically.
param(
  [string]$Video = '.\videos\03_Unified_Quick_Test_3s.mp4',
  [string]$Out = '.\videos\sim\unified_demo',
  [ValidateSet('Normal','Strong')][string]$Profile = 'Normal',
  [string]$Port = ''
)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
$argsList = @('.\host\unified_pipeline.py','--video',$Video,'--out',$Out,'--profile',$Profile)
if (-not [string]::IsNullOrWhiteSpace($Port)) { $argsList += @('--port',$Port) }
& python @argsList
if ($LASTEXITCODE -ne 0) { throw 'Unified video/audio processing FAILED. Review log; do not claim a hardware pass.' }
$mode = 'software reference'
if (-not [string]::IsNullOrWhiteSpace($Port)) { $mode = 'physical FPGA requested' }
Write-Host "UNIFIED_AV_DEMO_PASS (mode=$mode, output=$Out)"
