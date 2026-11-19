# Builds dist\FracturedSpaceOfflineSetup.exe using the C# compiler that ships with Windows
# (.NET Framework 4.x). No extra tools needed.
#   powershell -ExecutionPolicy Bypass -File build.ps1
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

$refs = '/r:System.dll', '/r:System.Core.dll', '/r:System.Drawing.dll', '/r:System.Windows.Forms.dll', '/r:System.Web.Extensions.dll', '/r:Microsoft.CSharp.dll'

# --- Launcher ---
$launcher = Join-Path $obj 'launcher.exe'
& $csc /nologo /target:winexe /optimize+ "/out:$launcher" "/win32icon:$ico" $refs (Join-Path $root 'src\Launcher\OfflineLauncher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed' }

# --- Installer (embeds launcher + data + client patch) ---
$patchRes = Get-ChildItem (Join-Path $root 'patch') -File | ForEach-Object { "/resource:$($_.FullName),patch/$($_.Name)" }
$setup = Join-Path $dist 'FracturedSpaceOfflineSetup.exe'
& $csc /nologo /target:winexe /optimize+ "/out:$setup" "/win32icon:$ico" $refs `
    "/resource:$launcher,launcher.exe" $patchRes `
    "/resource:$(Join-Path $root 'server\responses.json'),responses.json" `
    "/resource:$(Join-Path $root 'LICENSE'),LICENSE" `
    "/resource:$(Join-Path $root 'src\Launcher\README.txt'),README.txt" `
    (Join-Path $root 'src\Installer\Installer.cs')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }

Get-Item $setup | Select-Object FullName, Length

# --- Linux AppImage (needs Python 3) ---
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    & $py.Source (Join-Path $root 'linux\build_appimage.py')
    if ($LASTEXITCODE -ne 0) { throw 'AppImage build failed' }
} else {
    Write-Warning 'Python 3 not found: skipping the Linux AppImage'
}
