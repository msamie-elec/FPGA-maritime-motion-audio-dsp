<## Final reproducible Windows/Vivado build and vectorless power-report collection. ##>
param(
  [string]$VivadoBin = 'C:\AMDDesignTools\2025.2.1\Vivado\bin',
  [switch]$SkipGuiTests
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$exe = Join-Path $VivadoBin 'vivado.bat'
if (!(Test-Path $exe)) { throw "Vivado not found: $exe" }
if (!(Test-Path '.\hardware\rtl\audio_coefficients.svh')) { throw 'Dual coefficient-bank RTL missing' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$ev = Join-Path $root "evidence\final_validation\build_$stamp"
New-Item -ItemType Directory -Force -Path $ev | Out-Null
$transcribing = $false
try {
  Start-Transcript (Join-Path $ev 'console_transcript.txt') | Out-Null
  $transcribing = $true
  Write-Host "RELEASE_BUILD_SOURCE $root"
  if (!$SkipGuiTests) {
    Write-Host '[1/5] Python GUI + unified AV regression'
    & powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Python regression failed; build stopped' }
    & python -m pytest -q .\verification\system\tests\test_release_validation_tools.py
    if ($LASTEXITCODE -ne 0) { throw 'Engineering validation utility self-tests failed; build stopped' }
  } else { Write-Host 'WARNING: Python GUI regression SKIPPED' }
  # Preserve previously generated Vivado project and reports for provenance.
  $existing = Join-Path $root 'hardware\build'
  # A single tracked .xpr remains in hardware/build. Archive generated runs only.
  $generated = @(Get-ChildItem -LiteralPath $existing -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notin @('maritime_a7.xpr','README.md') })
  if ($generated.Count -gt 0) {
    $archive = Join-Path $root "evidence\local_build_archive\build_$stamp"
    New-Item -ItemType Directory -Force -Path $archive | Out-Null
    foreach ($item in $generated) { Move-Item -LiteralPath $item.FullName -Destination $archive }
    Write-Host "ARCHIVED_GENERATED_BUILD_OUTPUT $archive"
  }
  Write-Host '[2/5] XSim + synthesis + P&R + bitstream'
  & powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_unified_av_fpga.ps1 -VivadoBin $VivadoBin -SkipSoftwareTests
  if ($LASTEXITCODE -ne 0) { throw 'Unified Vivado build failed' }
  $bit = Join-Path $root 'hardware\build\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit'
  if (!(Test-Path $bit)) { throw "Missing new .bit: $bit" }
  Write-Host '[3/5] Post-route timing / DRC / power / methodology / clock interaction'
  & $exe -mode batch -source .\hardware\vivado\postroute_release_reports.tcl
  if ($LASTEXITCODE -ne 0) { throw 'Vivado post-route release reports failed' }
  $rpt = Join-Path $root 'hardware\build\reports'
  Copy-Item (Join-Path $rpt '*') -Destination $ev -Recurse -Force
  Write-Host '[4/5] Static report triage'
  & python .\scripts\summarize_release_reports.py --report-dir $rpt --json (Join-Path $ev 'report_summary.json') --markdown (Join-Path $ev 'report_summary.md')
  if ($LASTEXITCODE -ne 0) { throw 'Report summary failed' }
  $review = Get-Content (Join-Path $ev 'report_summary.json') -Raw | ConvertFrom-Json
  if ($review.internal_timing_met -ne $true) { throw 'Internal routed timing NOT PROVEN (missing or negative slack). Preserve reports; STOP BEFORE PROGRAMMING.' }
  if (!$review.drc_report_present) { throw 'DRC report missing; STOP BEFORE PROGRAMMING.' }
  if ($null -eq $review.estimated_power_w) { Write-Warning 'Power number not parsed: inspect power_routed_vectorless.rpt; DO NOT claim power estimate.' }
  if ($review.unconstrained_io_mentioned) { Write-Warning 'Unconstrained external I/O indicated: review UART/reset interface; internal timing PASS is not full I/O sign-off.' }
  if ($review.drc_rules.Count -gt 0) { Write-Warning 'DRC rules reported: check every instance. No waiver is implicit.' }
  $blockingRules = @($review.drc_rules | Where-Object { $_.rule -in @('REQP-1840','CFGBVS-1') })
  if ($blockingRules.Count -gt 0) {
    $names = ($blockingRules | ForEach-Object { $_.rule }) -join ', '
    throw "RELEASE_DRC_BLOCKED: $names still reported. Reports are saved at $ev. Do not program or tag a release until investigated."
  }
  Write-Host 'RELEASE_DRC_SAFETY_GATE_PASS: REQP-1840 and CFGBVS-1 absent (other advisories require review).'

  Write-Host '[5/5] Provenance manifest'
  # Generate reproducible analytical evidence separately from routed/physical results.
  & python .\verification\model\industrial_filter_assessment.py
  if ($LASTEXITCODE -ne 0) { throw 'Coefficient/bit-exact model assessment failed' }
  & python .\host\engineering_summary.py
  if ($LASTEXITCODE -ne 0) { throw 'Engineering summary export failed' }

  $srcFiles = @('hardware\rtl\fir_sequential.sv','hardware\rtl\fir_job_controller.sv','hardware\rtl\arty_a7_maritime_top.sv','hardware\rtl\audio_coefficients.svh','hardware\rtl\fir_coefficients.svh','hardware\constraints\arty_a7_35_maritime.xdc')
  $manifest = [ordered]@{
    captured_at = (Get-Date).ToString('o');
    board='Arty A7-35T'; target_part='xc7a35ticsg324-1L';
    new_bitfile=$bit; bit_sha256=(Get-FileHash $bit -Algorithm SHA256).Hash;
    source_hashes=@{}; github_commit='NOT_VERIFIED_FROM_LOCAL_CHECKOUT';
    build_completed=$true; board_programmed=$false; physical_tests='NOT_RUN';
    power_type='POST_ROUTE_VECTORLESS_ESTIMATE_NOT_MEASURED';
    evidence_dir=$ev
  }
  foreach($p in $srcFiles){if(Test-Path $p){$manifest.source_hashes[$p]=(Get-FileHash $p -Algorithm SHA256).Hash}}
  try {$gitHead = (& git rev-parse HEAD 2>$null); if($LASTEXITCODE -eq 0){$manifest.github_commit=$gitHead.Trim()}} catch {}
  $manifest | ConvertTo-Json -Depth 6 | Out-File (Join-Path $ev 'build_manifest.json') -Encoding UTF8
  Write-Host "FINAL_REBUILD_REPORTS_COMPLETE $ev"
  Write-Host "BITSTREAM_FILE $bit"
  Write-Host 'Program THIS exact bitstream using Vivado Hardware Manager. No board has been programmed by this script.'
} finally {
  if ($transcribing) { Stop-Transcript | Out-Null }
}
