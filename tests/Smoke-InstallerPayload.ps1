# Windows PowerShell 5.1: inspect resources without running the installer.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$assembly = [Reflection.Assembly]::LoadFile((Join-Path $root 'dist\FracturedSpaceOfflineSetup.exe'))
if ($assembly.GetName().Version.ToString() -ne '1.5.0.0') { throw 'Incorrect installer version.' }
$patch = $assembly.GetType('Setup').GetField('Patch', [Reflection.BindingFlags]'Public,Static').GetValue($null)
foreach ($entry in $patch) {
    $stream = $assembly.GetManifestResourceStream('patch/' + $entry.Src)
    if ($null -eq $stream) { throw "Missing embedded patch file: $($entry.Src)" }
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
        if ($digest -ne $entry.Sha256) { throw "Installer payload mismatch: $($entry.Src)" }
    } finally { $stream.Dispose(); $sha.Dispose() }
}
$stream = $assembly.GetManifestResourceStream('responses.json')
$reader = New-Object IO.StreamReader $stream
try { $records = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
$bundle = @($records | Where-Object { $_.request.url.EndsWith('/licenses/bundle/check') })
if ($bundle.Count -ne 1 -or ($bundle[0].response.content | ConvertFrom-Json).licenses.Count -ne 697) {
    throw 'Missing updated bundle entitlements.'
}
if ($assembly.GetManifestResourceNames() -match 'Expanse|fleet-manifest') { throw 'Main installer contains a test fleet.' }
Write-Output "Normal v1.5.0 installer: $($patch.Count) embedded patch hashes and updated entitlements verified without installation."
