# Run with Windows PowerShell 5.1: inspect the .NET Framework installer without
# executing its entry point or installing/updating any game files.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $root 'dist\FracturedSpaceOfflineSetup-ExpanseTest.exe'
$assembly = [Reflection.Assembly]::LoadFile($installer)
$patch = $assembly.GetType('Setup').GetField('Patch', [Reflection.BindingFlags]'Public,Static').GetValue($null)
$manifest = Get-Content -LiteralPath "$root\obj\expanse-authoring\fleet-manifest.json" -Raw | ConvertFrom-Json
if ($manifest.Count -ne 44) { throw 'Expected mandatory PAK, notices and six selector images for each of seven ships.' }
foreach ($source in @($manifest | ForEach-Object src)) {
    $entry = @($patch | Where-Object Src -eq $source)
    if ($entry.Count -ne 1) { throw "Fleet payload is not in the mandatory installer manifest: $source" }
    $stream = $assembly.GetManifestResourceStream('patch/' + $source)
    if ($null -eq $stream) { throw "Missing embedded fleet resource: $source" }
    $hash = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
        if ($digest -ne $entry[0].Sha256) { throw "Embedded resource does not match installer hash: $source" }
    } finally { $stream.Dispose(); $hash.Dispose() }
}
$stream = $assembly.GetManifestResourceStream('responses.json')
$hash = [Security.Cryptography.SHA256]::Create()
try {
    $digest = ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath "$root\obj\expanse-authoring\candidate-responses.json").Hash.ToLowerInvariant()
    if ($digest -ne $expected) { throw 'Installer does not embed the candidate fleet catalog.' }
} finally { $stream.Dispose(); $hash.Dispose() }
Write-Output 'Installer mandatory PAK, asset notices, 42 selector images and candidate catalog verified without installation.'
