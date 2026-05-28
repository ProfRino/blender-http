<#
.SYNOPSIS
    Install the Blender HTTP add-on into Blender's user_default extensions folder.

.EXAMPLE
    .\install.ps1
    .\install.ps1 -BlenderVersion 5.2
#>
param(
    [string]$BlenderVersion = "5.1"
)

$ErrorActionPreference = "Stop"
$src = Join-Path $PSScriptRoot "blender_http"
if (-not (Test-Path $src)) { throw "Source folder not found: $src" }

$dst = Join-Path $env:APPDATA "Blender Foundation\Blender\$BlenderVersion\extensions\user_default\blender_http"
$parent = Split-Path $dst -Parent
if (-not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
if (Test-Path $dst) {
    Write-Host "Removing existing install at $dst" -ForegroundColor DarkYellow
    Remove-Item -Recurse -Force $dst
}
Copy-Item -Recurse $src $dst
Write-Host ""
Write-Host "Installed Blender HTTP to:" -ForegroundColor Green
Write-Host "  $dst"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open (or restart) Blender $BlenderVersion"
Write-Host "  2. Edit > Preferences > Add-ons, search 'Blender HTTP', enable it"
Write-Host "  3. In the 3D Viewport, press N, click the 'HTTP' tab, click Start"
Write-Host "  4. Test: python client\send.py examples\01_simple_cube.py"
