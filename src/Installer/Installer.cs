// Fractured Space Offline - Installer / Uninstaller
// - Lets the user pick the Fractured Space game folder (auto-detects Steam)
// - Applies the community client patch (files embedded in this installer, verified by
//   SHA-256; originals backed up). Works fully offline.
// - Installs "Fractured Space Bootstrapper Offline" (launcher + local Fireline emulator)
//   with Start Menu / Desktop shortcuts and an entry in Settings > Apps
// Run with /uninstall to remove it.
// All application UI is English, independent of the Windows display language.
// C# 5 (compiled with .NET Framework csc).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("Fractured Space Offline Setup")]
[assembly: AssemblyProduct("Fractured Space Offline")]
[assembly: AssemblyVersion("1.4.1.0")]
[assembly: AssemblyFileVersion("1.4.1.0")]

static class Setup
{
    public const string AppName = "Fractured Space Bootstrapper Offline";
    public const string AppVersion = "1.4.1";
    public const string AppExe = "FracturedSpaceBootstrapperOffline.exe";
    public const string RegKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\FracturedSpaceBootstrapperOffline";
    public const string DpiKey = @"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers";
    public const int PatchLevel = 33;
    public const string BackupDirName = "fractured-offline-backup";
    public const string OfflineMarkerName = "fractured-space-offline.json";
    public const string GameExeRel = @"spacegame\Binaries\Win64\Fractured Space.exe";


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
        new PatchFile("player.js", @"spacegame\Content\UIResources\frontend\script\player.js", "8e722a3a5205808fc84cad489c0e9f0c70ccac96bdc43ba58006400429c8ffaa", false),
        new PatchFile("common.js", @"spacegame\Content\UIResources\frontend\script\common.js", "42c777e308cbbbb147ad95c9ba84e116f696f8c9c98e800ee1f769a551b37d2c", false),
        new PatchFile("scoreboard.js", @"spacegame\Content\UIResources\frontend\map\scoreboard.js", "91a4d1342dbee1786421eba7ab138126e599ef5819881ba512f7d77f3d39368b", false),
        new PatchFile("mode-selector.js", @"spacegame\Content\UIResources\frontend\drafting\mode-selector.js", "9b83c60984b50c2ce82fd6690e808b10acc9332df076000781cc994b97d07be7", false),
        new PatchFile("drafting-style.css", @"spacegame\Content\UIResources\frontend\drafting\drafting-style.css", "141794cd40ffbf06c30d3f05cdaea2be05fc6c60384143922b7dbf5dd6b45079", false),
        new PatchFile("drafting-script.js", @"spacegame\Content\UIResources\frontend\drafting\drafting-script.js", "f0123b19191d9208581fd8a77dcd9c440af1d8f3cff1b6811dce16aafa5cfdb1", false),
        new PatchFile("Makichika_XmasEvent_P.pak", @"spacegame\Content\Paks\Makichika_XmasEvent_P.pak", "c20482888a928d878548da0ef51073abcdb7ef6bf9e3c51cfdb793bf5a419a48", false),
        new PatchFile("Makichika_VenturerSkins_P.pak", @"spacegame\Content\Paks\Makichika_VenturerSkins_P.pak", "b5dd72b42563c75da64883903a57f151919c119a86ad90bdc6ca26072dedb997", false),
        new PatchFile("Makichika_ProtectorShield_P.pak", @"spacegame\Content\Paks\Makichika_ProtectorShield_P.pak", "527ee940e636dab6fbeb53099ba6008cedb36fde3b0a46f89826cdda2b3eb8e1", false),
        new PatchFile("Makichika_MapJamming_P.pak", @"spacegame\Content\Paks\Makichika_MapJamming_P.pak", "ae20f8f7ab1a7c59ea433b8b5d93a7ae3f9089c8169710b3705371d7d53b6aa1", false),
        new PatchFile("Makichika_DiscordAvatars_P.pak", @"spacegame\Content\Paks\Makichika_DiscordAvatars_P.pak", "9ef2d2f35d9ef8df8a0e26258992a6e018db5f47d50e2cef8bc012017812a23c", false),
        new PatchFile("Makichika_CharonEvent_P.pak", @"spacegame\Content\Paks\Makichika_CharonEvent_P.pak", "8718acfd43663cd9613a5c2993e2596b23f081b57490db1beefe9826d491fde2", false),
        new PatchFile("Fractured Space.exe", @"spacegame\Binaries\Win64\Fractured Space.exe", "faefbe37c6403fd1097ea5351711f364b1fba421c20cac002587b06c54d12f1e", false),
        new PatchFile("ClientConfig.json", @"spacegame\ClientConfig.json", "0087a651ad5fbb235fa438b8d3a3f47cf2f6b11b3f88c528f82c48ccdc8d4b91", true),
        new PatchFile("startgame-script.js", @"spacegame\Content\UIResources\frontend\views\startgame\startgame-script.js", "1c62a37d09fc3930aa97e7b798c337e95ce1d24be4829fa15e62eb23de7711af", false),
        new PatchFile("startgame-style.css", @"spacegame\Content\UIResources\frontend\views\startgame\startgame-style.css", "49e856f3667e0c22db18a8c864c62ae66f1e1e2940d0efb783955ea6e0460301", true),
        new PatchFile("gamemodes-config.js", @"spacegame\Content\UIResources\frontend\views\gamemodes\gamemodes-config.js", "7d864d2985f05b81cd37199c4150652c4becf9c5cc253f160c2f38d7db7509bd", true),
        new PatchFile("nsloctext.js", @"spacegame\Content\UIResources\frontend\data\translations\nsloctext.js", "c1d43e513deb470d763b5d023db9275d3cde6bb689c45f1da110eb14ddd091af", true),
        new PatchFile("BP.pak", @"spacegame\Content\Paks\BP.pak", "cac460fbce8a33e8f155b9a4abd14c15981156978b3a2d420dc2b468399d1681", false),
        new PatchFile("results-script.js", @"spacegame\Content\UIResources\frontend\views\results\results-script.js", "c3cf69101faccd85c84c54102a377fb16f8cd05ed18ea7ca2beef3d3303d4852", true),
        new PatchFile("hangar-script.js", @"spacegame\Content\UIResources\frontend\views\hangar\hangar-script.js", "b3290327dfa2c94af87a58aa13b3021706f5685f249edbcd1a34bbb40ff8eede", true),
    };

    [STAThread]
    static int Main(string[] args)
    {
        Application.EnableVisualStyles();
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
        if (MessageBox.Show(("Uninstall ") + AppName + "?", AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
            return 0;

        foreach (var p in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(AppExe)))
            try { p.Kill(); } catch { }

        string game = null;
        try { game = File.ReadAllText(Path.Combine(InstallDir, "gamepath.txt")).Trim(); } catch { }
        string backup = game == null ? null : Path.Combine(game, BackupDirName);
        if (backup != null && Directory.Exists(backup))
        {
            var r = MessageBox.Show(
                ("Also restore the original game files?\n\n" +
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
                        if (rel.EndsWith(".fso-absent", StringComparison.Ordinal)) continue;
                        string dest = Path.Combine(game, rel);
                        Directory.CreateDirectory(Path.GetDirectoryName(dest));
                        File.Copy(f, dest, true);
                    }
                    foreach (var f in Setup.Patch)
                    {
                        string dest = Path.Combine(game, f.Dest);
                        if (File.Exists(Path.Combine(backup, f.Dest) + ".fso-absent") &&
                            File.Exists(dest) && Setup.Sha256File(dest) == f.Sha256)
                            File.Delete(dest);
                    }
                    string bootlegger = Path.Combine(game, "bootlegger.json");
                    string bootleggerBackup = Path.Combine(backup, "bootlegger.json");
                    if (!File.Exists(bootleggerBackup))
                    {
                        try
                        {
                            if (File.ReadAllText(bootlegger).Trim() == "{\"version\":" + Setup.PatchLevel + ",\"status\":\"ok\"}")
                                File.Delete(bootlegger);
                        }
                        catch { }
                    }
                    string offlineMarker = Path.Combine(game, Setup.OfflineMarkerName);
                    string offlineMarkerBackup = Path.Combine(backup, Setup.OfflineMarkerName);
                    if (!File.Exists(offlineMarkerBackup))
                    {
                        try
                        {
                            if (File.ReadAllText(offlineMarker).Trim() == "{\"version\":" + Setup.PatchLevel + ",\"status\":\"ok\"}")
                                File.Delete(offlineMarker);
                        }
                        catch { }
                    }
                    Directory.Delete(backup, true);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(("Could not restore all files:\n") + ex.Message, AppName);
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
        MessageBox.Show(AppName + (" has been uninstalled."), AppName, MessageBoxButtons.OK, MessageBoxIcon.Information);
        return 0;
    }
}

class SetupForm : Form
{

    TextBox txtPath, txtLog;
    Button btnBrowse, btnInstall, btnClose;
    CheckBox chkDesktop;
    ProgressBar bar;
    bool installed;

    public SetupForm()
    {
        Text = ("Fractured Space Offline Setup");
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
            Text = ("Play Fractured Space offline against bots, using a local server.\r\n" +
                     "Select the game folder (the one containing \"spacegame\") and click Install."),
            AutoSize = true, Location = new Point(18, 48)
        };
        var lbl = new Label { Text = ("Game folder:"), AutoSize = true, Location = new Point(18, 96) };
        txtPath = new TextBox { Location = new Point(18, 116), Width = 490, Text = Setup.DetectGame() };
        btnBrowse = new Button { Text = ("Browse..."), Location = new Point(516, 114), Width = 88 };
        btnBrowse.Click += (s, e) => Browse();
        chkDesktop = new CheckBox { Text = ("Create a desktop shortcut"), Checked = true, AutoSize = true, Location = new Point(18, 148) };
        bar = new ProgressBar { Location = new Point(18, 178), Width = 586, Height = 18, Maximum = Setup.Patch.Length + 2 };
        txtLog = new TextBox { Location = new Point(18, 204), Width = 586, Height = 170, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, BackColor = SystemColors.Window };
        btnInstall = new Button { Text = ("Install"), Location = new Point(424, 388), Width = 88, Height = 28 };
        btnInstall.Click += (s, e) => StartInstall();
        btnClose = new Button { Text = ("Close"), Location = new Point(516, 388), Width = 88, Height = 28 };
        btnClose.Click += (s, e) => Close();
        AcceptButton = btnInstall;

        Controls.AddRange(new Control[] { title, sub, lbl, txtPath, btnBrowse, chkDesktop, bar, txtLog, btnInstall, btnClose });
        Log(txtPath.Text.Length > 0
            ? ("Game found at: ") + txtPath.Text
            : ("The game was not detected automatically. Click Browse."));
    }

    void Browse()
    {
        using (var d = new FolderBrowserDialog())
        {
            d.Description = ("Select the Fractured Space folder (usually ...\\steamapps\\common\\Space)");
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
            MessageBox.Show(this, ("That folder does not look like Fractured Space.\nIt must contain spacegame\\Binaries\\Win64."),
                Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        if (Process.GetProcessesByName("Fractured Space").Length > 0)
        {
            MessageBox.Show(this, ("Close Fractured Space before installing."),
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
            Log(("Done! Open \"" + Setup.AppName + "\" from the Start menu" + (desktop ? " or the desktop" : "") + "."));
            Log(("In game: Play -> Training -> Solo vs AI to play against bots."));
            BeginInvoke(new Action(() =>
            {
                installed = true;
                bar.Value = bar.Maximum;
                btnInstall.Text = ("Play");
                btnInstall.Enabled = true;
            }));
        }
        catch (UnauthorizedAccessException ex)
        {
            Log(("ERROR: no permission to write: ") + ex.Message);
            Log(("Run the installer with right click -> Run as administrator."));
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
        Log(("Checking game patch..."));
        string backup = Path.Combine(game, Setup.BackupDirName);
        string offlineMarker = Path.Combine(game, Setup.OfflineMarkerName);
        string bootleggerMarker = Path.Combine(game, "bootlegger.json");
        bool anotherBootstrapperOwnsPatch = File.Exists(bootleggerMarker) && !File.Exists(offlineMarker);
        if (anotherBootstrapperOwnsPatch)
        {
            foreach (var f in Setup.Patch)
            {
                string dest = Path.Combine(game, f.Dest);
                if (!File.Exists(dest) || Setup.Sha256File(dest) != f.Sha256)
                    throw new Exception(("A different online Bootstrapper patch is active in this game folder. It was left untouched. Update or uninstall that patch, then try again."));
            }
        }
        {
            foreach (var f in Setup.Patch)
            {
                string dest = Path.Combine(game, f.Dest);
                if (File.Exists(dest) && Setup.Sha256File(dest) == f.Sha256)
                {
                    Log(("  OK (already patched): ") + f.Src);
                    Step();
                    continue;
                }
                byte[] data = Setup.Resource("patch/" + f.Src);
                string got;
                using (var h = SHA256.Create()) got = Setup.Hex(h.ComputeHash(data));
                if (got != f.Sha256)
                    throw new Exception(("Patch file " + f.Src + " is corrupted (hash mismatch)."));

                if (File.Exists(dest))
                {
                    string b = Path.Combine(backup, f.Dest);
                    if (!File.Exists(b))
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(b));
                        File.Copy(dest, b);
                    }
                }
                else
                {
                    string b = Path.Combine(backup, f.Dest);
                    if (!File.Exists(b))
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(b));
                        File.WriteAllText(b + ".fso-absent", "");
                    }
                }
                Directory.CreateDirectory(Path.GetDirectoryName(dest));
                File.WriteAllBytes(dest, data);
                Log(("  Patched: ") + f.Src);
                Step();
            }
        }
        // Keep this launcher's state separate; bootlegger.json belongs to the online Bootstrapper.
        string markerBackup = Path.Combine(backup, Setup.OfflineMarkerName);
        if (File.Exists(offlineMarker) && !File.Exists(markerBackup))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(markerBackup));
            File.Copy(offlineMarker, markerBackup);
        }
        File.WriteAllText(offlineMarker, "{\"version\":" + Setup.PatchLevel + ",\"status\":\"ok\"}");
        InstallServerWrapper(game, backup);
        Log(("Patch applied (level ") + Setup.PatchLevel + ").");

        // Stop Windows from upscaling the game on high-DPI screens (window bigger than the screen)
        try
        {
            using (var k = Registry.CurrentUser.CreateSubKey(Setup.DpiKey))
                k.SetValue(Path.Combine(game, Setup.GameExeRel), "~ HIGHDPIAWARE");
            Log(("Windows DPI scaling disabled for the game (high-DPI screens)."));
        }
        catch { }
    }

    void InstallServerWrapper(string game, string backup)
    {
        string server = Path.Combine(game, @"spacegame\Binaries\Win64\spserver.exe");
        if (!File.Exists(server)) { Log(("Dedicated server not found; skipping wrapper.")); return; }
        string original = Path.Combine(Path.GetDirectoryName(server), "spserver_original.exe");
        string saved = Path.Combine(backup, @"spacegame\Binaries\Win64\spserver.exe");
        if (!File.Exists(original))
        {
            if (!File.Exists(saved)) { Directory.CreateDirectory(Path.GetDirectoryName(saved)); File.Copy(server, saved); }
            File.Copy(server, original, true);
        }
        File.WriteAllBytes(server, Setup.Resource("spserver-wrapper.exe"));
        Log(("Co-op server wrapper installed (original backed up)."));
    }

    void InstallApp(string game, bool desktop)
    {
        string dir = Setup.InstallDir;
        Log(("Installing to ") + dir + "...");
        foreach (var p in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(Setup.AppExe)))
            try { p.Kill(); p.WaitForExit(3000); } catch { }
        Directory.CreateDirectory(dir);
        string exe = Path.Combine(dir, Setup.AppExe);
        File.WriteAllBytes(exe, Setup.Resource("launcher.exe"));
        File.WriteAllBytes(Path.Combine(dir, "fso_offline_menu.dll"), Setup.Resource("fso_offline_menu.dll"));
        using (var archive = new System.IO.Compression.ZipArchive(new MemoryStream(Setup.Resource("trainer.zip"))))
        foreach (var entry in archive.Entries)
        {
            string target = Path.GetFullPath(Path.Combine(dir, "trainer", entry.FullName));
            string root = Path.GetFullPath(Path.Combine(dir, "trainer")) + Path.DirectorySeparatorChar;
            if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new Exception("Invalid trainer path");
            if (entry.Name.Length == 0) { Directory.CreateDirectory(target); continue; }
            Directory.CreateDirectory(Path.GetDirectoryName(target));
            using (var input = entry.Open()) using (var output = File.Create(target)) input.CopyTo(output);
        }

        File.WriteAllBytes(Path.Combine(dir, "responses.json"), Setup.Resource("responses.json"));
        File.WriteAllBytes(Path.Combine(dir, "LICENSE.txt"), Setup.Resource("LICENSE"));
        foreach (string notice in new[] { "NOTICE.md", "overlay-licenses.md", "minhook-license.txt" })
            File.WriteAllBytes(Path.Combine(dir, notice), Setup.Resource(notice));
        File.WriteAllBytes(Path.Combine(dir, "README.txt"), Setup.Resource("README.txt"));
        File.WriteAllText(Path.Combine(dir, "gamepath.txt"), game);
        string uninst = Path.Combine(dir, "uninstall.exe");
        File.Copy(Application.ExecutablePath, uninst, true);

        string desc = ("Fractured Space offline");
        Setup.CreateShortcut(Setup.StartLnk, exe, dir, desc);
        if (desktop) Setup.CreateShortcut(Setup.DesktopLnk, exe, dir, desc);
        else { try { File.Delete(Setup.DesktopLnk); } catch { } }
        Log(("Shortcuts created."));

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
        Log(("Registered in Settings > Apps."));
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
