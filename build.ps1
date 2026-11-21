# Builds dist\FracturedSpaceOfflineSetup.exe using the C# compiler that ships with Windows
# (.NET Framework 4.x). No extra tools needed.
#   powershell -ExecutionPolicy Bypass -File build.ps1
param([switch]$LocalFleet)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $root 'dist'
$obj  = Join-Path $root 'obj'
New-Item -ItemType Directory -Force $dist, $obj | Out-Null

$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path $csc)) { throw 'csc.exe (.NET Framework 4.x) not found' }

# --- Icon (generated, multi-size PNG .ico) ---
$ico = Join-Path $root 'assets\app.ico'
if (-not (Test-Path $ico)) {
    Add-Type -AssemblyName System.Drawing
    $sizes = 256, 48, 32, 16
    $pngs = foreach ($s in $sizes) {
        $bmp = New-Object System.Drawing.Bitmap $s, $s
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.SmoothingMode = 'AntiAlias'; $g.TextRenderingHint = 'AntiAliasGridFit'
        $rect = New-Object System.Drawing.RectangleF 0, 0, $s, $s
        $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush $rect, ([System.Drawing.Color]::FromArgb(255, 18, 24, 48)), ([System.Drawing.Color]::FromArgb(255, 8, 10, 20)), 45
        $g.FillEllipse($bg, 0, 0, $s - 1, $s - 1)
        $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 255, 140, 0)), ([Math]::Max(1, $s / 24))
        $g.DrawEllipse($pen, $s * 0.04, $s * 0.04, $s * 0.92, $s * 0.92)
        # stylised ship: a wedge
        $pts = [System.Drawing.PointF[]]@(
            (New-Object System.Drawing.PointF ($s * 0.22), ($s * 0.70)),
            (New-Object System.Drawing.PointF ($s * 0.78), ($s * 0.30)),
            (New-Object System.Drawing.PointF ($s * 0.60), ($s * 0.72)),
            (New-Object System.Drawing.PointF ($s * 0.48), ($s * 0.56)))
        $g.FillPolygon((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 255, 160, 40))), $pts)
        $g.Dispose()
        $ms = New-Object IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
        , $ms.ToArray()
    }
    $out = New-Object IO.MemoryStream
    $w = New-Object IO.BinaryWriter $out
    $w.Write([UInt16]0); $w.Write([UInt16]1); $w.Write([UInt16]$sizes.Count)
    $offset = 6 + 16 * $sizes.Count
    for ($i = 0; $i -lt $sizes.Count; $i++) {
        $d = if ($sizes[$i] -ge 256) { 0 } else { $sizes[$i] }
        $w.Write([byte]$d); $w.Write([byte]$d); $w.Write([byte]0); $w.Write([byte]0)
        $w.Write([UInt16]1); $w.Write([UInt16]32)
        $w.Write([UInt32]$pngs[$i].Length); $w.Write([UInt32]$offset)
        $offset += $pngs[$i].Length
    }
    foreach ($p in $pngs) { $w.Write($p) }
    $w.Flush(); [IO.File]::WriteAllBytes($ico, $out.ToArray())
}

$refs = '/r:System.dll', '/r:System.Core.dll', '/r:System.Drawing.dll', '/r:System.Windows.Forms.dll', '/r:System.Web.Extensions.dll', '/r:System.Web.dll', '/r:System.IO.Compression.dll', '/r:System.IO.Compression.FileSystem.dll', '/r:Microsoft.CSharp.dll'

# --- In-game DirectX 11 F1 menu ---
& cmd /c (Join-Path $root 'src\Overlay\build.bat')
if ($LASTEXITCODE -ne 0) { throw 'F1 overlay build failed' }
Copy-Item (Join-Path $root 'src\Overlay\build\fso_offline_menu.dll') (Join-Path $obj 'fso_offline_menu.dll') -Force

# --- Launcher ---
$launcher = Join-Path $obj 'launcher.exe'
& $csc /nologo /target:winexe /platform:x64 /optimize+ "/out:$launcher" "/win32icon:$ico" $refs (Join-Path $root 'src\Launcher\OfflineLauncher.cs') (Join-Path $root 'src\Launcher\CoopAdmission.cs') (Join-Path $root 'src\Launcher\UdpRelay.cs') (Join-Path $root 'src\Launcher\ProfileStore.cs') (Join-Path $root 'src\Launcher\MatchRecorder.cs') (Join-Path $root 'src\Launcher\OverlayLoader.cs') (Join-Path $root 'src\Launcher\TrainerBridge.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed' }

# --- Dedicated server wrapper (installed beside the original spserver.exe) ---
$wrapper = Join-Path $obj 'spserver-wrapper.exe'
& $csc /nologo /target:exe /optimize+ "/out:$wrapper" $refs (Join-Path $root 'src\ServerWrapper\ServerWrapper.cs')
if ($LASTEXITCODE -ne 0) { throw 'Server wrapper build failed' }

# --- Trainer engine, embedded for fully offline installation ---
Add-Type -AssemblyName System.IO.Compression.FileSystem
$trainerZip = Join-Path $obj 'trainer.zip'
if (Test-Path $trainerZip) { Remove-Item -LiteralPath $trainerZip }
[IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $root 'src\Trainer'), $trainerZip)

# --- Installer (embeds launcher + data + client patch) ---
$patchRes = Get-ChildItem (Join-Path $root 'patch') -File | ForEach-Object { "/resource:$($_.FullName),patch/$($_.Name)" }
$responses = Join-Path $root 'server\responses.json'
if ($LocalFleet) {
    $fleetFolder = Join-Path $obj 'expanse-authoring'
    if (-not (Test-Path -LiteralPath (Join-Path $fleetFolder 'fleet-manifest.json'))) {
        $fleetFolder = Join-Path $root 'mods\expanse\payload'
    }
    $fleet = Join-Path $fleetFolder 'FSO_Expanse_Experimental_P.pak'
    $manifest = Join-Path $fleetFolder 'fleet-manifest.json'
    $responses = Join-Path $fleetFolder 'candidate-responses.json'
    if (-not (Test-Path -LiteralPath $fleet) -and (Test-Path -LiteralPath (Join-Path $fleetFolder 'pak-parts.json'))) {
        & python (Join-Path $root 'tools\restore_expanse_payload.py')
        if ($LASTEXITCODE -ne 0) { throw 'Could not restore cooked fleet payload.' }
    }
    foreach ($required in @($fleet, $manifest, $responses)) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Missing local fleet input: $required" }
    }
    foreach ($entry in (Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json)) {
        $payload = Join-Path $fleetFolder $entry.src
        if (-not (Test-Path -LiteralPath $payload)) { throw "Missing local fleet resource: $payload" }
        $patchRes += "/resource:$payload,patch/$($entry.src)"
    }
    $patchRes += "/resource:$manifest,fleet-manifest.json"
}
$setup = Join-Path $dist 'FracturedSpaceOfflineSetup.exe'
if ($LocalFleet) { $setup = Join-Path $dist 'FracturedSpaceOfflineSetup-ExpanseTest.exe' }
& $csc /nologo /target:winexe /optimize+ "/out:$setup" "/win32icon:$ico" $refs `
    "/resource:$launcher,launcher.exe" "/resource:$(Join-Path $obj 'fso_offline_menu.dll'),fso_offline_menu.dll" $patchRes `
    "/resource:$trainerZip,trainer.zip" `
    "/resource:$wrapper,spserver-wrapper.exe" `
    "/resource:$responses,responses.json" `
    "/resource:$(Join-Path $root 'LICENSE'),LICENSE" `
    "/resource:$(Join-Path $root 'NOTICE.md'),NOTICE.md" `
    "/resource:$(Join-Path $root 'src\Overlay\third_party\LICENSES.md'),overlay-licenses.md" `
    "/resource:$(Join-Path $root 'src\Overlay\third_party\minhook\LICENSE.txt'),minhook-license.txt" `
    "/resource:$(Join-Path $root 'src\Launcher\README.txt'),README.txt" `
    (Join-Path $root 'src\Installer\Installer.cs')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }

Get-Item $setup | Select-Object FullName, Length

# --- Linux AppImage (needs Python 3) ---
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $linuxArgs = @((Join-Path $root 'linux\build_appimage.py'))
    if ($LocalFleet) { $linuxArgs += '--local-fleet' }
    & $py.Source @linuxArgs
    if ($LASTEXITCODE -ne 0) { throw 'AppImage build failed' }
} elseif (-not $LocalFleet) {
    Write-Warning 'Python 3 not found: skipping the Linux AppImage'
}
if ($LocalFleet -and $py) {
    & $py.Source (Join-Path $root 'tools\write_expanse_checksums.py')
    if ($LASTEXITCODE -ne 0) { throw 'Local fleet test checksum generation failed' }
}
