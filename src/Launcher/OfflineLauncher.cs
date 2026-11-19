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
[assembly: System.Reflection.AssemblyVersion("1.1.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("1.1.0.0")]

static class OfflineLauncher
{
    const string Title = "Fractured Space Bootstrapper Offline";
    const string Prefix = "https://api.fireteam.net/";
    const string RecordedIdentity = "197a97fc-4179-43f4-b009-9432ac0c8e53";
    static string activeIdentity = RecordedIdentity;
    static readonly Dictionary<string, Canned> canned = new Dictionary<string, Canned>();
    static readonly Dictionary<string, Canned> byPath = new Dictionary<string, Canned>();
    static string logPath;
    static readonly object logLock = new object();
    enum PlayMode { Solo, Host, Join }
    static PlayMode selectedMode = PlayMode.Solo;
    static string selectedHost = "";
    static string selectedBindIp = "0.0.0.0";
    static bool sameTeam = true;

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
            if (!created) { Fail(L("El lanzador offline ya está en marcha.", "The offline launcher is already running.")); return 1; }
            try { File.WriteAllText(logPath, ""); } catch { }

            string playerId = LoadPlayerId(appDir);
            CoopAdmission admission = null;
            UdpRelay relay = null;
            try
            {
                if (selectedMode == PlayMode.Host)
                {
                    string state = Path.Combine(appDir, "approved-guests.json");
                    admission = new CoopAdmission(IPAddress.Parse(selectedBindIp), state, peer =>
                    {
                        DialogResult answer = DialogResult.No;
                        var t = new Thread(() => answer = MessageBox.Show(
                            L("El jugador " + peer + " solicita unirse. ¿Aceptar?", "Player " + peer + " requests to join. Accept?"),
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
                    playerId = CoopAdmission.Request(selectedHost, playerId, 120000);
                    File.WriteAllText(Path.Combine(appDir, "player-id.txt"), playerId);
                }
            }
            catch (Exception ex) { Fail(L("No se pudo iniciar/unir a la partida cooperativa:\n", "Could not host/join the co-op game:\n") + ex.Message); return 1; }
            activeIdentity = String.IsNullOrEmpty(playerId) ? RecordedIdentity : playerId;

            try { LoadResponses(Path.Combine(appDir, "responses.json")); }
            catch (Exception ex) { Fail(L("No se pudo leer responses.json:\n", "Could not read responses.json:\n") + ex.Message); return 1; }

            TcpListener listener;
            try
            {
                listener = new TcpListener(IPAddress.Loopback, port);
                listener.Start();
            }
            catch (Exception ex)
            {
                Fail(L("El puerto " + port + " está ocupado (¿hay otro servidor offline o el juego abierto?).\n\n",
                     "Port " + port + " is in use (is another offline server or the game already running?).\n\n") + ex.Message);
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
            if (gameRoot == null) { Fail(L("No se encuentra Fractured Space instalado en Steam.", "Fractured Space was not found in your Steam libraries.")); return 1; }
            string exe = Path.Combine(gameRoot, @"spacegame\Binaries\Win64\Fractured Space.exe");
            if (selectedMode != PlayMode.Solo && !File.Exists(Path.Combine(gameRoot, @"spacegame\Binaries\Win64\spserver_original.exe")))
            {
                Fail(L("No está instalado el wrapper del servidor. Vuelve a ejecutar el instalador.", "The server wrapper is not installed. Run the installer again."));
                return 1;
            }
            if (selectedMode != PlayMode.Solo && !File.Exists(Path.Combine(gameRoot, @"spacegame\Binaries\Win64\spserver_original.exe")))
            {
                Fail(L("No está instalado el wrapper del servidor. Vuelve a ejecutar el instalador.", "The server wrapper is not installed. Run the installer again."));
                return 1;
            }
            if (!File.Exists(exe)) { Fail(L("No se encuentra:\n", "Not found:\n") + exe); return 1; }
            if (!File.Exists(Path.Combine(gameRoot, "bootlegger.json")))
            {
                Fail(L("El juego no está parcheado.\nVuelve a ejecutar el instalador de Fractured Space Offline.",
                     "The game is not patched.\nRun the Fractured Space Offline installer again."));
                return 1;
            }
            if (Process.GetProcessesByName("Fractured Space").Length > 0)
            {
                Fail(L("Fractured Space ya está abierto. Ciérralo antes de usar el modo offline.",
                     "Fractured Space is already running. Close it before using offline mode."));
                return 1;
            }

            try { ConfigureDisplay(); } catch (Exception ex) { Log("Display config failed: " + ex.Message); }
            using (var progress = new LaunchProgress())
            {
                progress.Show(); progress.Set(65, L("Preparando el servidor local…", "Preparing the local server…"));
                Application.DoEvents();

            var psi = new ProcessStartInfo(exe,
                "-flhost=http://127.0.0.1:" + port + " -discord=offline -culture=en-GB");
            psi.WorkingDirectory = Path.GetDirectoryName(exe);
            psi.UseShellExecute = false;
            psi.EnvironmentVariables["SteamAppId"] = "310380";
            psi.EnvironmentVariables["OPENSSL_ia32cap"] = ":~0x20000000";
            if (selectedMode == PlayMode.Host) psi.EnvironmentVariables["FSO_COOP_MODE"] = "host";
            if (selectedMode == PlayMode.Host) psi.EnvironmentVariables["FSO_SERVER_URL_EXTRA"] = sameTeam ? "?coop=1" : "?coop=0";
            if (selectedMode == PlayMode.Join) { psi.EnvironmentVariables["FSO_COOP_MODE"] = "guest"; psi.EnvironmentVariables["FSO_COOP_HOST"] = selectedHost; }
            psi.EnvironmentVariables["FSO_PLAYER_ID"] = playerId;
            try
            {
                progress.Set(82, L("Iniciando Fractured Space…", "Starting Fractured Space…")); Application.DoEvents();
                var game = Process.Start(psi);
                progress.Set(100, L("Esperando a que aparezca la ventana del juego…", "Waiting for the game window…"));
                if (game != null)
                {
                    while (!game.HasExited && game.MainWindowHandle == IntPtr.Zero) { Thread.Sleep(500); game.Refresh(); Application.DoEvents(); }
                    progress.Close();
                    game.WaitForExit();
                }
                progress.Close();
            }
            catch (Exception ex) { Fail(L("No se pudo abrir el juego:\n", "Could not start the game:\n") + ex.Message); return 1; }
            }

            // The game may relaunch itself; wait until no instance remains.
            do { Thread.Sleep(3000); } while (Process.GetProcessesByName("Fractured Space").Length > 0);
            if (admission != null) admission.Dispose();
            if (relay != null) relay.Dispose();
            listener.Stop();
            return 0;
        }
    }

    static string LoadPlayerId(string appDir)
    {
        string f = Path.Combine(appDir, "player-id.txt");
        try { string id = File.ReadAllText(f).Trim(); Guid.Parse(id); return id; } catch { return ""; }
    }

    static bool ChooseMode(string appDir)
    {
        string file = Path.Combine(appDir, "launcher-mode.txt");
        int last = 0; try { int.TryParse(File.ReadAllText(file).Trim(), out last); } catch { }
        using (var f = new Form())
        {
            f.Text = Title; f.Width = 480; f.Height = 330; f.StartPosition = FormStartPosition.CenterScreen;
            var solo = new RadioButton { Left = 24, Top = 24, Width = 410, Text = L("Jugar solo contra bots", "Play solo vs bots"), Checked = last == 0 };
            var host = new RadioButton { Left = 24, Top = 60, Width = 410, Text = L("Crear partida cooperativa (anfitrión)", "Create co-op game (host)"), Checked = last == 1 };
            var join = new RadioButton { Left = 24, Top = 96, Width = 410, Text = L("Unirse a una partida cooperativa", "Join a co-op game"), Checked = last == 2 };
            var ipLabel = new Label { Left = 46, Top = 132, Width = 100, Text = "Host IP:" };
            var ip = new TextBox { Left = 145, Top = 128, Width = 250, Text = "127.0.0.1" };
            var bindLabel = new Label { Left = 46, Top = 166, Width = 100, Text = L("IP local:", "Local IP:") };
            var bind = new ComboBox { Left = 145, Top = 162, Width = 250, DropDownStyle = ComboBoxStyle.DropDownList };
            foreach (var a in LocalAddresses()) bind.Items.Add(a);
            if (bind.Items.Count > 0) bind.SelectedIndex = 0;
            var team = new CheckBox { Left = 46, Top = 196, Width = 370, Text = L("Jugar en el mismo equipo", "Play on the same team"), Checked = true };
            var go = new Button { Left = 300, Top = 235, Width = 100, Text = L("Continuar", "Continue"), DialogResult = DialogResult.OK };
            go.Click += (s,e) => { IPAddress parsed; if (join.Checked && !IPAddress.TryParse(ip.Text.Trim(), out parsed)) { MessageBox.Show(L("Escribe una IP válida.", "Enter a valid IP address.")); f.DialogResult = DialogResult.None; } };
            f.Controls.AddRange(new Control[] { solo, host, join, ipLabel, ip, bindLabel, bind, team, go }); f.AcceptButton = go;
            if (f.ShowDialog() != DialogResult.OK) return false;
            selectedMode = solo.Checked ? PlayMode.Solo : host.Checked ? PlayMode.Host : PlayMode.Join;
            selectedHost = ip.Text.Trim();
            selectedBindIp = bind.SelectedItem == null ? "0.0.0.0" : bind.SelectedItem.ToString().Split(' ')[0];
            sameTeam = team.Checked;
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
            Text = Title; Width = 470; Height = 135; FormBorderStyle = FormBorderStyle.FixedDialog;
            ControlBox = false; StartPosition = FormStartPosition.CenterScreen;
            label = new Label { Left = 18, Top = 16, Width = 420, Height = 24, Text = L("Buscando el juego…", "Finding the game…") };
            bar = new ProgressBar { Left = 18, Top = 52, Width = 420, Height = 22, Minimum = 0, Maximum = 100, Value = 20 };
            Controls.Add(label); Controls.Add(bar);
        }
        public void Set(int value, string text) { bar.Value = Math.Max(0, Math.Min(100, value)); label.Text = text; }
    }

    static readonly bool Spanish =
        System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es";
    static string L(string es, string en) { return Spanish ? es : en; }

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
                    if (path.Length == 0)
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
        return Encoding.UTF8.GetBytes(body);
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
