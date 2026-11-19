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
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Fractured Space Bootstrapper Offline")]
[assembly: System.Reflection.AssemblyProduct("Fractured Space Bootstrapper Offline")]
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("1.0.0.0")]

static class OfflineLauncher
{
    const string Title = "Fractured Space Bootstrapper Offline";
    const string Prefix = "https://api.fireteam.net/";
    static readonly Dictionary<string, Canned> canned = new Dictionary<string, Canned>();
    static readonly Dictionary<string, Canned> byPath = new Dictionary<string, Canned>();
    static string logPath;
    static readonly object logLock = new object();

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

        bool created;
        using (var mutex = new Mutex(true, "FracturedSpaceBootstrapperOffline_" + port, out created))
        {
            if (!created) { Fail("El lanzador offline ya está en marcha."); return 1; }
            try { File.WriteAllText(logPath, ""); } catch { }

            try { LoadResponses(Path.Combine(appDir, "responses.json")); }
            catch (Exception ex) { Fail("No se pudo leer responses.json:\n" + ex.Message); return 1; }

            TcpListener listener;
            try
            {
                listener = new TcpListener(IPAddress.Loopback, port);
                listener.Start();
            }
            catch (Exception ex)
            {
                Fail("El puerto " + port + " está ocupado (¿hay otro servidor offline o el juego abierto?).\n\n" + ex.Message);
                return 1;
            }
            var serverThread = new Thread(() => Serve(listener)) { IsBackground = true };
            serverThread.Start();
            Log("Servidor local en http://127.0.0.1:" + port);

            if (serveOnly)
            {
                Thread.Sleep(Timeout.Infinite);
                return 0;
            }

            string gameRoot = FindGame(appDir);
            if (gameRoot == null) { Fail("No se encuentra Fractured Space instalado en Steam."); return 1; }
            string exe = Path.Combine(gameRoot, @"spacegame\Binaries\Win64\Fractured Space.exe");
            if (!File.Exists(exe)) { Fail("No se encuentra:\n" + exe); return 1; }
            if (!File.Exists(Path.Combine(gameRoot, "bootlegger.json")))
            {
                Fail("El juego no está parcheado.\nVuelve a ejecutar el instalador de Fractured Space Offline.");
                return 1;
            }
            if (Process.GetProcessesByName("Fractured Space").Length > 0)
            {
                Fail("Fractured Space ya está abierto. Ciérralo antes de usar el modo offline.");
                return 1;
            }

            var psi = new ProcessStartInfo(exe,
                "-flhost=http://127.0.0.1:" + port + " -discord=offline -culture=en-GB");
            psi.WorkingDirectory = Path.GetDirectoryName(exe);
            psi.UseShellExecute = false;
            psi.EnvironmentVariables["SteamAppId"] = "310380";
            psi.EnvironmentVariables["OPENSSL_ia32cap"] = ":~0x20000000";
            try { Process.Start(psi).WaitForExit(); }
            catch (Exception ex) { Fail("No se pudo abrir el juego:\n" + ex.Message); return 1; }

            // The game may relaunch itself; wait until no instance remains.
            do { Thread.Sleep(3000); } while (Process.GetProcessesByName("Fractured Space").Length > 0);
            listener.Stop();
            return 0;
        }
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
                        status = c.Status; payload = c.Body;
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
