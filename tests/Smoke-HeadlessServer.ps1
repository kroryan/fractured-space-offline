param([switch]$CoopMode)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$game = $env:FSO_GAME_DIR
if (-not $game) { $game = 'C:\Program Files (x86)\Steam\steamapps\common\Space' }
$bin = Join-Path $game 'spacegame\Binaries\Win64'
$server = Join-Path $bin 'spserver_original.exe'
if (-not (Test-Path $server)) { $server = Join-Path $bin 'spserver.exe' }
if (-not (Test-Path $server)) { throw 'Install Fractured Space or set FSO_GAME_DIR.' }
$tmp = Join-Path $root 'obj\headless-server-smoke'
New-Item -ItemType Directory -Force $tmp | Out-Null
$out = Join-Path $tmp 'stdout.log'; $err = Join-Path $tmp 'stderr.log'; $log = Join-Path $tmp 'server.log'
Remove-Item $out,$err,$log -Force -ErrorAction SilentlyContinue
$gameMode = 'spacegame.SinglePlayerLobbyGameMode'
$expectedClass = "Game class is 'SinglePlayerLobbyGameMode'"
$expectedState = $null
if ($CoopMode) {
    $map = '/Game/Maps/ActionConquest/Map_ActionConquest_A3_B6'
    $gameMode = '/Game/Blueprints/GameModes/BP_ConquestGameMode_Coop.BP_ConquestGameMode_Coop_C'
    $expectedClass = "Game class is 'BP_ConquestGameMode_Coop_C'"
    $expectedState = 'Match State Changed from WaitingToStart to InProgress'
}
$map = if ($map) { $map } else { '/Game/Maps/Lobby' }
$args = @($map + '?game=' + $gameMode, '-nullrhi', '-unattended', '-log',
          "-abslog=$log", '-port=17777', '-multihome=127.0.0.1')
$p = Start-Process -FilePath $server -ArgumentList $args -WorkingDirectory $bin -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $out -RedirectStandardError $err
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline -and -not $p.HasExited) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $log) {
            $text = Get-Content $log -Raw -ErrorAction SilentlyContinue
            $readyMarker = $CoopMode -or $text -match 'lobby_ready'
            $managerOk = -not $CoopMode -or $text -notmatch 'CommunicationManager blueprint not found in level'
            if ($readyMarker -and $text -match [regex]::Escape($expectedClass) -and
                $text -match 'IpNetDriver listening on port 17777' -and
                $managerOk -and
                (-not $expectedState -or $text -match [regex]::Escape($expectedState))) {
                $ready = $true; break
            }
        }
        $p.Refresh()
    }
    if (-not $ready) { throw 'Server did not reach lobby_ready on the expected test port; inspect obj/headless-server-smoke/.' }
    Write-Output $(if ($CoopMode) { 'Headless co-op game mode loaded and UDP driver listened on port 17777.' } else { 'Headless Solo vs AI smoke test passed (lobby_ready and UDP game driver listening on port 17777).' })
}
finally {
    $p.Refresh()
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
}
