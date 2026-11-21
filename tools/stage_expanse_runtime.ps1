param([string]$Game = 'C:\Program Files (x86)\Steam\steamapps\common\Space')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
$stage = Join-Path $root 'obj\expanse-runtime'
if (Test-Path -LiteralPath $stage) { throw 'Runtime staging already exists; inspect it before creating another staging tree.' }
New-Item -ItemType Directory -Path "$stage\spacegame\Content\Paks" -Force | Out-Null
# Shared directories are read-only inputs for the test process. Do not run an
# installer or authoring mutation against this staging tree.
New-Item -ItemType Junction -Path "$stage\Engine" -Target "$Game\Engine" | Out-Null
New-Item -ItemType Junction -Path "$stage\spacegame\Plugins" -Target "$Game\spacegame\Plugins" | Out-Null
Copy-Item -LiteralPath "$Game\spacegame\Binaries" -Destination "$stage\spacegame\Binaries" -Recurse
Get-ChildItem -LiteralPath "$Game\spacegame" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination "$stage\spacegame"
}
Get-ChildItem -LiteralPath "$Game\spacegame\Content" -Directory | Where-Object Name -ne 'Paks' | ForEach-Object {
    New-Item -ItemType Junction -Path (Join-Path "$stage\spacegame\Content" $_.Name) -Target $_.FullName | Out-Null
}
Get-ChildItem -LiteralPath "$Game\spacegame\Content\Paks" -File | Where-Object Name -ne 'FSO_Expanse_Experimental_P.pak' | ForEach-Object {
    New-Item -ItemType HardLink -Path (Join-Path "$stage\spacegame\Content\Paks" $_.Name) -Target $_.FullName | Out-Null
}
Copy-Item -LiteralPath "$root\obj\expanse-authoring\FSO_Expanse_Experimental_P.pak" -Destination "$stage\spacegame\Content\Paks"
Write-Output "Created isolated runtime tree: $stage"
