# Load each generated system through the engine's game-mode class resolver.
# The expected type rejection proves the class exists and was deserialized;
# this is not a spawn, combat, registration or game-mode test.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $root 'obj\expanse-runtime'
$bin = Join-Path $stage 'spacegame\Binaries\Win64'
$output = Join-Path $root ('obj\expanse-authoring\class-probes-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $output -Force | Out-Null
$targets = @()
foreach ($ship in @('Rocinante', 'Avalanche', 'Mayotte', 'Donnager', 'Chariot', 'Razorback', 'EpsteinYacht')) {
  foreach ($kind in @('System', 'Part', 'Data')) {
    $name = switch ($kind) { 'System' { "BP_SYS_EXP_$ship" }; 'Part' { "BP_SHP_EXP_${ship}_01" }; 'Data' { "Bp_Sys_ShipData_EXP_$ship" } }
    $folder = switch ($kind) { 'System' { 'Systems/Expanse' }; 'Part' { 'Parts/Expanse' }; 'Data' { 'Systems/ShipData' } }
    $class = "/Game/Blueprints/$folder/$name.${name}_C"
    $targets += @{ Kind=$kind; Ship=$ship; Class=$class }
  }
}
foreach ($folder in @('Turrets/Expanse', 'Systems/Subsystems/Expanse', 'Systems/Expanse', 'Parts/Expanse')) {
    Get-ChildItem -LiteralPath "$root\obj\expanse-authoring\patch-content\Content\Blueprints\$folder" -Filter '*.uasset' -File | ForEach-Object {
        $name = $_.BaseName
        if ($folder -in @('Systems/Expanse', 'Parts/Expanse') -and $name -notlike 'BP_FX_*') { return }
        $targets += @{ Kind='Weapon'; Ship=$name; Class="/Game/Blueprints/$folder/$name.${name}_C" }
    }
}
foreach ($target in $targets) {
    $kind, $ship, $class = $target.Kind, $target.Ship, $target.Class
    $log = Join-Path $output "$kind-$ship.log"
    if (Test-Path -LiteralPath $log) { throw "Existing probe log: $log" }
    $arguments = @("/Game/Maps/Lobby?game=$class", '-nullrhi', '-unattended', '-culture=en',
                   '-log', "-abslog=$log", '-port=17778', '-multihome=127.0.0.1')
    $process = Start-Process -FilePath "$bin\spserver_original.exe" -ArgumentList $arguments `
        -WorkingDirectory $bin -WindowStyle Hidden -PassThru
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        $found = $false
        while ([DateTime]::UtcNow -lt $deadline) {
            $process.Refresh()
            if (Test-Path -LiteralPath $log) {
                $text = Get-Content -LiteralPath $log -Raw
                $found = $text -and $text.Contains("BlueprintGeneratedClass $class is not a child class of Class /Script/Engine.GameModeBase")
                if ($found) { break }
            }
            if ($process.HasExited) { break }
            Start-Sleep -Milliseconds 300
        }
        if (-not $found) { throw "Native engine could not resolve $ship; inspect $log" }
        Write-Output "Native class resolved: $kind $ship (not gameplay validation)."
    } finally {
        $process.Refresh()
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    }
}
Write-Output "Native class evidence: $output"
