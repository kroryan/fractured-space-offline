using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;

sealed class TrainerBridge : IDisposable
{
    Process worker;
    string endpoint;
    readonly string token = Guid.NewGuid().ToString("N");
    public void Start(string appDir, string gameRoot)
    {
        var socket = new TcpListener(IPAddress.Loopback, 0); socket.Start();
        int port = ((IPEndPoint)socket.LocalEndpoint).Port; socket.Stop();
        endpoint = "http://127.0.0.1:" + port + "/?t=" + token;
        var psi = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"WindowsPowerShell\v1.0\powershell.exe"),
            "-NoProfile -ExecutionPolicy Bypass -STA -File \"" + Path.Combine(appDir, @"trainer\FracturedSpaceSoloTrainer_v20.ps1") + "\"");
        psi.UseShellExecute = false; psi.CreateNoWindow = true;
        psi.EnvironmentVariables["FSO_TRAINER_PORT"] = port.ToString();
        psi.EnvironmentVariables["FSO_TRAINER_TOKEN"] = token;
        psi.EnvironmentVariables["FSO_TRAINER_PARENT"] = Process.GetCurrentProcess().Id.ToString();
        psi.EnvironmentVariables["FSO_TRAINER_SERVER"] = Path.Combine(gameRoot, @"spacegame\Binaries\Win64\spserver_original.exe");
        worker = Process.Start(psi);
    }
    public string Action(string action, string ship)
    {
        if (worker == null || worker.HasExited) return "Trainer unavailable. Restart the offline launcher.";
        var request = (HttpWebRequest)WebRequest.Create(endpoint + "&name=" + Uri.EscapeDataString(action) + "&ship=" + Uri.EscapeDataString(ship ?? ""));
        request.Proxy = null; request.Method = "POST"; request.ContentLength = 0; request.Timeout = 20000;
        using (var response = request.GetResponse())
        using (var reader = new StreamReader(response.GetResponseStream())) return reader.ReadToEnd();
    }
    public void Dispose() { if (worker != null) { try { if (!worker.HasExited) worker.Kill(); } catch { } worker.Dispose(); worker = null; } }
}
