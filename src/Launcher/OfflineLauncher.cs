// Fractured Space Bootstrapper Offline
// Self-contained launcher: embedded Fireline emulator (based on Tigerhacker/refireline, GPL-3.0)
// serving recorded api.fireteam.net responses on http://127.0.0.1:8080, then launches the
// patched game against it and exits when the game closes.
// C# 5 (compiled with .NET Framework csc).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Net.NetworkInformation;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Fractured Space Bootstrapper Offline")]
[assembly: System.Reflection.AssemblyProduct("Fractured Space Bootstrapper Offline")]
[assembly: System.Reflection.AssemblyVersion("1.4.1.0")]
[assembly: System.Reflection.AssemblyFileVersion("1.4.1.0")]

static class OfflineLauncher
{
    const string Title = "Fractured Space Bootstrapper Offline";
    const string Prefix = "https://api.fireteam.net/";
    const string RecordedIdentity = "197a97fc-4179-43f4-b009-9432ac0c8e53";
    static string activeIdentity = RecordedIdentity;
    static readonly Dictionary<string, Canned> canned = new Dictionary<string, Canned>();
    static readonly Dictionary<string, Canned> byPath = new Dictionary<string, Canned>();
    static string logPath;
    static ProfileStore profile;
    static TrainerBridge trainer;
    static readonly string menuToken = Guid.NewGuid().ToString("N");
    static readonly object logLock = new object();
    enum PlayMode { Solo, Host, Join }
    static PlayMode selectedMode = PlayMode.Solo;
    static string selectedHost = "";
    static string selectedBindIp = "0.0.0.0";
    static int expectedPlayers = 2;
    static int hostTeamSize = 2;
    static int assignedTeam = 1;

    class Canned { public int Status; public byte[] Body; }

    [STAThread]
    static int Main(string[] args)
    {
        string appDir = AppDomain.CurrentDomain.BaseDirectory;
        logPath = Path.Combine(appDir, "requests.log");
        int port = 8080;
        bool serveOnly = false;
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--serve-only") serveOnly = true;
            else if (args[i] == "--port" && i + 1 < args.Length) port = int.Parse(args[++i]);
        }

        if (!serveOnly && !ChooseMode(appDir)) return 0;

        bool created;
        using (var mutex = new Mutex(true, "FracturedSpaceBootstrapperOffline_" + port, out created))
        {
            if (!created) { Fail(("The offline launcher is already running.")); return 1; }
            try { File.WriteAllText(logPath, ""); } catch { }

            string playerId = LoadPlayerId(appDir);
            CoopAdmission admission = null;
            UdpRelay relay = null;
            try
            {
                if (selectedMode == PlayMode.Host)
                {
                    string state = Path.Combine(appDir, "approved-guests.json");
                    string teamState = Path.Combine(appDir, "approved-guest-teams.json");
                    admission = new CoopAdmission(IPAddress.Parse(selectedBindIp), state, teamState,
                        expectedPlayers, hostTeamSize, (peer, team) =>
                    {
                        DialogResult answer = DialogResult.No;
                        var t = new Thread(() => answer = MessageBox.Show(
                            ("Player " + peer + " requests to join team " + team + ". Accept?"),
                            Title, MessageBoxButtons.YesNo, MessageBoxIcon.Question));
                        t.SetApartmentState(ApartmentState.STA); t.Start(); t.Join();
                        return answer == DialogResult.Yes;
                    });
                    relay = new UdpRelay(admission, IPAddress.Parse(selectedBindIp), 7777);
                    Log("Co-op admission listening on TCP 8090");
                    Log("Approved-peer UDP relay listening on UDP 7777");
                }
                else if (selectedMode == PlayMode.Join)
                {
                    CoopAdmission.JoinResult join = CoopAdmission.Request(selectedHost, playerId, 120000);
                    playerId = join.PlayerId;
                    assignedTeam = join.Team;
                    File.WriteAllText(Path.Combine(appDir, "player-id.txt"), playerId);
                }
            }
            catch (Exception ex) { Fail(("Could not host/join the co-op game:\n") + ex.Message); return 1; }
            activeIdentity = String.IsNullOrEmpty(playerId) ? RecordedIdentity : playerId;
            string profileDirectory = serveOnly ? Path.Combine(appDir, "profiles") : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "FracturedSpaceOffline", "profiles");
            profile = new ProfileStore(profileDirectory, activeIdentity);

            try { LoadResponses(Path.Combine(appDir, "responses.json")); }
            catch (Exception ex) { Fail(("Could not read responses.json:\n") + ex.Message); return 1; }

            TcpListener listener;
            try
            {
                listener = new TcpListener(IPAddress.Loopback, port);
                listener.Start();
            }
            catch (Exception ex)
            {
                Fail(("Port " + port + " is in use (is another offline server or the game already running?).\n\n") + ex.Message);
                return 1;
            }
            var serverThread = new Thread(() => Serve(listener)) { IsBackground = true };
            serverThread.Start();
            Log("Local server on http://127.0.0.1:" + port);

            if (serveOnly)
            {
                Thread.Sleep(Timeout.Infinite);
                return 0;
            }

            string gameRoot = FindGame(appDir);
            if (gameRoot == null) { Fail(("Fractured Space was not found in your Steam libraries.")); return 1; }
            string exe = Path.Combine(gameRoot, @"spacegame\Binaries\Win64\Fractured Space.exe");
            if (selectedMode != PlayMode.Solo && !File.Exists(Path.Combine(gameRoot, @"spacegame\Binaries\Win64\spserver_original.exe")))
            {
                Fail(("The server wrapper is not installed. Run the installer again."));
                return 1;
            }
            if (selectedMode != PlayMode.Solo && !File.Exists(Path.Combine(gameRoot, @"spacegame\Binaries\Win64\spserver_original.exe")))
            {
                Fail(("The server wrapper is not installed. Run the installer again."));
                return 1;
            }
            if (!File.Exists(exe)) { Fail(("Not found:\n") + exe); return 1; }
            string patchError = GetPatchError(exe);
            if (patchError != null) { listener.Stop(); Fail(patchError); return 1; }
            if (!File.Exists(Path.Combine(gameRoot, "fractured-space-offline.json")) &&
                !File.Exists(Path.Combine(gameRoot, "bootlegger.json")))
            {
                Fail(("The game is not patched.\nRun the Fractured Space Offline installer again."));
                return 1;
            }
            if (Process.GetProcessesByName("Fractured Space").Length > 0)
            {
                Fail(("Fractured Space is already running. Close it before using offline mode."));
                return 1;
            }

            if (selectedMode != PlayMode.Join) {
                trainer = new TrainerBridge();
                trainer.Start(appDir, gameRoot);
                AppDomain.CurrentDomain.ProcessExit += (sender, e) => trainer.Dispose();
            }
            try { ConfigureDisplay(); } catch (Exception ex) { Log("Display config failed: " + ex.Message); }
            using (var progress = new LaunchProgress())
            {
                progress.Show(); progress.Set(65, ("Preparing the local server…"));
                Application.DoEvents();

            var psi = new ProcessStartInfo(exe,
                "-flhost=http://127.0.0.1:" + port + " -discord=offline -culture=en-GB");
            psi.WorkingDirectory = Path.GetDirectoryName(exe);
            psi.UseShellExecute = false;
            psi.EnvironmentVariables["FSO_OFFLINE_MENU"] = port + ":" + menuToken;
            psi.EnvironmentVariables["SteamAppId"] = "310380";
            psi.EnvironmentVariables["OPENSSL_ia32cap"] = ":~0x20000000";
            if (selectedMode == PlayMode.Host) psi.EnvironmentVariables["FSO_COOP_MODE"] = "host";
            if (selectedMode == PlayMode.Host)
            {
                psi.EnvironmentVariables["FSO_COOP_TEAM"] = "1";
                int otherTeamSize = expectedPlayers - hostTeamSize;
                psi.EnvironmentVariables["FSO_SERVER_URL_EXTRA"] = hostTeamSize == expectedPlayers
                    ? "?coop=1"
                    : "?coop=0?team1Players=" + hostTeamSize + "?team2Players=" + otherTeamSize;
            }
            if (selectedMode == PlayMode.Join) { psi.EnvironmentVariables["FSO_COOP_MODE"] = "guest"; psi.EnvironmentVariables["FSO_COOP_HOST"] = selectedHost; }
            if (selectedMode == PlayMode.Join) psi.EnvironmentVariables["FSO_COOP_TEAM"] = assignedTeam.ToString();
            psi.EnvironmentVariables["FSO_PLAYER_ID"] = playerId;
            try
            {
                progress.Set(82, ("Starting Fractured Space…")); Application.DoEvents();
                var recorder = new MatchRecorder(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"spacegame\Saved\FracturedSpace\fso-results.json"), profile, Log);
                var game = Process.Start(psi);
                progress.Set(100, ("Waiting for the game window…"));
                if (game != null)
                {
                    while (!game.HasExited && game.MainWindowHandle == IntPtr.Zero) { Thread.Sleep(500); game.Refresh(); Application.DoEvents(); }
                    progress.Close();
                    try { OverlayLoader.Load(game, Path.Combine(appDir, "fso_offline_menu.dll")); }
                    catch (Exception overlayError) { Log("F1 menu failed: " + overlayError.Message); }
                    while (!game.HasExited) { recorder.Poll(); Application.DoEvents(); Thread.Sleep(100); game.Refresh(); }
                    recorder.Poll();
                }
                progress.Close();
            }
            catch (Exception ex) { Fail(("Could not start the game:\n") + ex.Message); return 1; }
            }

            // The game may relaunch itself; wait until no instance remains.
            do { Thread.Sleep(3000); } while (Process.GetProcessesByName("Fractured Space").Length > 0);
            if (admission != null) admission.Dispose();
            if (relay != null) relay.Dispose();
            if (trainer != null) trainer.Dispose();
            listener.Stop();
            return 0;
        }
    }

    static string GetPatchError(string executable)
    {
        using (var stream = System.Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream("game-exe.sha256"))
        {
            if (stream == null) return "The launcher patch verification data is missing. Reinstall Fractured Space Offline.";
            string expected;
            using (var reader = new StreamReader(stream)) expected = reader.ReadToEnd().Trim();
            using (var hash = System.Security.Cryptography.SHA256.Create())
            using (var file = File.OpenRead(executable))
            {
                string actual = BitConverter.ToString(hash.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
                if (actual == expected) return null;
            }
        }
        return "The game executable no longer matches the offline patch. It may have been restored by an uninstall, Steam verification or another launcher.\n\nClose the game and run the installer for the edition you want to play again. Your player profile does not need to be deleted.";
    }

    static string LoadPlayerId(string appDir)
    {
        string f = Path.Combine(appDir, "player-id.txt");
        try { string id = File.ReadAllText(f).Trim(); Guid.Parse(id); return id; } catch { string id = Guid.NewGuid().ToString(); File.WriteAllText(f, id); return id; }
    }

    static bool ChooseMode(string appDir)
    {
        string file = Path.Combine(appDir, "launcher-mode.txt");
        int last = 0; try { int.TryParse(File.ReadAllText(file).Trim(), out last); } catch { }
        string teamFile = Path.Combine(appDir, "coop-team.txt");
        try
        {
            string[] saved = File.ReadAllText(teamFile).Split(',');
            expectedPlayers = Math.Max(2, Math.Min(4, int.Parse(saved[0])));
            hostTeamSize = Math.Max(1, Math.Min(expectedPlayers, int.Parse(saved[1])));
        }
        catch { expectedPlayers = 2; hostTeamSize = 2; }
        using (var f = new Form())
        {
            f.BackColor = System.Drawing.Color.FromArgb(18, 22, 30); f.ForeColor = System.Drawing.Color.FromArgb(225, 232, 240); f.Font = new System.Drawing.Font("Segoe UI", 10);
            f.Text = Title; f.Width = 520; f.Height = 420; f.StartPosition = FormStartPosition.CenterScreen;
            var solo = new RadioButton { Left = 24, Top = 24, Width = 410, Text = ("Play solo vs bots"), Checked = last == 0 };
            var host = new RadioButton { Left = 24, Top = 60, Width = 410, Text = ("Create co-op game (host)"), Checked = last == 1 };
            var join = new RadioButton { Left = 24, Top = 96, Width = 410, Text = ("Join a co-op game"), Checked = last == 2 };
            var ipLabel = new Label { Left = 46, Top = 132, Width = 100, Text = "Host IP:" };
            var ip = new TextBox { Left = 145, Top = 128, Width = 250, Text = "127.0.0.1" };
            var bindLabel = new Label { Left = 46, Top = 166, Width = 100, Text = ("Local IP:") };
            var bind = new ComboBox { Left = 145, Top = 162, Width = 250, DropDownStyle = ComboBoxStyle.DropDownList };
            foreach (var a in LocalAddresses()) bind.Items.Add(a);
            if (bind.Items.Count > 0) bind.SelectedIndex = 0;
            var partyLabel = new Label { Left = 46, Top = 202, Width = 215, Text = ("Human players (including you):") };
            var party = new NumericUpDown { Left = 270, Top = 198, Width = 65, Minimum = 2, Maximum = 4, Value = expectedPlayers };
            var teamLabel = new Label { Left = 46, Top = 238, Width = 215, Text = ("Humans on your team:") };
            var teamSize = new ComboBox { Left = 270, Top = 234, Width = 175, DropDownStyle = ComboBoxStyle.DropDownList };
            var distribution = new Label { Left = 46, Top = 270, Width = 410, Height = 38 };
            Action refreshTeams = () =>
            {
                int count = (int)party.Value;
                int selected = Math.Max(1, Math.Min(count, hostTeamSize));
                teamSize.Items.Clear();
                for (int i = 1; i <= count; i++)
                    teamSize.Items.Add(i == count
                        ? ("All together (" + count + ")")
                        : (i + " on your team / " + (count - i) + " on the other"));
                teamSize.SelectedIndex = selected - 1;
                hostTeamSize = selected;
                distribution.Text = ("The host will be on team 1. Each join request will show its assigned team.");
            };
            party.ValueChanged += (s, e) => refreshTeams();
            teamSize.SelectedIndexChanged += (s, e) => { if (teamSize.SelectedIndex >= 0) hostTeamSize = teamSize.SelectedIndex + 1; };
            refreshTeams();
            Action updateEnabled = () =>
            {
                bool hosting = host.Checked;
                ipLabel.Enabled = ip.Enabled = join.Checked;
                bindLabel.Enabled = bind.Enabled = hosting;
                partyLabel.Enabled = party.Enabled = teamLabel.Enabled = teamSize.Enabled = distribution.Enabled = hosting;
            };
            solo.CheckedChanged += (s, e) => updateEnabled();
            host.CheckedChanged += (s, e) => updateEnabled();
            join.CheckedChanged += (s, e) => updateEnabled();
            updateEnabled();
            var go = new Button { Left = 335, Top = 325, Width = 110, Text = ("Continue"), DialogResult = DialogResult.OK };
            go.Click += (s,e) => { IPAddress parsed; if (join.Checked && !IPAddress.TryParse(ip.Text.Trim(), out parsed)) { MessageBox.Show(("Enter a valid IP address.")); f.DialogResult = DialogResult.None; } };
            f.Controls.AddRange(new Control[] { solo, host, join, ipLabel, ip, bindLabel, bind, partyLabel, party, teamLabel, teamSize, distribution, go }); f.AcceptButton = go;
            foreach (Control control in f.Controls) {
                if (control is TextBox || control is ComboBox || control is Button) {
                    control.BackColor = System.Drawing.Color.FromArgb(32, 42, 56);
                    control.ForeColor = System.Drawing.Color.FromArgb(225, 232, 240);
                }
            }
            go.FlatStyle = FlatStyle.Flat;
            go.BackColor = System.Drawing.Color.FromArgb(35, 102, 155);
            if (f.ShowDialog() != DialogResult.OK) return false;
            selectedMode = solo.Checked ? PlayMode.Solo : host.Checked ? PlayMode.Host : PlayMode.Join;
            selectedHost = ip.Text.Trim();
            selectedBindIp = bind.SelectedItem == null ? "0.0.0.0" : bind.SelectedItem.ToString().Split(' ')[0];
            expectedPlayers = (int)party.Value;
            hostTeamSize = Math.Max(1, teamSize.SelectedIndex + 1);
            try { File.WriteAllText(teamFile, expectedPlayers + "," + hostTeamSize); } catch { }
            try { File.WriteAllText(file, selectedMode == PlayMode.Solo ? "0" : selectedMode == PlayMode.Host ? "1" : "2"); } catch { }
            return true;
        }
    }

    static List<string> LocalAddresses()
    {
        var rows = new List<Tuple<int, string>>();
        try
        {
            foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
            {
                string name = ((nic.Name ?? "") + " " + (nic.Description ?? "")).ToLowerInvariant();
                foreach (var ua in nic.GetIPProperties().UnicastAddresses)
                    if (ua.Address.AddressFamily == AddressFamily.InterNetwork && !IPAddress.IsLoopback(ua.Address))
                    {
                        string ip = ua.Address.ToString();
                        byte[] b = ua.Address.GetAddressBytes();
                        bool vpnRange = (b[0] == 100 && b[1] >= 64 && b[1] <= 127) || b[0] == 25 || b[0] == 26 ||
                                        (b[0] == 192 && b[1] == 168 && (b[2] == 191 || b[2] == 192)) ||
                                        (b[0] == 10 && b[1] >= 147 && b[1] <= 151);
                        int rank = (name.Contains("tailscale") || name.Contains("zerotier") || name.Contains("hamachi") || name.Contains("radmin") || vpnRange) ? 0 : 1;
                        rows.Add(Tuple.Create(rank, ip + "  —  " + nic.Name));
                    }
            }
        }
        catch { }
        rows.Sort((a,b) => a.Item1 != b.Item1 ? a.Item1.CompareTo(b.Item1) : String.Compare(a.Item2,b.Item2,StringComparison.OrdinalIgnoreCase));
        return rows.ConvertAll(x => x.Item2);
    }

    sealed class LaunchProgress : Form
    {
        readonly Label label; readonly ProgressBar bar;
        public LaunchProgress()
        {
            BackColor = System.Drawing.Color.FromArgb(18, 22, 30); ForeColor = System.Drawing.Color.FromArgb(225, 232, 240); Font = new System.Drawing.Font("Segoe UI", 10);
            Text = Title; Width = 470; Height = 135; FormBorderStyle = FormBorderStyle.FixedDialog;
            ControlBox = false; StartPosition = FormStartPosition.CenterScreen;
            label = new Label { Left = 18, Top = 16, Width = 420, Height = 24, Text = ("Finding the game…") };
            bar = new ProgressBar { Left = 18, Top = 52, Width = 420, Height = 22, Minimum = 0, Maximum = 100, Value = 20 };
            Controls.Add(label); Controls.Add(bar);
        }
        public void Set(int value, string text) { bar.Value = Math.Max(0, Math.Min(100, value)); label.Text = text; }
    }


    [System.Runtime.InteropServices.DllImport("user32.dll")]
    static extern bool SetProcessDPIAware();

    // Windowed fullscreen at the monitor's real resolution, so the game always fits the screen.
    static void ConfigureDisplay()
    {
        SetProcessDPIAware();
        var b = Screen.PrimaryScreen.Bounds; // physical pixels once DPI-aware
        string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            @"spacegame\Saved\Config\WindowsNoEditor");
        string ini = Path.Combine(dir, "GameUserSettings.ini");
        Directory.CreateDirectory(dir);
        string text = File.Exists(ini) ? File.ReadAllText(ini) : "";
        const string section = "[/Script/spacegame.SpaceUserSettings]";
        if (text.IndexOf(section, StringComparison.Ordinal) < 0)
            text = text.TrimEnd() + (text.Length > 0 ? "\r\n\r\n" : "") + section + "\r\n";
        var values = new Dictionary<string, string>
        {
            { "ResolutionSizeX", b.Width.ToString() },
            { "ResolutionSizeY", b.Height.ToString() },
            { "LastUserConfirmedResolutionSizeX", b.Width.ToString() },
            { "LastUserConfirmedResolutionSizeY", b.Height.ToString() },
            { "DesiredScreenWidth", b.Width.ToString() },
            { "DesiredScreenHeight", b.Height.ToString() },
            { "FullscreenMode", "1" },
            { "LastConfirmedFullscreenMode", "1" },
            { "PreferredFullscreenMode", "1" },
        };
        foreach (var kv in values)
        {
            var rx = new System.Text.RegularExpressions.Regex("(?m)^" + kv.Key + "=.*$");
            if (rx.IsMatch(text))
                text = rx.Replace(text, kv.Key + "=" + kv.Value);
            else
            {
                int i = text.IndexOf(section, StringComparison.Ordinal) + section.Length;
                text = text.Insert(i, "\r\n" + kv.Key + "=" + kv.Value);
            }
        }
        File.WriteAllText(ini, text);
        Log("Display: windowed fullscreen " + b.Width + "x" + b.Height);
    }

    static void Fail(string msg)
    {
        MessageBox.Show(msg, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    static void Log(string line)
    {
        lock (logLock)
        {
            try { File.AppendAllText(logPath, DateTime.Now.ToString("HH:mm:ss") + " " + line + "\r\n"); } catch { }
        }
    }

    static string FindGame(string appDir)
    {
        // Folder chosen in the installer takes priority
        try
        {
            string cfg = Path.Combine(appDir, "gamepath.txt");
            if (File.Exists(cfg))
            {
                string p = File.ReadAllText(cfg).Trim();
                if (Directory.Exists(Path.Combine(p, "spacegame"))) return p;
            }
        }
        catch { }
        var candidates = new List<string>();
        string steam = null;
        try
        {
            using (var k = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Wow6432Node\Valve\Steam"))
                if (k != null) steam = k.GetValue("InstallPath") as string;
        }
        catch { }
        if (steam == null) steam = @"C:\Program Files (x86)\Steam";
        string steamapps = Path.Combine(steam, "steamapps");
        candidates.Add(steamapps);
        try
        {
            string vdf = File.ReadAllText(Path.Combine(steamapps, "libraryfolders.vdf"));
            foreach (System.Text.RegularExpressions.Match m in
                System.Text.RegularExpressions.Regex.Matches(vdf, "\"path\"\\s+\"([^\"]+)\""))
                candidates.Add(Path.Combine(m.Groups[1].Value.Replace("\\\\", "\\"), "steamapps"));
        }
        catch { }
        foreach (var c in candidates)
        {
            string root = Path.Combine(c, @"common\Space");
            if (Directory.Exists(Path.Combine(root, "spacegame"))) return root;
        }
        return null;
    }

    static void LoadResponses(string file)
    {
        var ser = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        var list = ser.DeserializeObject(File.ReadAllText(file, Encoding.UTF8)) as object[];
        foreach (Dictionary<string, object> entry in list)
        {
            var req = (Dictionary<string, object>)entry["request"];
            var res = (Dictionary<string, object>)entry["response"];
            string url = (string)req["url"];
            string path = url.StartsWith(Prefix) ? url.Substring(Prefix.Length) : url;
            int q = path.IndexOf('?');
            if (q >= 0) path = path.Substring(0, q);
            var c = new Canned
            {
                Status = Convert.ToInt32(res["status_code"]),
                Body = Encoding.UTF8.GetBytes((string)res["content"] ?? "")
            };
            profile.Register(path, c.Body);
            canned[(string)req["method"] + " " + path] = c;
            byPath[path] = c;
        }
    }

    static void Serve(TcpListener listener)
    {
        while (true)
        {
            TcpClient client;
            try { client = listener.AcceptTcpClient(); }
            catch { return; }
            ThreadPool.QueueUserWorkItem(_ => Handle(client));
        }
    }

    static void Handle(TcpClient client)
    {
        using (client)
        {
            try
            {
                client.ReceiveTimeout = 15000;
                var stream = client.GetStream();
                while (true)
                {
                    string head = ReadHead(stream);
                    if (head == null) return;
                    string[] lines = head.Split(new[] { "\r\n" }, StringSplitOptions.None);
                    string[] first = lines[0].Split(' ');
                    if (first.Length < 2) return;
                    string method = first[0];
                    string target = first[1];
                    int contentLength = 0;
                    bool close = false;
                    foreach (var l in lines.Skip(1))
                    {
                        int idx = l.IndexOf(':');
                        if (idx <= 0) continue;
                        string name = l.Substring(0, idx).Trim().ToLowerInvariant();
                        string val = l.Substring(idx + 1).Trim();
                        if (name == "content-length") int.TryParse(val, out contentLength);
                        if (name == "connection" && val.ToLowerInvariant() == "close") close = true;
                    }
                    byte[] body = new byte[contentLength];
                    int read = 0;
                    while (read < contentLength)
                    {
                        int n = stream.Read(body, read, contentLength - read);
                        if (n <= 0) return;
                        read += n;
                    }

                    string path = target.TrimStart('/');
                    int q = path.IndexOf('?');
                    string query = q >= 0 ? path.Substring(q + 1) : "";
                    if (q >= 0) path = path.Substring(0, q);

                    Canned c;
                    int status = 200;
                    byte[] payload;
                    if (path == "status" || path == "action" || path == "requests")
                    {
                        var args = System.Web.HttpUtility.ParseQueryString(query);
                        if (args["t"] != menuToken) { status = 403; payload = Encoding.UTF8.GetBytes("Forbidden"); }
                        else if (path == "action" && method == "POST")
                            {
                            string action = args["name"] ?? "";
                            bool combat = action.StartsWith("god_") || action.StartsWith("spawn_");
                            try { payload = Encoding.UTF8.GetBytes(combat ? (trainer == null ? "Only the local host can control the server." : trainer.Action(action, args["ship"])) : profile.Action(action)); }
                            catch (Exception error) { payload = Encoding.UTF8.GetBytes(error.Message); }
                        }
                        else payload = Encoding.UTF8.GetBytes(path == "status" ? "Fractured Space Offline | Personal profile | All ships unlocked" : "");
                    }
                    else if (profile.Handle(method, path, body, out payload))
                    {
                        payload = RewriteIdentity(payload); Log("profile " + method + " /" + path);
                    }
                    else if (path.Length == 0)
                    {
                        payload = Encoding.UTF8.GetBytes("Fireline Emulator for Fractured Space (offline launcher)");
                        Log(method + " /");
                    }
                    else if (canned.TryGetValue(method + " " + path, out c) || byPath.TryGetValue(path, out c))
                    {
                        status = c.Status; payload = RewriteIdentity(c.Body);
                        Log("hit  " + method + " /" + path);
                    }
                    else
                    {
                        payload = Encoding.UTF8.GetBytes("{}");
                        string b = Encoding.UTF8.GetString(body);
                        if (b.Length > 200) b = b.Substring(0, 200);
                        Log("MISS " + method + " /" + path + (query.Length > 0 ? "?" + query : "") + " " + b);
                    }

                    string reason = status == 200 ? "OK" : status == 201 ? "Created" : status == 404 ? "Not Found" : "Status";
                    string header = "HTTP/1.1 " + status + " " + reason + "\r\n" +
                                    "Content-Type: application/json\r\n" +
                                    "Content-Length: " + payload.Length + "\r\n" +
                                    "Connection: " + (close ? "close" : "keep-alive") + "\r\n\r\n";
                    byte[] hb = Encoding.ASCII.GetBytes(header);
                    stream.Write(hb, 0, hb.Length);
                    if (method != "HEAD") stream.Write(payload, 0, payload.Length);
                    stream.Flush();
                    if (close) return;
                }
            }
            catch { }
        }
    }

    static byte[] RewriteIdentity(byte[] source)
    {
        if (activeIdentity == RecordedIdentity) return source;
        string body = Encoding.UTF8.GetString(source).Replace(RecordedIdentity, activeIdentity);
        body = System.Text.RegularExpressions.Regex.Replace(body,
            "eyJhbGciOiJIUzI1NiJ9\\.([A-Za-z0-9_-]+)\\.", m =>
            {
                try
                {
                    string encoded = m.Groups[1].Value.Replace('-', '+').Replace('_', '/');
                    while (encoded.Length % 4 != 0) encoded += "=";
                    string json = Encoding.UTF8.GetString(Convert.FromBase64String(encoded)).Replace(RecordedIdentity, activeIdentity);
                    return "eyJhbGciOiJIUzI1NiJ9." + Convert.ToBase64String(Encoding.UTF8.GetBytes(json)).TrimEnd('=').Replace('+', '-').Replace('/', '_') + ".";
                }
                catch { return m.Value; }
            });
        body = System.Text.RegularExpressions.Regex.Replace(body,
            "(\\\"refresh_token\\\"\\s*:\\s*\\\")\\.([A-Za-z0-9_-]+)\\.([A-Za-z0-9_-]+)(\\\")", m =>
            {
                try
                {
                    byte[] packed = DecodeBase64Url(m.Groups[2].Value);
                    if (packed.Length < 6) return m.Value;
                    string json;
                    using (var input = new MemoryStream(packed, 2, packed.Length - 6))
                    using (var deflate = new System.IO.Compression.DeflateStream(input, System.IO.Compression.CompressionMode.Decompress))
                    using (var output = new MemoryStream())
                    {
                        deflate.CopyTo(output);
                        json = Encoding.UTF8.GetString(output.ToArray()).Replace(RecordedIdentity, activeIdentity);
                    }
                    byte[] raw;
                    using (var output = new MemoryStream())
                    {
                        using (var deflate = new System.IO.Compression.DeflateStream(output, System.IO.Compression.CompressionLevel.Optimal, true))
                        {
                            byte[] plain = Encoding.UTF8.GetBytes(json); deflate.Write(plain, 0, plain.Length);
                        }
                        raw = output.ToArray();
                    }
                    byte[] zlib = new byte[raw.Length + 6]; zlib[0] = 0x78; zlib[1] = 0x9c;
                    Buffer.BlockCopy(raw, 0, zlib, 2, raw.Length);
                    uint a = 1, b = 0;
                    for (int i = 0; i < Encoding.UTF8.GetByteCount(json); i++) { a = (a + Encoding.UTF8.GetBytes(json)[i]) % 65521; b = (b + a) % 65521; }
                    uint sum = (b << 16) | a; int end = zlib.Length - 4;
                    zlib[end] = (byte)(sum >> 24); zlib[end + 1] = (byte)(sum >> 16); zlib[end + 2] = (byte)(sum >> 8); zlib[end + 3] = (byte)sum;
                    return m.Groups[1].Value + "." + Base64Url(zlib) + "." + m.Groups[3].Value + m.Groups[4].Value;
                }
                catch { return m.Value; }
            });
        return Encoding.UTF8.GetBytes(body);
    }

    static byte[] DecodeBase64Url(string value)
    {
        value = value.Replace('-', '+').Replace('_', '/');
        while (value.Length % 4 != 0) value += "=";
        return Convert.FromBase64String(value);
    }

    static string Base64Url(byte[] value)
    {
        return Convert.ToBase64String(value).TrimEnd('=').Replace('+', '-').Replace('/', '_');
    }

    // Reads bytes up to and including CRLFCRLF; returns header text without it.
    static string ReadHead(NetworkStream s)
    {
        var buf = new List<byte>(1024);
        int matched = 0;
        while (true)
        {
            int b = s.ReadByte();
            if (b < 0) return null;
            buf.Add((byte)b);
            if ((matched % 2 == 0 && b == '\r') || (matched % 2 == 1 && b == '\n')) matched++;
            else matched = (b == '\r') ? 1 : 0;
            if (matched == 4) break;
            if (buf.Count > 65536) return null;
        }
        return Encoding.ASCII.GetString(buf.ToArray(), 0, buf.Count - 4);
    }
}
