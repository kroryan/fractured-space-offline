$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$tmp = Join-Path $root 'obj\fireline-identity-smoke'
New-Item -ItemType Directory -Force $tmp | Out-Null
$players = @(
    @{ name = 'player-a'; id = '11111111-1111-4111-8111-111111111111'; port = 18080 },
    @{ name = 'player-b'; id = '22222222-2222-4222-8222-222222222222'; port = 18081 }
)
$procs = @()
try {
    foreach ($p in $players) {
        $dir = Join-Path $tmp $p.name
        New-Item -ItemType Directory -Force $dir | Out-Null
        Copy-Item (Join-Path $root 'obj\launcher.exe') (Join-Path $dir 'launcher.exe') -Force
        Copy-Item (Join-Path $root 'server\responses.json') (Join-Path $dir 'responses.json') -Force
        Set-Content -NoNewline -Path (Join-Path $dir 'player-id.txt') -Value $p.id
        $procs += Start-Process (Join-Path $dir 'launcher.exe') -ArgumentList "--serve-only --port $($p.port)" `
            -WorkingDirectory $dir -WindowStyle Hidden -PassThru
    }
    Start-Sleep -Seconds 2
    foreach ($p in $players) {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$($p.port)/auth/oauth2/token" -Method Post -TimeoutSec 5 -UseBasicParsing
        $json = $response.Content
        if ($json -notmatch [regex]::Escape($p.id)) { throw "Response for $($p.name) did not contain its identity: $json" }
        if ($json -match '197a97fc-4179-43f4-b009-9432ac0c8e53') { throw "Response for $($p.name) retained the recorded identity." }
        $token = ($json | ConvertFrom-Json).refresh_token
        $payload = $token.Split('.')[1].Replace('-', '+').Replace('_', '/')
        while (($payload.Length % 4) -ne 0) { $payload += '=' }
        $packed = [Convert]::FromBase64String($payload)
        $input = New-Object IO.MemoryStream(,$packed[2..($packed.Length - 5)])
        $deflate = New-Object IO.Compression.DeflateStream($input, [IO.Compression.CompressionMode]::Decompress)
        $output = New-Object IO.MemoryStream
        $deflate.CopyTo($output)
        $refreshClaims = [Text.Encoding]::UTF8.GetString($output.ToArray())
        $deflate.Dispose(); $input.Dispose(); $output.Dispose()
        if ($refreshClaims -notmatch [regex]::Escape($p.id)) { throw "Refresh token for $($p.name) retained the recorded identity: $refreshClaims" }
    }
    Write-Output 'Fireline per-player identity smoke test passed.'
}
finally {
    foreach ($p in $procs) {
        $p.Refresh()
        if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
    }
}
