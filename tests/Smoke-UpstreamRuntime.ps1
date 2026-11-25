# Use a workspace-only stage; never patch the installed game for a smoke test.
param([string]$Game = 'C:\Program Files (x86)\Steam\steamapps\common\Space')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $root ('obj\upstream-runtime-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path "$stage\Engine", "$stage\spacegame\Content\Paks", "$stage\backend" -Force | Out-Null
Get-ChildItem -LiteralPath "$Game\Engine" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination "$stage\Engine"
}
foreach ($folder in Get-ChildItem -LiteralPath "$Game\Engine" -Directory) {
    if ($folder.Name -eq 'Config') {
        Copy-Item -LiteralPath $folder.FullName -Destination "$stage\Engine\Config" -Recurse
    } else {
        New-Item -ItemType Junction -Path (Join-Path "$stage\Engine" $folder.Name) -Target $folder.FullName | Out-Null
    }
}
New-Item -ItemType Junction -Path "$stage\spacegame\Plugins" -Target "$Game\spacegame\Plugins" | Out-Null
Copy-Item -LiteralPath "$Game\spacegame\Binaries" -Destination "$stage\spacegame\Binaries" -Recurse
Get-ChildItem -LiteralPath "$Game\spacegame" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination "$stage\spacegame"
}
foreach ($folder in Get-ChildItem -LiteralPath "$Game\spacegame\Content" -Directory) {
    if ($folder.Name -eq 'Paks') { continue }
    if ($folder.Name -eq 'UIResources') {
        Copy-Item -LiteralPath $folder.FullName -Destination "$stage\spacegame\Content\UIResources" -Recurse
    } else {
        New-Item -ItemType Junction -Path (Join-Path "$stage\spacegame\Content" $folder.Name) -Target $folder.FullName | Out-Null
    }
}
$retired = @('BP.pak', 'Makichika_MapJamming_P.pak', 'Makichika_ProtectorShield_P.pak', 'Makichika_VenturerSkins_P.pak', 'FSO_Expanse_Experimental_P.pak')
Get-ChildItem -LiteralPath "$Game\spacegame\Content\Paks" -File | Where-Object Name -notin $retired | ForEach-Object {
    New-Item -ItemType HardLink -Path (Join-Path "$stage\spacegame\Content\Paks" $_.Name) -Target $_.FullName | Out-Null
}
$lock = Get-Content -LiteralPath "$root\tools\bootstrapper-lock.json" -Raw | ConvertFrom-Json
foreach ($file in $lock.files) {
    $dest = Join-Path $stage $file.destination
    if (-not (Test-Path -LiteralPath (Split-Path $dest))) { throw "Missing stage destination: $dest" }
    Copy-Item -LiteralPath (Join-Path "$root\patch" $file.file) -Destination $dest -Force
}
Copy-Item -LiteralPath "$root\obj\launcher.exe" -Destination "$stage\backend\launcher.exe"
Copy-Item -LiteralPath "$root\server\responses.json" -Destination "$stage\backend\responses.json"
$backend = Start-Process -FilePath "$stage\backend\launcher.exe" -ArgumentList '--serve-only --port 18084' `
    -WorkingDirectory "$stage\backend" -WindowStyle Hidden -PassThru
$client = $null
try {
    Start-Sleep -Seconds 1
    $check = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:18084/bootstrapper/launch-check' -TimeoutSec 5
    $nonce = ($check.Content | ConvertFrom-Json).nonce
    if (-not $nonce -or $check.Headers['Access-Control-Allow-Origin'] -ne '*') { throw 'Invalid launch-check response.' }
    @{offline=$true; check='http://127.0.0.1:18084/bootstrapper/launch-check'; nonce=$nonce} | ConvertTo-Json -Compress |
        Set-Content -Encoding UTF8 -LiteralPath "$stage\spacegame\Content\UIResources\frontend\views\gamemodes\bootstrapper-launch.json"
    $env:SteamAppId='310380'
    $env:OPENSSL_ia32cap=':~0x20000000'
    $log = Join-Path $stage 'client.log'
    $client = Start-Process -FilePath "$stage\spacegame\Binaries\Win64\Fractured Space.exe" `
        -ArgumentList @('-flhost=http://127.0.0.1:18084', '-discord=offline', '-culture=en-GB', '-windowed', '-ResX=1280', '-ResY=720', "-abslog=$log") `
        -WorkingDirectory "$stage\spacegame\Binaries\Win64" -WindowStyle Hidden -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(55)
    $success = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if (Test-Path -LiteralPath $log) {
            $text = Get-Content -LiteralPath $log -Raw
            if ($text -match 'Login was True') { $success = $true; break }
            if ($text -match 'Login was False|Fatal error:') { break }
        }
        $client.Refresh()
        if ($client.HasExited) { break }
    }
    if (-not $success) { throw "Updated native client did not log in; inspect $stage" }
    Start-Sleep -Seconds 4
    $text = Get-Content -LiteralPath $log -Raw
    if ($text -match 'ReferenceError: Can.t find variable: (DataStore|utils|GameModeConfig)|SyntaxError:') {
        throw "Game UI script failure; inspect $stage"
    }
    Write-Output "Updated native client logged into local backend; evidence: $stage"
} finally {
    if ($client) { $client.Refresh(); if (-not $client.HasExited) { Stop-Process -Id $client.Id -Force } }
    $backend.Refresh(); if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
}
