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
        Console.WriteLine("lobby_ready");
        Console.WriteLine("ecg_fs_sp_server_host=127.0.0.1");
        Console.WriteLine("ecg_fs_sp_server_port=7777");
        Console.WriteLine("ARGS=" + String.Join("|", args));
        return 0;
    }
}
'@ | Set-Content -Encoding ASCII $fakeSource
$fakeExe = Join-Path $tmp 'spserver_original.exe'
& $csc /nologo /target:exe "/out:$fakeExe" $fakeSource
if ($LASTEXITCODE -ne 0) { throw 'Could not compile fake server.' }
$env:FSO_COOP_MODE = 'host'
$env:FSO_SERVER_URL_EXTRA = '?coop=1'
$env:FSO_COOP_STATUS = Join-Path $tmp 'status.txt'
try {
    $output = & (Join-Path $tmp 'wrapper.exe') '/Game/Maps/Lobby?game=spacegame.SinglePlayerLobbyGameMode' '-log' 2>&1
    $text = $output -join "`n"
    foreach ($expected in @('lobby_ready', 'ecg_fs_sp_server_port=7777', '/Game/Maps/ActionConquest/Map_ActionConquest_A3_B6', 'BP_ConquestGameMode_Coop_C', 'coop=1', '-multihome=127.0.0.1')) {
        if ($text -notmatch [regex]::Escape($expected)) { throw "Wrapper output did not include: $expected`n$text" }
    }
    if (-not (Test-Path $env:FSO_COOP_STATUS)) { throw 'Wrapper did not write host status.' }
    Write-Output 'Server wrapper smoke test passed.'
}
finally {
    Remove-Item Env:FSO_COOP_MODE, Env:FSO_SERVER_URL_EXTRA, Env:FSO_COOP_STATUS -ErrorAction SilentlyContinue
}
