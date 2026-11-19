// Explicit co-op admission over TCP. This service accepts join requests only; it
// exposes no account-management or server-administration commands.
// C# 5 / .NET Framework. Guest IDs are created only after host approval.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

sealed class CoopAdmission : IDisposable
{
    readonly TcpListener listener;
    readonly string stateFile;
    readonly Func<string, bool> approve;
    readonly object gate = new object();
    Dictionary<string, string> guests;
    readonly HashSet<string> allowedPeers = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    volatile bool stopped;
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    public CoopAdmission(IPAddress bindAddress, string statePath, Func<string, bool> approval)
    {
        stateFile = statePath;
        approve = approval;
        guests = Load();
        listener = new TcpListener(bindAddress, 8090);
        listener.Start();
        var t = new Thread(AcceptLoop) { IsBackground = true, Name = "FSO co-op admission" };
        t.Start();
    }

    Dictionary<string, string> Load()
    {
        try { return Json.Deserialize<Dictionary<string, string>>(File.ReadAllText(stateFile, Encoding.UTF8)) ?? new Dictionary<string, string>(); }
        catch { return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase); }
    }

    void AcceptLoop()
    {
        while (!stopped)
        {
            TcpClient c;
            try { c = listener.AcceptTcpClient(); } catch { return; }
            ThreadPool.QueueUserWorkItem(_ => Handle(c));
        }
    }

    void Handle(TcpClient c)
    {
        using (c)
        {
            c.ReceiveTimeout = 30000; c.SendTimeout = 30000;
            try
            {
                var stream = c.GetStream();
                var sr = new StreamReader(stream, Encoding.UTF8, false, 1024, true);
                var sw = new StreamWriter(stream, new UTF8Encoding(false), 1024, true) { AutoFlush = true };
                string line = sr.ReadLine();
                if (line == null || line.Length > 4096) { Reply(sw, "rejected", ""); return; }
                var request = Json.Deserialize<Dictionary<string, object>>(line);
                if (!request.ContainsKey("op") || Convert.ToString(request["op"]) != "join") { Reply(sw, "rejected", ""); return; }
                string prior = request.ContainsKey("id") ? Convert.ToString(request["id"]) : "";
                string id;
                lock (gate) guests.TryGetValue(prior, out id);
                if (id != null) { Reply(sw, "accepted", id); return; }

                string peer = ((IPEndPoint)c.Client.RemoteEndPoint).Address.ToString();
                bool accepted;
                lock (gate) accepted = guests.TryGetValue(prior, out id);
                if (!accepted) accepted = approve(peer);
                if (!accepted) { Reply(sw, "rejected", ""); return; }
                if (String.IsNullOrEmpty(id)) id = Guid.NewGuid().ToString();
                lock (gate)
                {
                    guests[id] = id;
                    allowedPeers.Add(peer);
                    Directory.CreateDirectory(Path.GetDirectoryName(stateFile));
                    File.WriteAllText(stateFile, Json.Serialize(guests), Encoding.UTF8);
                }
                Reply(sw, "accepted", id);
            }
            catch { }
        }
    }

    public bool IsAllowed(IPAddress address)
    {
        string ip = address.IsIPv4MappedToIPv6 ? address.MapToIPv4().ToString() : address.ToString();
        lock (gate) return allowedPeers.Contains(ip);
    }

    static void Reply(StreamWriter w, string status, string id)
    {
        w.WriteLine(Json.Serialize(new Dictionary<string, string> { { "status", status }, { "id", id } }));
    }

    public void Dispose()
    {
        stopped = true;
        try { listener.Stop(); } catch { }
    }

    public static string Request(string host, string savedId, int timeoutMs)
    {
        using (var client = new TcpClient())
        {
            var ar = client.BeginConnect(host, 8090, null, null);
            if (!ar.AsyncWaitHandle.WaitOne(timeoutMs)) throw new TimeoutException("Host did not answer on TCP 8090.");
            client.EndConnect(ar); client.ReceiveTimeout = timeoutMs; client.SendTimeout = timeoutMs;
            var stream = client.GetStream();
            var sw = new StreamWriter(stream, new UTF8Encoding(false), 1024, true) { AutoFlush = true };
            var sr = new StreamReader(stream, Encoding.UTF8, false, 1024, true);
            sw.WriteLine(Json.Serialize(new Dictionary<string, string> { { "op", "join" }, { "id", savedId ?? "" } }));
            var response = Json.Deserialize<Dictionary<string, object>>(sr.ReadLine());
            if (response == null || Convert.ToString(response["status"]) != "accepted") throw new UnauthorizedAccessException("The host rejected the join request.");
            return Convert.ToString(response["id"]);
        }
    }
}
