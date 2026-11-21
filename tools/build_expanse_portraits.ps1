$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
$blender = Join-Path $root 'obj\tooling\blender-4.2.23-windows-x64\blender.exe'
$ships = Get-Content -LiteralPath "$root\mods\expanse\fleet.json" -Raw | ConvertFrom-Json
foreach ($ship in $ships) {
    $folder = Join-Path $root "obj\expanse-authoring\$($ship.workshop_id)"
    $name = $ship.display_name -replace '[^A-Za-z0-9_]', '_'
    & $blender -b -t 2 "$folder\$name.blend" --python-exit-code 1 --python "$PSScriptRoot\render_expanse_portrait.py" -- $ship.slug *> "$folder\portrait-render.log"
    if ($LASTEXITCODE -ne 0) { throw "Portrait render failed: $($ship.slug)" }
    Write-Output "Rendered selector images: $($ship.display_name)"
}
