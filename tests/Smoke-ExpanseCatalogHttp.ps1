$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $root 'obj\expanse-authoring\backend-test'
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item -LiteralPath "$root\obj\launcher.exe" -Destination "$stage\launcher.exe" -Force
Copy-Item -LiteralPath "$root\obj\expanse-authoring\candidate-responses.json" -Destination "$stage\responses.json" -Force
$process = Start-Process -FilePath "$stage\launcher.exe" -ArgumentList '--serve-only --port 18082' `
    -WorkingDirectory $stage -WindowStyle Hidden -PassThru
try {
    Start-Sleep -Seconds 2
    $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Uri 'http://127.0.0.1:18082/o/ship_tree_table/18ace861-958b-36b2-8a14-ec1f9cc37677'
    $catalog = $response.Content | ConvertFrom-Json
    $encoded = $catalog.blob.Replace('-', '+').Replace('_', '/')
    while ($encoded.Length % 4) { $encoded += '=' }
    $packed = [Convert]::FromBase64String($encoded)
    $input = New-Object IO.MemoryStream(,$packed[2..($packed.Length - 5)])
    $deflate = New-Object IO.Compression.DeflateStream($input, [IO.Compression.CompressionMode]::Decompress)
    $decoded = New-Object IO.MemoryStream
    try {
        $deflate.CopyTo($decoded)
        if ($decoded.Length -ne $catalog.decompressedSize) { throw 'Served catalog length mismatch.' }
        $fleet = [Text.Encoding]::UTF8.GetString($decoded.ToArray()) | ConvertFrom-Json
        if ($fleet.ships.Count -ne 43) { throw 'Served catalog does not contain 43 ships.' }
        foreach ($name in @('Rocinante', 'MCRN Avalanche', 'UNN Mayotte', 'MCRN Donnager', 'MCRN Chariot-Type Dropship', 'Razorback', "Epstein's Yacht")) {
            if (-not ($fleet.ships | Where-Object name -eq $name)) { throw "Missing served ship: $name" }
        }
    } finally {
        $deflate.Dispose(); $input.Dispose(); $decoded.Dispose()
    }
    Write-Output 'Local Fireline HTTP catalog served and decompressed: all seven additional ships present.'
} finally {
    $process.Refresh()
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
}
