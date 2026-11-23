<# Open the ONE portable native Vivado .xpr. -Recreate regenerates it IN PLACE; close Vivado first. #>
param(
  [string]$VivadoBin = 'C:\AMDDesignTools\2025.2.1\Vivado\bin',
  [switch]$Recreate
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path $PSScriptRoot).Path
$vivado=Join-Path $VivadoBin 'vivado.bat'
if (!(Test-Path $vivado)) { throw "Vivado installation not found: $vivado" }
Set-Location $root
if ($Recreate) {
  & $vivado -mode batch -source .\hardware\vivado\create_maritime_vivado.tcl
  if ($LASTEXITCODE -ne 0) {throw 'Vivado project recreation failed'}
  $project=Join-Path $root 'hardware\build\maritime_a7.xpr'
} else {
  $project=Join-Path $root 'hardware\build\maritime_a7.xpr'
}
if (!(Test-Path $project)) {throw "Missing project: $project"}
Write-Host "OPENING_VIVADO_PROJECT $project"
& $vivado -mode gui -project $project
if ($LASTEXITCODE -ne 0) {throw "Vivado exit code $LASTEXITCODE"}
