$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
$tmp = Join-Path $root 'obj\coop-admission-smoke'
New-Item -ItemType Directory -Force $tmp | Out-Null
$harness = Join-Path $tmp 'Harness.cs'
@'
using System;
using System.IO;
using System.Net;
class Harness {
    static void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
    static int Main(string[] args) {
        string dir = args[0];
        string guests = Path.Combine(dir, "guests.json");
        string teams = Path.Combine(dir, "teams.json");
        using (var host = new CoopAdmission(IPAddress.Loopback, guests, teams, 3, 2, (peer, team) => true)) {
            var a = CoopAdmission.Request("127.0.0.1", "", 5000);
            var b = CoopAdmission.Request("127.0.0.1", "", 5000);
            Check(a.Team == 1, "First approved guest should fill the host's team capacity.");
            Check(b.Team == 2, "Second approved guest should fill the opposing team.");
            bool full = false;
            try { CoopAdmission.Request("127.0.0.1", "", 5000); }
            catch (InvalidOperationException) { full = true; }
            Check(full, "Admission must reject a guest after the selected capacity is reached.");
        }
        using (var host = new CoopAdmission(IPAddress.Loopback, guests, teams, 4, 1, (peer, team) => true)) {
            var a = CoopAdmission.Request("127.0.0.1", "", 5000);
            var b = CoopAdmission.Request("127.0.0.1", "", 5000);
            var c = CoopAdmission.Request("127.0.0.1", "", 5000);
            Check(a.Team == 2 && b.Team == 2 && c.Team == 2, "A host-only team must put every accepted guest on team 2.");
            bool full = false;
            try { CoopAdmission.Request("127.0.0.1", "", 5000); }
            catch (InvalidOperationException) { full = true; }
            Check(full, "Four-player capacity must reject a fifth human.");
        }
        Console.WriteLine("Co-op admission assignment and capacity smoke test passed.");
        return 0;
    }
}
'@ | Set-Content -Encoding ASCII $harness
$exe = Join-Path $tmp 'Harness.exe'
& $csc /nologo /target:exe "/out:$exe" /r:System.dll /r:System.Core.dll /r:System.Web.Extensions.dll `
    $harness (Join-Path $root 'src\Launcher\CoopAdmission.cs')
if ($LASTEXITCODE -ne 0) { throw 'Could not compile co-op admission smoke harness.' }
& $exe $tmp
if ($LASTEXITCODE -ne 0) { throw 'Co-op admission smoke test failed.' }
