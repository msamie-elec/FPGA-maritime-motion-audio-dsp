param(
  [Parameter(Mandatory=$true)][string]$RunDir,
  [string]$OutputDir=''
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if (!(Test-Path $RunDir -PathType Container)) {throw "Full-system run directory not found: $RunDir"}
$argsList=@('.\verification\system\media_quality_assessment.py','--run-dir',$RunDir)
if ($OutputDir) { $argsList += @('--out',$OutputDir) }
& python @argsList
if ($LASTEXITCODE -ne 0) {throw 'Media quality assessment failed'}
Write-Host 'STAGE_RESOLVED_MEDIA_QUALITY_COMPLETE; NO NEW FPGA IMPLEMENTATION'
