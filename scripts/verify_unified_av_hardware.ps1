<#
Run AFTER programming the matching dual-bank bitstream in Vivado Hardware Manager.
Do NOT leave the GUI open: it can hold the same UART port.
Example:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_unified_av_hardware.ps1 -Port COM4
#>
param(
  [Parameter(Mandatory=$true)][ValidatePattern('^(?i:COM\d+)$')][string]$Port,
  [string]$Source = 'videos\03_Unified_Quick_Test_3s.mp4',
  [switch]$SkipFullDemo
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$sourcePath = if ([IO.Path]::IsPathRooted($Source)) { $Source } else { Join-Path $root $Source }
if (!(Test-Path $sourcePath)) { throw "Video input missing: $sourcePath" }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$evidence = Join-Path $root "evidence\hardware\unified_av_$stamp"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$transcribing = $false
try {
  Start-Transcript -Path (Join-Path $evidence 'console_transcript.txt') | Out-Null
  $transcribing = $true
  Write-Host "TESTING_PHYSICAL_FPGA $Port"
  Write-Host 'This script does NOT program the board. Use new dual-bank bitstream first.'
  & python -m serial.tools.list_ports
  if ($LASTEXITCODE -ne 0) { throw 'pyserial/COM port discovery FAILED' }
  Write-Host '[1/2] Test motion FIR, audio FIR, audio mixed-sign, and return to motion coefficients'
  & python host/verify_dual_bank_fpga.py --port $Port --json-out (Join-Path $evidence 'physical_banks.json')
  if ($LASTEXITCODE -ne 0) { throw 'Dual-bank PHYSICAL FPGA verification FAILED. Do not claim hardware success.' }
  if (!$SkipFullDemo) {
    Write-Host '[2/2] One source MP4 -> physical FPGA X/Y/Roll and speech FIR -> unified MP4'
    $out = Join-Path $root "videos\hrd\unified_av_$stamp"
    & python host/unified_pipeline.py --video $sourcePath --out $out --port $Port --profile Normal --processing 'Video + Audio'
    if ($LASTEXITCODE -ne 0) { throw 'Combined physical video/audio processing FAILED' }
    $report = Join-Path $out 'combined_metrics.json'
    $video = Join-Path $out 'final_stabilised_filtered_audio.mp4'
    if (!(Test-Path $report) -or !(Test-Path $video)) { throw 'Physical output or combined metrics absent' }
    $metrics = Get-Content $report -Raw | ConvertFrom-Json
    if (!$metrics.both_hardware_verified -or $metrics.mode -ne 'PHYSICAL FPGA') {
      throw 'Combined report did not verify BOTH audio and video through physical FPGA'
    }
    Copy-Item $report -Destination (Join-Path $evidence 'combined_metrics.json') -Force
    Write-Host "COMBINED_VIDEO $video"
    Write-Host "COMBINED_METRICS $report"
    Write-Host 'UNIFIED_AV_PHYSICAL_FPGA_PASS - numerical bit-exact verification for video motion and audio; subjective quality evaluation remains separate.'
  } else {
    Write-Host 'Only dual-bank numeric smoke verified. Full video/audio hardware demonstration SKIPPED.'
  }
  $reports = Join-Path $root 'hardware\build\reports'
  if (Test-Path $reports) {
    New-Item -ItemType Directory -Force -Path (Join-Path $evidence 'vivado_reports') | Out-Null
    Copy-Item (Join-Path $reports '*.rpt') -Destination (Join-Path $evidence 'vivado_reports') -Force
  }
  Write-Host "PHYSICAL_EVIDENCE $evidence"
}
finally {
  if ($transcribing) { Stop-Transcript | Out-Null }
}
