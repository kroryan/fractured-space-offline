// Fractured Space Offline - Installer / Uninstaller
// - Lets the user pick the Fractured Space game folder (auto-detects Steam)
// - Applies the community patch (files downloaded from Tigerhacker/fractured-bootstrapper,
//   pinned commit, verified by SHA-256; originals backed up)
// - Installs "Fractured Space Bootstrapper Offline" (launcher + local Fireline emulator)
//   with Start Menu / Desktop shortcuts and an entry in Settings > Apps
// Run with /uninstall to remove it.
// UI is English, or Spanish when Windows is in Spanish.
// C# 5 (compiled with .NET Framework csc).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("Fractured Space Offline Setup")]
[assembly: AssemblyProduct("Fractured Space Offline")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

static class Setup
{
    public const string AppName = "Fractured Space Bootstrapper Offline";
    public const string AppVersion = "1.0.0";
    public const string AppExe = "FracturedSpaceBootstrapperOffline.exe";
    public const string RegKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\FracturedSpaceBootstrapperOffline";
    public const string DpiKey = @"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers";
    public const string PatchCommit = "0b89d9e97d03734a9411f389b58a4d7eed21ea32";
    public const string PatchBase = "https://raw.githubusercontent.com/Tigerhacker/fractured-bootstrapper/" + PatchCommit + "/data/";
    public const int PatchLevel = 30;
    public const string BackupDirName = "fractured-offline-backup";
    public const string GameExeRel = @"spacegame\Binaries\Win64\Fractured Space.exe";

    public static readonly bool Spanish =
        System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es";
    public static string L(string es, string en) { return Spanish ? es : en; }

    public static string InstallDir
    {
        get
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                @"Programs\fractured-space-bootstrapper-offline");
        }
    }

    public class PatchFile
    {
        public string Src, Dest, Sha256; public bool Text;
        public PatchFile(string src, string dest, string sha, bool text) { Src = src; Dest = dest; Sha256 = sha; Text = text; }
    }

    public static readonly PatchFile[] Patch = new[]
    {
        new PatchFile("Fractured Space.exe", GameExeRel, "fa6288c2d914366e14175c1d9ebbb459f6bd605c348b6148e9eea33d7290bc2a", false),
        new PatchFile("ClientConfig.json", @"spacegame\ClientConfig.json", "0087a651ad5fbb235fa438b8d3a3f47cf2f6b11b3f88c528f82c48ccdc8d4b91", true),
        new PatchFile("startgame-script.js", @"spacegame\Content\UIResources\frontend\views\startgame\startgame-script.js", "bac58eaa7f06a1b2401e5300e0141739055736bfb66d285e28b0096b83bcc1bb", true),
        new PatchFile("startgame-style.css", @"spacegame\Content\UIResources\frontend\views\startgame\startgame-style.css", "49e856f3667e0c22db18a8c864c62ae66f1e1e2940d0efb783955ea6e0460301", true),
        new PatchFile("gamemodes-config.js", @"spacegame\Content\UIResources\frontend\views\gamemodes\gamemodes-config.js", "7d864d2985f05b81cd37199c4150652c4becf9c5cc253f160c2f38d7db7509bd", true),
        new PatchFile("nsloctext.js", @"spacegame\Content\UIResources\frontend\data\translations\nsloctext.js", "c1d43e513deb470d763b5d023db9275d3cde6bb689c45f1da110eb14ddd091af", true),
        new PatchFile("BP.pak", @"spacegame\Content\Paks\BP.pak", "cac460fbce8a33e8f155b9a4abd14c15981156978b3a2d420dc2b468399d1681", false),
        new PatchFile("results-script.js", @"spacegame\Content\UIResources\frontend\views\results\results-script.js", "ace5e5197f6779efd46531c0f08c6b2b7d963f3ee23533bcbea3c6ab7c710766", true),
        new PatchFile("hangar-script.js", @"spacegame\Content\UIResources\frontend\views\hangar\hangar-script.js", "b3290327dfa2c94af87a58aa13b3021706f5685f249edbcd1a34bbb40ff8eede", true),
    };

    [STAThread]
    static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; // TLS 1.2
        foreach (var a in args)
        {
            if (a.Equals("/uninstall", StringComparison.OrdinalIgnoreCase))
                return Uninstall();
        }
        Application.Run(new SetupForm());
        return 0;
    }

    // ---------- helpers ----------

    public static string Sha256File(string path)
    {
        using (var s = File.OpenRead(path))
        using (var h = SHA256.Create())
            return Hex(h.ComputeHash(s));
    }

    public static string Hex(byte[] b)
    {
        var sb = new StringBuilder(b.Length * 2);
        foreach (var x in b) sb.Append(x.ToString("x2"));
        return sb.ToString();
    }

    // Git stores the text files with LF; the original patch uses CRLF.
    public static byte[] ToCrlf(byte[] data)
    {
        var o = new List<byte>(data.Length + data.Length / 20);
        for (int i = 0; i < data.Length; i++)
        {
            if (data[i] == (byte)'\n' && (i == 0 || data[i - 1] != (byte)'\r')) o.Add((byte)'\r');
            o.Add(data[i]);
        }
        return o.ToArray();
    }

    public static bool IsGameFolder(string p)
    {
        return !string.IsNullOrEmpty(p) && Directory.Exists(Path.Combine(p, @"spacegame\Binaries\Win64"));
    }

    public static string DetectGame()
    {
        var libs = new List<string>();
        string steam = null;
        foreach (var view in new[] { @"SOFTWARE\Wow6432Node\Valve\Steam", @"SOFTWARE\Valve\Steam" })
        {
            try
            {
                using (var k = Registry.LocalMachine.OpenSubKey(view))
                    if (k != null && steam == null) steam = k.GetValue("InstallPath") as string;
            }
            catch { }
        }
        try
        {
            using (var k = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam"))
                if (k != null && steam == null)
                {
                    var sp = k.GetValue("SteamPath") as string;
                    if (sp != null) steam = sp.Replace('/', '\\');
                }
        }
        catch { }
        if (steam == null) steam = @"C:\Program Files (x86)\Steam";
        string steamapps = Path.Combine(steam, "steamapps");
        libs.Add(steamapps);
        try
        {
            string vdf = File.ReadAllText(Path.Combine(steamapps, "libraryfolders.vdf"));
            foreach (Match m in Regex.Matches(vdf, "\"path\"\\s+\"([^\"]+)\""))
                libs.Add(Path.Combine(m.Groups[1].Value.Replace("\\\\", "\\"), "steamapps"));
        }
        catch { }
        foreach (var l in libs)
        {
            string p = Path.Combine(l, @"common\Space");
            if (IsGameFolder(p)) return p;
        }
        return "";
    }

    public static byte[] Resource(string name)
    {
        using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
        using (var m = new MemoryStream())
        {
            s.CopyTo(m);
            return m.ToArray();
        }
    }

    public static void CreateShortcut(string lnk, string target, string workDir, string desc)
    {
        Type t = Type.GetTypeFromProgID("WScript.Shell");
        dynamic shell = Activator.CreateInstance(t);
        dynamic sc = shell.CreateShortcut(lnk);
        sc.TargetPath = target;
        sc.WorkingDirectory = workDir;
        sc.IconLocation = target + ",0";
        sc.Description = desc;
        sc.Save();
    }

    public static string DesktopLnk { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), AppName + ".lnk"); } }
    public static string StartLnk { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), AppName + ".lnk"); } }

    // ---------- uninstall ----------

    static int Uninstall()
    {
        if (MessageBox.Show(L("¿Desinstalar ", "Uninstall ") + AppName + "?", AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
            return 0;

        foreach (var p in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(AppExe)))
            try { p.Kill(); } catch { }

        string game = null;
        try { game = File.ReadAllText(Path.Combine(InstallDir, "gamepath.txt")).Trim(); } catch { }
        string backup = game == null ? null : Path.Combine(game, BackupDirName);
        if (backup != null && Directory.Exists(backup))
        {
            var r = MessageBox.Show(
                L("¿Restaurar también los archivos originales del juego?\n\n" +
                  "Sí: el juego vuelve a como estaba (el Bootstrapper online tendrá que volver a parchearlo).\n" +
                  "No: el juego queda parcheado (sigue funcionando con el Bootstrapper online).",
                  "Also restore the original game files?\n\n" +
                  "Yes: the game goes back to how it was (the online Bootstrapper will need to patch it again).\n" +
                  "No: the game stays patched (keeps working with the online Bootstrapper)."),
                AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Question);
            if (r == DialogResult.Yes)
            {
                try
                {
                    foreach (var f in Directory.GetFiles(backup, "*", SearchOption.AllDirectories))
                    {
                        string rel = f.Substring(backup.Length + 1);
                        string dest = Path.Combine(game, rel);
                        Directory.CreateDirectory(Path.GetDirectoryName(dest));
                        File.Copy(f, dest, true);
                    }
                    File.Delete(Path.Combine(game, "bootlegger.json"));
                    Directory.Delete(backup, true);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(L("No se pudieron restaurar todos los archivos:\n", "Could not restore all files:\n") + ex.Message, AppName);
                }
            }
        }

        try { File.Delete(DesktopLnk); } catch { }
        try { File.Delete(StartLnk); } catch { }
        try { Registry.CurrentUser.DeleteSubKeyTree(RegKey, false); } catch { }

        // Delete install folder after this process exits
        string dir = InstallDir;
        var psi = new ProcessStartInfo("cmd.exe", "/c timeout /t 2 /nobreak >nul & rmdir /s /q \"" + dir + "\"");
        psi.WindowStyle = ProcessWindowStyle.Hidden;
        psi.CreateNoWindow = true;
        psi.WorkingDirectory = Path.GetTempPath();
        Process.Start(psi);
        MessageBox.Show(AppName + L(" se ha desinstalado.", " has been uninstalled."), AppName, MessageBoxButtons.OK, MessageBoxIcon.Information);
        return 0;
    }
}

class SetupForm : Form
{
    static string L(string es, string en) { return Setup.L(es, en); }

    TextBox txtPath, txtLog;
    Button btnBrowse, btnInstall, btnClose;
    CheckBox chkDesktop;
    ProgressBar bar;
    bool installed;

    public SetupForm()
    {
        Text = L("Instalar Fractured Space Offline", "Fractured Space Offline Setup");
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(620, 430);
        Font = new Font("Segoe UI", 9f);

        var title = new Label { Text = "Fractured Space Offline", Font = new Font("Segoe UI", 15f, FontStyle.Bold), AutoSize = true, Location = new Point(16, 12) };
        var sub = new Label
        {
            Text = L("Juega a Fractured Space sin conexión contra bots, con un servidor local.\r\n" +
                     "Selecciona la carpeta del juego (la que contiene \"spacegame\") y pulsa Instalar.",
                     "Play Fractured Space offline against bots, using a local server.\r\n" +
                     "Select the game folder (the one containing \"spacegame\") and click Install."),
            AutoSize = true, Location = new Point(18, 48)
        };
        var lbl = new Label { Text = L("Carpeta del juego:", "Game folder:"), AutoSize = true, Location = new Point(18, 96) };
        txtPath = new TextBox { Location = new Point(18, 116), Width = 490, Text = Setup.DetectGame() };
        btnBrowse = new Button { Text = L("Examinar...", "Browse..."), Location = new Point(516, 114), Width = 88 };
        btnBrowse.Click += (s, e) => Browse();
        chkDesktop = new CheckBox { Text = L("Crear acceso directo en el escritorio", "Create a desktop shortcut"), Checked = true, AutoSize = true, Location = new Point(18, 148) };
        bar = new ProgressBar { Location = new Point(18, 178), Width = 586, Height = 18, Maximum = Setup.Patch.Length + 2 };
        txtLog = new TextBox { Location = new Point(18, 204), Width = 586, Height = 170, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, BackColor = SystemColors.Window };
        btnInstall = new Button { Text = L("Instalar", "Install"), Location = new Point(424, 388), Width = 88, Height = 28 };
        btnInstall.Click += (s, e) => StartInstall();
        btnClose = new Button { Text = L("Cerrar", "Close"), Location = new Point(516, 388), Width = 88, Height = 28 };
        btnClose.Click += (s, e) => Close();
        AcceptButton = btnInstall;

        Controls.AddRange(new Control[] { title, sub, lbl, txtPath, btnBrowse, chkDesktop, bar, txtLog, btnInstall, btnClose });
        Log(txtPath.Text.Length > 0
            ? L("Juego detectado en: ", "Game found at: ") + txtPath.Text
            : L("No se detectó el juego automáticamente. Pulsa Examinar.", "The game was not detected automatically. Click Browse."));
    }

    void Browse()
    {
        using (var d = new FolderBrowserDialog())
        {
            d.Description = L("Selecciona la carpeta de Fractured Space (normalmente ...\\steamapps\\common\\Space)",
                              "Select the Fractured Space folder (usually ...\\steamapps\\common\\Space)");
            if (Directory.Exists(txtPath.Text)) d.SelectedPath = txtPath.Text;
            if (d.ShowDialog(this) == DialogResult.OK)
            {
                string p = d.SelectedPath;
                // Accept selecting "spacegame" or deeper by walking up
                var dir = new DirectoryInfo(p);
                while (dir != null && !Setup.IsGameFolder(dir.FullName)) dir = dir.Parent;
                txtPath.Text = dir != null ? dir.FullName : p;
            }
        }
    }

    void Log(string s)
    {
        if (InvokeRequired) { BeginInvoke(new Action<string>(Log), s); return; }
        txtLog.AppendText(s + "\r\n");
    }

    void Step()
    {
        if (InvokeRequired) { BeginInvoke(new Action(Step)); return; }
        bar.Value = Math.Min(bar.Maximum, bar.Value + 1);
    }

    void StartInstall()
    {
        if (installed)
        {
            LaunchApp();
            return;
        }
        string game = txtPath.Text.Trim().TrimEnd('\\');
        if (!Setup.IsGameFolder(game))
        {
            MessageBox.Show(this, L("Esa carpeta no parece ser Fractured Space.\nDebe contener spacegame\\Binaries\\Win64.",
                                    "That folder does not look like Fractured Space.\nIt must contain spacegame\\Binaries\\Win64."),
                Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        if (Process.GetProcessesByName("Fractured Space").Length > 0)
        {
            MessageBox.Show(this, L("Cierra Fractured Space antes de instalar.", "Close Fractured Space before installing."),
                Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        btnInstall.Enabled = btnBrowse.Enabled = txtPath.Enabled = chkDesktop.Enabled = false;
        bar.Value = 0;
        bool desktop = chkDesktop.Checked;
        var t = new Thread(() => DoInstall(game, desktop)) { IsBackground = true };
        t.Start();
    }

    void DoInstall(string game, bool desktop)
    {
        try
        {
            PatchGame(game);
            InstallApp(game, desktop);
            Step();
            Log("");
            Log(L("¡Listo! Abre \"" + Setup.AppName + "\" desde el menú Inicio" + (desktop ? " o el escritorio" : "") + ".",
                  "Done! Open \"" + Setup.AppName + "\" from the Start menu" + (desktop ? " or the desktop" : "") + "."));
            Log(L("En el juego: Play -> Training -> Solo vs AI para jugar contra bots.",
                  "In game: Play -> Training -> Solo vs AI to play against bots."));
            BeginInvoke(new Action(() =>
            {
                installed = true;
                bar.Value = bar.Maximum;
                btnInstall.Text = L("Jugar", "Play");
                btnInstall.Enabled = true;
            }));
        }
        catch (UnauthorizedAccessException ex)
        {
            Log(L("ERROR: sin permiso para escribir: ", "ERROR: no permission to write: ") + ex.Message);
            Log(L("Ejecuta el instalador con clic derecho -> Ejecutar como administrador.",
                  "Run the installer with right click -> Run as administrator."));
            Reenable();
        }
        catch (Exception ex)
        {
            Log("ERROR: " + ex.Message);
            Reenable();
        }
    }

    void Reenable()
    {
        BeginInvoke(new Action(() => { btnInstall.Enabled = btnBrowse.Enabled = txtPath.Enabled = chkDesktop.Enabled = true; }));
    }

    void PatchGame(string game)
    {
        Log(L("Comprobando parche del juego...", "Checking game patch..."));
        string backup = Path.Combine(game, Setup.BackupDirName);
        using (var wc = new WebClient())
        {
            wc.Headers[HttpRequestHeader.UserAgent] = "fractured-space-offline-setup";
            foreach (var f in Setup.Patch)
            {
                string dest = Path.Combine(game, f.Dest);
                if (File.Exists(dest) && Setup.Sha256File(dest) == f.Sha256)
                {
                    Log(L("  OK (ya parcheado): ", "  OK (already patched): ") + f.Src);
                    Step();
                    continue;
                }
                Log(L("  Descargando ", "  Downloading ") + f.Src + "...");
                byte[] data = wc.DownloadData(Setup.PatchBase + Uri.EscapeDataString(f.Src));
                if (f.Text) data = Setup.ToCrlf(data);
                string got;
                using (var h = SHA256.Create()) got = Setup.Hex(h.ComputeHash(data));
                if (got != f.Sha256)
                    throw new Exception(L("El archivo descargado " + f.Src + " no coincide con el esperado (hash).",
                                          "Downloaded file " + f.Src + " does not match the expected hash."));

                if (File.Exists(dest))
                {
                    string b = Path.Combine(backup, f.Dest);
                    if (!File.Exists(b))
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(b));
                        File.Copy(dest, b);
                    }
                }
                Directory.CreateDirectory(Path.GetDirectoryName(dest));
                File.WriteAllBytes(dest, data);
                Log(L("  Parcheado: ", "  Patched: ") + f.Src);
                Step();
            }
        }
        // Same marker the online bootstrapper uses, so both launchers agree it is patched
        File.WriteAllText(Path.Combine(game, "bootlegger.json"), "{\"version\":" + Setup.PatchLevel + ",\"status\":\"ok\"}");
        Log(L("Parche aplicado (nivel ", "Patch applied (level ") + Setup.PatchLevel + ").");

        // Stop Windows from upscaling the game on high-DPI screens (window bigger than the screen)
        try
        {
            using (var k = Registry.CurrentUser.CreateSubKey(Setup.DpiKey))
                k.SetValue(Path.Combine(game, Setup.GameExeRel), "~ HIGHDPIAWARE");
            Log(L("Escalado de Windows desactivado para el juego (pantallas con DPI alto).",
                  "Windows DPI scaling disabled for the game (high-DPI screens)."));
        }
        catch { }
    }

    void InstallApp(string game, bool desktop)
    {
        string dir = Setup.InstallDir;
        Log(L("Instalando en ", "Installing to ") + dir + "...");
        foreach (var p in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(Setup.AppExe)))
            try { p.Kill(); p.WaitForExit(3000); } catch { }
        Directory.CreateDirectory(dir);
        string exe = Path.Combine(dir, Setup.AppExe);
        File.WriteAllBytes(exe, Setup.Resource("launcher.exe"));
        File.WriteAllBytes(Path.Combine(dir, "responses.json"), Setup.Resource("responses.json"));
        File.WriteAllBytes(Path.Combine(dir, "LICENSE.txt"), Setup.Resource("LICENSE"));
        File.WriteAllBytes(Path.Combine(dir, "README.txt"), Setup.Resource("README.txt"));
        File.WriteAllText(Path.Combine(dir, "gamepath.txt"), game);
        string uninst = Path.Combine(dir, "uninstall.exe");
        File.Copy(Application.ExecutablePath, uninst, true);

        string desc = L("Fractured Space sin conexión", "Fractured Space offline");
        Setup.CreateShortcut(Setup.StartLnk, exe, dir, desc);
        if (desktop) Setup.CreateShortcut(Setup.DesktopLnk, exe, dir, desc);
        else { try { File.Delete(Setup.DesktopLnk); } catch { } }
        Log(L("Accesos directos creados.", "Shortcuts created."));

        using (var k = Registry.CurrentUser.CreateSubKey(Setup.RegKey))
        {
            k.SetValue("DisplayName", Setup.AppName);
            k.SetValue("DisplayVersion", Setup.AppVersion);
            k.SetValue("Publisher", "fractured-space-offline");
            k.SetValue("DisplayIcon", exe + ",0");
            k.SetValue("InstallLocation", dir);
            k.SetValue("UninstallString", "\"" + uninst + "\" /uninstall");
            k.SetValue("URLInfoAbout", "https://github.com/kroryan/fractured-space-offline");
            k.SetValue("NoModify", 1, RegistryValueKind.DWord);
            k.SetValue("NoRepair", 1, RegistryValueKind.DWord);
            k.SetValue("EstimatedSize", 1400, RegistryValueKind.DWord);
        }
        Log(L("Registrado en Configuración > Aplicaciones.", "Registered in Settings > Apps."));
    }

    void LaunchApp()
    {
        try
        {
            Process.Start(new ProcessStartInfo(Path.Combine(Setup.InstallDir, Setup.AppExe)) { WorkingDirectory = Setup.InstallDir });
            Close();
        }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, Text); }
    }
}
