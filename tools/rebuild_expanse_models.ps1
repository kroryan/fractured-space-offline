param([string]$Unreal = 'C:\Program Files\Epic Games\UE_4.19\Engine\Binaries\Win64\UE4Editor-Cmd.exe', [switch]$SkipExport,
      [string[]]$Ship)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
$blender = Join-Path $root 'obj\tooling\blender-4.2.23-windows-x64\blender.exe'
$project = Join-Path $root 'obj\expanse-authoring\UnrealProject'
$jobs = @(
    @('2211361535', 210000), @('2224316655', 260000),
    @('2368610280', 180000), @('2375119898', 350000),
    @('2375181309', 180000), @('2687045417', 350000), @('2687094193', 300000)
)
foreach ($job in $jobs) {
    if ($Ship -and $job[0] -notin $Ship) { continue }
    $folder = Join-Path $root "obj\expanse-authoring\$($job[0])"
    $env:EXPANSE_TRIANGLE_BUDGET = [string]$job[1]
    if (-not $SkipExport) {
        & $blender -b -t 2 --python-exit-code 1 --python "$PSScriptRoot\blender_expanse.py" -- "$folder\prepared.json" *> "$folder\axis-rebuild-blender.log"
        if ($LASTEXITCODE -ne 0) { throw "Export failed: $($job[0])" }
    }
    & python "$PSScriptRoot\create_expanse_project.py" --ship $job[0] *> "$folder\axis-project.log"
    if ($LASTEXITCODE -ne 0) { throw "Import settings failed: $($job[0])" }
    # UE4.19's atomic FBX reimport retains the old UFbxAssetImportData settings.
    # Archive only the generated mesh package so the explicit import settings
    # apply to a fresh package. Materials/textures and source FBX stay intact.
    $metadata = Get-Content -LiteralPath "$folder\prepared.json" -Raw | ConvertFrom-Json
    $meshName = $metadata.display_name -replace '[^A-Za-z0-9_]', '_'
    $settings = Get-Content -LiteralPath "$project\import-settings.json" -Raw | ConvertFrom-Json
    foreach ($group in $settings.ImportGroups) {
      foreach ($fbx in $group.Filenames) {
    $generatedName = [IO.Path]::GetFileNameWithoutExtension($fbx)
    $meshPath = Join-Path $project ("Content\" + $group.DestinationPath.Substring('/Game/'.Length).Replace('/', '\') + "\$generatedName.uasset")
    if (Test-Path -LiteralPath $meshPath) {
        $resolved = (Resolve-Path -LiteralPath $meshPath).Path
        if (-not $resolved.StartsWith($project + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Generated mesh escaped authoring project.'
        }
        $archive = Join-Path $folder 'previous-imports'
        New-Item -ItemType Directory -Path $archive -Force | Out-Null
        $archived = Join-Path $archive ($generatedName + '-' + [Guid]::NewGuid().ToString('N') + '.uasset')
        Move-Item -LiteralPath $resolved -Destination $archived
    }
      }
    }
    $env:OPENSSL_ia32cap = ':~0x20000000'
    & $Unreal "$project\spacegame.uproject" -run=ImportAssets "-importsettings=$project\import-settings.json" `
        -dest=/Game/Expanse -nosourcecontrol -unattended -nop4 -nosplash -nullrhi -culture=en `
        "-abslog=$folder\axis-import.log" *> "$folder\axis-import-console.log"
    if ($LASTEXITCODE -ne 0) { throw "Import failed: $($job[0])" }
    Write-Output "Rebuilt and imported reviewed axes: $($job[0])"
}
& $Unreal "$project\spacegame.uproject" -run=Cook -TargetPlatform=WindowsNoEditor -CookDir=Expanse `
    -unattended -nop4 -nosplash -nullrhi -culture=en "-abslog=$root\obj\expanse-authoring\axis-cook.log" `
    *> "$root\obj\expanse-authoring\axis-cook-console.log"
if ($LASTEXITCODE -ne 0) { throw 'Cooking corrected models failed.' }
Write-Output 'Corrected fleet models cooked successfully.'
