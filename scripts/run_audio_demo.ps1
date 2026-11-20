# Audio v0.9 offline prototype. By default software-reference only.
param(
  [Parameter(Mandatory=$true)][string]$Source,
  [string]$Port = '',
  [double]$Start = 0,
  [double]$Seconds = 4
)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
python host/design_audio_coefficients.py
if ($LASTEXITCODE -ne 0) { throw 'Audio coefficient generator failed' }
$mode = if ($Port.Trim()) { 'hrd' } else { 'sim' }
$dest = Join-Path ('videos/' + $mode) ('audio_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$args = @('host/audio_dsp.py', '--source', $Source, '--out', $dest, '--start', "$Start", '--seconds', "$Seconds")
if ($Port.Trim()) {
  Write-Host 'IMPORTANT: New v0.9 bitstream REQUIRED for hardware audio mode.'
  $args += @('--port', $Port)
}
python @args
if ($LASTEXITCODE -ne 0) { throw 'Audio FIR run failed; no hardware claim permitted' }
Write-Host "AUDIO_DEMO_COMPLETE: $dest"
