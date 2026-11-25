# Inspect the launcher without starting it. A restored original executable must
# produce a repair message, while the expected offline executable must pass.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$assembly = [Reflection.Assembly]::LoadFile((Join-Path $root 'obj\launcher.exe'))
$method = $assembly.GetType('OfflineLauncher').GetMethod('GetPatchError', [Reflection.BindingFlags]'NonPublic,Static')
$type = $assembly.GetType('OfflineLauncher')
$flags = [Reflection.BindingFlags]'NonPublic,Static'
if ($type.GetField('launchNonce', $flags).GetValue($null) -eq $type.GetField('menuToken', $flags).GetValue($null)) {
    throw 'Public launch-state nonce must be independent of the F1 control token.'
}
$valid = Join-Path $root 'patch\Fractured Space.exe'
if ($null -ne $method.Invoke($null, [object[]]@([string]$valid))) { throw 'Offline executable was rejected.' }
$restored = Join-Path $root 'obj\restore-guard-original.exe'
try {
    [IO.File]::WriteAllText($restored, 'restored executable does not contain the offline patch')
    $message = $method.Invoke($null, [object[]]@([string]$restored))
    if (-not $message.Contains('no longer matches the offline patch') -or -not $message.Contains('run the installer')) {
        throw 'Restored executable did not produce an actionable repair message.'
    }
} finally { Remove-Item -LiteralPath $restored -ErrorAction SilentlyContinue }
Write-Output 'Offline executable accepted; restored executable blocked with repair instructions.'
