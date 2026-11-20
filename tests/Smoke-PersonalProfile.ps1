$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $root
try {
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    & $csc /nologo /out:obj\ProfileTest.exe /r:System.Web.Extensions.dll src\Launcher\ProfileStore.cs tests\ProfileStoreSmoke.cs
    if ($LASTEXITCODE -ne 0) { throw 'Profile test compilation failed' }
    & obj\ProfileTest.exe (Join-Path $root ('obj\profile-test-' + [Guid]::NewGuid().ToString('N')))
    if ($LASTEXITCODE -ne 0) { throw 'Profile tests failed' }
} finally { Pop-Location }
