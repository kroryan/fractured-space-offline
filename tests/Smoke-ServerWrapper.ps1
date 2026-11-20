$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
$wrapper = Join-Path $root 'obj\spserver-wrapper.exe'
if (-not (Test-Path $wrapper)) { throw 'Run build.ps1 first to compile spserver-wrapper.exe.' }
$tmp = Join-Path $root 'obj\wrapper-smoke'
New-Item -ItemType Directory -Force $tmp | Out-Null
Copy-Item $wrapper (Join-Path $tmp 'wrapper.exe') -Force
$fakeSource = Join-Path $tmp 'FakeServer.cs'
@'
using System;
class FakeServer {
    static int Main(string[] args) {
        Console.WriteLine("LogNet: GameNetDriver IpNetDriver_0 IpNetDriver listening on port 7777");
        Console.WriteLine("ARGS=" + String.Join("|", args));
        return 0;
    }
}
'@ | Set-Content -Encoding ASCII $fakeSource
$fakeExe = Join-Path $tmp 'spserver_original.exe'
& $csc /nologo /target:exe "/out:$fakeExe" $fakeSource
if ($LASTEXITCODE -ne 0) { throw 'Could not compile fake server.' }
$env:FSO_COOP_MODE = 'host'
$env:FSO_SERVER_URL_EXTRA = '?coop=0?team1Players=2?team2Players=1'
$env:FSO_COOP_TEAM = '1'
$env:FSO_COOP_STATUS = Join-Path $tmp 'status.txt'
try {
    $output = & (Join-Path $tmp 'wrapper.exe') '/Game/Maps/Lobby?game=spacegame.SinglePlayerLobbyGameMode' '-log' 2>&1
    $text = $output -join "`n"
    foreach ($expected in @('lobby_ready', 'ecg_fs_sp_server_host=127.0.0.1', 'ecg_fs_sp_server_port=7777?Team=1', '/Game/Maps/ActionConquest/Map_ActionConquest_A3_B6', 'BP_ConquestGameMode_Coop_C', 'coop=0?team1Players=2?team2Players=1', '-multihome=127.0.0.1')) {
        if ($text -notmatch [regex]::Escape($expected)) { throw "Wrapper output did not include: $expected`n$text" }
    }
    if (-not (Test-Path $env:FSO_COOP_STATUS)) { throw 'Wrapper did not write host status.' }
    $env:FSO_COOP_MODE = 'guest'
    $env:FSO_COOP_HOST = '10.0.0.2'
    $env:FSO_COOP_TEAM = '2'
    $guestOut = Join-Path $tmp 'guest.stdout.log'
    $guestErr = Join-Path $tmp 'guest.stderr.log'
    Remove-Item $guestOut,$guestErr -Force -ErrorAction SilentlyContinue
    $guest = Start-Process -FilePath (Join-Path $tmp 'wrapper.exe') -WorkingDirectory $tmp -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $guestOut -RedirectStandardError $guestErr
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(5)
        do { Start-Sleep -Milliseconds 100; $text = if (Test-Path $guestOut) { Get-Content $guestOut -Raw } else { '' } }
        while ([DateTime]::UtcNow -lt $deadline -and $text -notmatch 'ecg_fs_sp_server_port=7777\?Team=2')
        foreach ($expected in @('ecg_fs_sp_server_host=10.0.0.2', 'ecg_fs_sp_server_port=7777?Team=2')) {
            if ($text -notmatch [regex]::Escape($expected)) { throw "Guest wrapper output did not include: $expected`n$text" }
        }
        if ((Get-Content $env:FSO_COOP_STATUS -Raw) -notmatch 'team 2') { throw 'Guest status did not retain the selected team.' }
    }
    finally { if (-not $guest.HasExited) { Stop-Process -Id $guest.Id -Force } }
    Write-Output 'Server wrapper smoke test passed.'
}
finally {
    Remove-Item Env:FSO_COOP_MODE, Env:FSO_SERVER_URL_EXTRA, Env:FSO_COOP_TEAM, Env:FSO_COOP_STATUS, Env:FSO_COOP_HOST -ErrorAction SilentlyContinue
}
