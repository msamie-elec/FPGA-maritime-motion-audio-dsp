<#
Build integrated Arty A7 video-motion + speech-audio dual-bank bitstream.
From project root:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_unified_av_fpga.ps1
The physical device is NOT programmed by this command.
#>
param(
  [string]$VivadoBin = 'C:\AMDDesignTools\2025.2.1\Vivado\bin',
  [switch]$SkipSoftwareTests
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$vivado = Join-Path $VivadoBin 'vivado.bat'
if (!(Test-Path $vivado)) { throw "Missing Vivado installation: $vivado" }
if (!(Test-Path 'rtl\audio_coefficients.svh')) { throw 'Missing audio coefficient ROM; this is not the dual-bank source' }
$env:PATH = "$VivadoBin;$env:PATH"
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$evidence = Join-Path $root "evidence\build\$stamp"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$log = Join-Path $evidence 'build_transcript.txt'
$transcribing = $false
try {
  Start-Transcript -Path $log | Out-Null
  $transcribing = $true
  Write-Host "SOURCE_ROOT $root"
  Write-Host "VIVADO $vivado"
  Write-Host 'IMPORTANT: Close any Vivado GUI project pointing to this build directory before continuing.'
  Write-Host '[1/4] Check deterministic motion/audio RTL coefficient banks'
  & python host/design_audio_coefficients.py
  if ($LASTEXITCODE -ne 0) { throw 'Failed to generate audio coefficient ROM' }
  if (!$SkipSoftwareTests) {
    Write-Host '[2/4] Run software regression in two groups'
    & python -m pytest -q tests/test_fixed_point.py tests/test_serial_protocol.py tests/test_synthetic_maritime.py tests/test_gui_pipeline.py tests/test_natural_footage.py tests/test_three_axis_v07.py tests/test_gui_playback.py tests/test_gui_audio_playback_v102.py tests/test_long_media_v082.py tests/test_audio_fir_v09.py tests/test_dual_bank_physical_verifier.py
    if ($LASTEXITCODE -ne 0) { throw 'Software regression group 1 FAILED' }
    & python -m pytest -q tests/test_unified_pipeline_v10.py
    if ($LASTEXITCODE -ne 0) { throw 'Software regression group 2 FAILED' }
  } else {
    Write-Host '[2/4] SKIPPED host tests by user option; this does not indicate a verified software build.'
  }
  Write-Host '[3/4] Vivado XSim: UART + dual-bank FIR + bank switching'
  & powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_maritime_xsim.ps1
  if ($LASTEXITCODE -ne 0) { throw 'Vivado XSim FAILED; stop before implementation' }
  Write-Host '[4/4] Vivado synthesis, place/route, bitstream and post-route reports'
  & $vivado -mode batch -source scripts/build_maritime_bitstream.tcl
  if ($LASTEXITCODE -ne 0) { throw 'Vivado synthesis/implementation FAILED' }
  $bit = Join-Path $root 'build\vivado_maritime_a7\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit'
  if (!(Test-Path $bit)) { throw "Expected bitstream missing: $bit" }
  $reportDir = Join-Path $root 'build\vivado_maritime_a7\reports'
  foreach ($rpt in @('utilization_routed.rpt', 'timing_routed.rpt', 'drc_routed.rpt')) {
    $p = Join-Path $reportDir $rpt
    if (!(Test-Path $p)) { throw "Missing implementation report: $p" }
    Copy-Item $p -Destination (Join-Path $evidence $rpt) -Force
  }
  $hash = (Get-FileHash $bit -Algorithm SHA256).Hash
  $manifest = [ordered]@{
     date = (Get-Date).ToString('o'); source_root = $root;
     bitstream = $bit; bitstream_sha256 = $hash;
     serial_baud = 115200; platform = 'Arty A7-35T';
     hardware_programmed = $false; physical_verification = 'PENDING';
     note = 'Bitstream created, not yet programmed; routed timing/DRC still require engineering review.'
  }
  $manifest | ConvertTo-Json -Depth 4 | Out-File (Join-Path $evidence 'manifest.json') -Encoding UTF8
  Write-Host "BITSTREAM_AVAILABLE $bit"
  Write-Host "BITSTREAM_SHA256 $hash"
  Write-Host "ROUTED_REPORTS $reportDir"
  Write-Host "EVIDENCE_FOLDER $evidence"
  Write-Host 'UNIFIED_AV_BUILD_DONE - program this exact bitstream via Vivado Hardware Manager, then run verify_unified_av_hardware.ps1'
}
finally {
  if ($transcribing) { Stop-Transcript | Out-Null }
}
