param(
    [string]$Dotnet = "$PSScriptRoot\..\obj\tooling\dotnet\dotnet.exe",
    [string]$Tool = "$PSScriptRoot\FleetAssetTool\bin\Debug\net10.0\FleetAssetTool.dll"
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
$base = Join-Path $root 'obj\expanse-review\base-blueprints'
$output = Join-Path $root 'obj\expanse-authoring\patch-content\Content\Blueprints'
& python "$PSScriptRoot\prepare_expanse_drives.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare source drive positions.' }

$ships = @(
    @{ Slug='rocinante'; System='BP_SYS_M02_MID_C28_Interceptor'; Data='Bp_Sys_ShipData_ship_M02_C28_Interceptor'; Part='BP_SHP_MID_M02_C28_Interceptor_01'; PartFolder='M02'; MeshPath='/Game/Ships/M02/C28/SM_M02_C28_A'; MeshObject='SM_M02_C28_A'; Mesh='Rocinante'; Collision='/Game/Meshes/ShipCollision/SM_COLL_Interceptor'; CollisionObject='SM_COLL_Interceptor' },
    @{ Slug='avalanche'; System='BP_SYS_M01_C14_Destroyer'; Data='Bp_Sys_ShipData_ship_M01_C14_Destroyer_A'; Part='BP_SHP_M01_LRG_C14_A_001_DESTROYER_2'; PartFolder='M01'; MeshPath='/Game/Ships/M01/C14/SM_M01_C14'; MeshObject='SM_M01_C14'; Mesh='MCRN_Avalanche'; Collision='/Game/Meshes/ShipCollision/SM_COLL_Destroyer'; CollisionObject='SM_COLL_Destroyer' },
    @{ Slug='mayotte'; System='BP_SYS_M01_LRG_CO1_Flagship'; Data='Bp_Sys_ShipData_ship_M01_C01_Flagship'; Part='BP_SHP_M01_LRG_C02_A_001_FLAGSHIP'; PartFolder='M01'; MeshPath='/Game/Ships/M01/C02/A/SM_M01_C02A'; MeshObject='SM_M01_C02A'; Mesh='UNN_Mayotte'; Collision='/Game/Meshes/ShipCollision/SM_COLL_Colossus'; CollisionObject='SM_COLL_Colossus' },
    @{ Slug='donnager'; System='BP_SYS_M01_LRG_CO1_Flagship'; Data='Bp_Sys_ShipData_ship_M01_C01_Flagship'; Part='BP_SHP_M01_LRG_C02_A_001_FLAGSHIP'; PartFolder='M01'; MeshPath='/Game/Ships/M01/C02/A/SM_M01_C02A'; MeshObject='SM_M01_C02A'; Mesh='MCRN_Donnager'; Collision='/Game/Meshes/ShipCollision/SM_COLL_Colossus'; CollisionObject='SM_COLL_Colossus' },
    @{ Slug='chariot'; System='BP_SYS_M02_SML_C07_Corvette_A'; Data='Bp_Sys_ShipData_ship_M02_C07_Corvette'; Part='BP_SHP_SML_M02_C07_Corvette_01'; PartFolder='M02'; MeshPath='/Game/Ships/M02/C05/SM_M02_C05_1A_A'; MeshObject='SM_M02_C05_1A_A'; Mesh='MCRN_Chariot_Type_Dropship'; Collision='/Game/Meshes/ShipCollision/SM_COLL_Protector'; CollisionObject='SM_COLL_Protector' },
    @{ Slug='razorback'; System='BP_SYS_M02_MID_C28_Interceptor'; Data='Bp_Sys_ShipData_ship_M02_C28_Interceptor'; Part='BP_SHP_MID_M02_C28_Interceptor_01'; PartFolder='M02'; MeshPath='/Game/Ships/M02/C28/SM_M02_C28_A'; MeshObject='SM_M02_C28_A'; Mesh='Razorback'; Collision='/Game/Meshes/ShipCollision/SM_COLL_Interceptor'; CollisionObject='SM_COLL_Interceptor' },
    @{ Slug='epstein_yacht'; System='BP_SYS_M02_MID_C28_Interceptor'; Data='Bp_Sys_ShipData_ship_M02_C28_Interceptor'; Part='BP_SHP_MID_M02_C28_Interceptor_01'; PartFolder='M02'; MeshPath='/Game/Ships/M02/C28/SM_M02_C28_A'; MeshObject='SM_M02_C28_A'; Mesh='Epstein_s_Yacht'; Collision='/Game/Meshes/ShipCollision/SM_COLL_Interceptor'; CollisionObject='SM_COLL_Interceptor' }
)

function Invoke-Clone([string]$Source, [string]$Destination, [string[]]$Changes) {
    & $Dotnet $Tool clone $Source $Destination @Changes
    if ($LASTEXITCODE -ne 0) { throw "Could not clone $Source" }
}

# The native railgun already uses Ballistic hardpoints. Adapt its grade to the
# capital-hull primary mounts while retaining native aiming, recoil and effects.
Invoke-Clone (Join-Path $base 'Systems\Subsystems\BP_SYS_WEAP_PRJ_LR_Interceptor_Railgun_test.uasset') `
    (Join-Path $output 'Systems\Subsystems\Expanse\BP_SYS_EXP_HeavyRailgun.uasset') @(
        '/Game/Blueprints/Systems/Subsystems/BP_SYS_WEAP_PRJ_LR_Interceptor_Railgun_test=/Game/Blueprints/Systems/Subsystems/Expanse/BP_SYS_EXP_HeavyRailgun',
        'BP_SYS_WEAP_PRJ_LR_Interceptor_Railgun_test=BP_SYS_EXP_HeavyRailgun',
        'EHardpointGrade::HARDPOINTGRADE_2=EHardpointGrade::HARDPOINTGRADE_1'
    )
$railgun = Join-Path $output 'Systems\Subsystems\Expanse\BP_SYS_EXP_HeavyRailgun.uasset'
& $Dotnet $Tool tune $railgun $railgun "$root\mods\expanse\balance\heavy_railgun.json"
if ($LASTEXITCODE -ne 0) { throw 'Could not tune capital-ship railgun.' }

foreach ($ship in $ships) {
    $title = (Get-Culture).TextInfo.ToTitleCase($ship.Slug).Replace('_', '')
    $system = "BP_SYS_EXP_$title"
    $data = "Bp_Sys_ShipData_EXP_$title"
    $part = "BP_SHP_EXP_${title}_01"
    $partSource = Join-Path $base "Parts\$($ship.PartFolder)\$($ship.Part).uasset"
    $partDestination = Join-Path $output "Parts\Expanse\$part.uasset"
    $systemDestination = Join-Path $output "Systems\Expanse\$system.uasset"
    $dataDestination = Join-Path $output "Systems\ShipData\$data.uasset"
    $armour = switch ($ship.Slug) {
        'avalanche' { 'SM_ARM_Destroyer' }
        'mayotte' { 'SM_ARM_Flagship' }
        'donnager' { 'SM_ARM_Flagship' }
        'chariot' { 'SM_ARM_CORVETTE' }
        default { 'SM_ARM_Interceptor' }
    }

    Invoke-Clone $partSource $partDestination @(
        "/Game/Blueprints/Parts/$($ship.PartFolder)/$($ship.Part)=/Game/Blueprints/Parts/Expanse/$part",
        "/Game/Meshes/Armour/Merged/$armour=/Game/Expanse/$($ship.Mesh)/SM_ARM_EXP_$($ship.Mesh)",
        "$armour=SM_ARM_EXP_$($ship.Mesh)",
        "$($ship.MeshPath)=/Game/Expanse/$($ship.Mesh)/$($ship.Mesh)",
        "$($ship.MeshObject)=$($ship.Mesh)",
        "$($ship.Part)=$part"
    )
    Invoke-Clone (Join-Path $base "Systems\$($ship.System).uasset") $systemDestination @(
        "/Game/Blueprints/Systems/$($ship.System)=/Game/Blueprints/Systems/Expanse/$system",
        "/Game/Blueprints/Parts/$($ship.PartFolder)/$($ship.Part)=/Game/Blueprints/Parts/Expanse/$part",
        "$($ship.Part)=$part",
        "$($ship.System)=$system"
    )
    Invoke-Clone (Join-Path $base "Systems\ShipData\$($ship.Data).uasset") $dataDestination @(
        "$($ship.Collision)=/Game/Expanse/$($ship.Mesh)/$($ship.Mesh)",
        "$($ship.CollisionObject)=$($ship.Mesh)",
        "$($ship.Data)=$data"
    )
    $vectors = Join-Path $root "mods\expanse\attachments\$($ship.Slug).json"
    $balance = Join-Path $root "mods\expanse\balance\$($ship.Slug).json"
    & $Dotnet $Tool tune $dataDestination $dataDestination $balance
    if ($LASTEXITCODE -ne 0) { throw "Could not tune ship data for $($ship.Slug)" }
    if (Test-Path -LiteralPath $vectors) {
        & $Dotnet $Tool vectors $partDestination $partDestination $vectors
        if ($LASTEXITCODE -ne 0) { throw "Could not adjust attachments for $($ship.Slug)" }
    }
    $fleetSpec = Get-Content -LiteralPath "$root\mods\expanse\fleet.json" -Raw | ConvertFrom-Json |
        Where-Object slug -eq $ship.Slug
    $drives = Join-Path $root "obj\expanse-authoring\$($fleetSpec.workshop_id)\drive-positions.json"
    if ((Get-Content -LiteralPath $drives -Raw | ConvertFrom-Json).Count -gt 0) {
        & $Dotnet $Tool drives $partDestination $partDestination $drives
        if ($LASTEXITCODE -ne 0) { throw "Could not map native drive effects for $($ship.Slug)" }
    }
}

Write-Output "Generated independent system, ship-data and hull-part assets for $($ships.Count) ships."
& python "$PSScriptRoot\build_rocinante_pdc.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not bind original Rocinante PDC meshes and mounts.' }
& python "$PSScriptRoot\build_donnager_weapons.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not bind original Donnager weapon meshes and mounts.' }
& python "$PSScriptRoot\build_razorback_weapon.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not bind requested Razorback light cannon.' }
& python "$PSScriptRoot\build_mayotte_weapons.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not bind original Mayotte weapons.' }
& python "$PSScriptRoot\build_escort_weapons.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not bind original Avalanche and Chariot cannons.' }
& python "$PSScriptRoot\build_rocinante_torpedoes.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not bind source-hatch torpedo launch sites.' }
& python "$PSScriptRoot\build_expanse_effects.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not adapt hull effects to the imported geometry.' }
