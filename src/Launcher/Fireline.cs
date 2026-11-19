// Local Fireline emulator (based on Tigerhacker/refireline, GPL-3.0).
// Serves recorded api.fireteam.net responses on 127.0.0.1. With an identity
// other than the recorded one (co-op guests), every response is rewritten for
// that identity, and objects requested by an unknown id are served from the
// recorded object of the same type.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;

class FirelineServer
{
    public const string RecordedIdentity = "197a97fc-4179-43f4-b009-9432ac0c8e53";
    const string Prefix = "https://api.fireteam.net/";

    class Canned { public string Method, Path, ObjectId; public int Status; public string Body; }

    readonly Dictionary<string, Canned> exact = new Dictionary<string, Canned>();
    readonly Dictionary<string, Canned> byPattern = new Dictionary<string, Canned>();
    readonly Dictionary<string, Canned> byPath = new Dictionary<string, Canned>();
    readonly string identity;
    readonly Action<string> log;
    TcpListener listener;

    public int Port { get; private set; }

    public FirelineServer(string responsesJson, string identityId, Action<string> logger)
    {
        identity = string.IsNullOrEmpty(identityId) ? RecordedIdentity : identityId.ToLowerInvariant();
        log = logger ?? (s => { });
        var ser = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        var list = (object[])ser.DeserializeObject(File.ReadAllText(responsesJson, Encoding.UTF8));
        foreach (Dictionary<string, object> e in list)
        {
            var req = (Dictionary<string, object>)e["request"];
            var res = (Dictionary<string, object>)e["response"];
            string url = (string)req["url"];
            string path = url.StartsWith(Prefix) ? url.Substring(Prefix.Length) : url;
            int q = path.IndexOf('?');
            if (q >= 0) path = path.Substring(0, q);
            var c = new Canned
            {
                Method = (string)req["method"], Path = path,
                Status = Convert.ToInt32(res["status_code"]), Body = (string)res["content"] ?? ""
            };
            string pattern = Pattern(path, out c.ObjectId);
            exact[c.Method + " " + path] = c;
            byPattern[c.Method + " " + pattern] = c;
            byPath[path] = c;
        }
    }

    static readonly Regex Guid = new Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$");

    // "o/player_info/<id>" -> "o/player_info/*", "o/_identities/<id>/inbox" -> "o/_identities/*/inbox"
    static string Pattern(string path, out string objectId)
    {
        objectId = null;
        var parts = path.Split('/');
        for (int i = 0; i < parts.Length; i++)
        {
            if (Guid.IsMatch(parts[i]))
            {
                if (objectId == null) objectId = parts[i];
                parts[i] = "*";
            }
        }
        return string.Join("/", parts);
    }

    public void Start(int port)
    {
        listener = new TcpListener(IPAddress.Loopback, port);
        listener.Start();
        Port = ((IPEndPoint)listener.LocalEndpoint).Port;
        var t = new Thread(Serve) { IsBackground = true, Name = "fireline" };
        t.Start();
        log("Local Fireline server on http://127.0.0.1:" + Port + " (identity " + identity + ")");
    }

    public void Stop()
    {
        try { if (listener != null) listener.Stop(); } catch { }
    }

    void Serve()
    {
        while (true)
        {
            TcpClient c;
            try { c = listener.AcceptTcpClient(); } catch { return; }
            ThreadPool.QueueUserWorkItem(_ => Handle(c));
        }
    }

    string Rewrite(string body, string cannedId, string requestedId)
    {
        if (identity != RecordedIdentity)
        {
            body = body.Replace(RecordedIdentity, identity);
            // The JWT's payload carries the identity in "sub": rewrite it too.
            body = Regex.Replace(body, "eyJhbGciOiJIUzI1NiJ9\\.([A-Za-z0-9_-]+)\\.", m =>
            {
                try
                {
                    string json = Encoding.UTF8.GetString(B64UrlDecode(m.Groups[1].Value)).Replace(RecordedIdentity, identity);
                    return "eyJhbGciOiJIUzI1NiJ9." + B64UrlEncode(Encoding.UTF8.GetBytes(json)) + ".";
                }
                catch { return m.Value; }
            });
        }
        if (cannedId != null && requestedId != null && cannedId != requestedId)
            body = body.Replace(cannedId, requestedId);
        return body;
    }

    static byte[] B64UrlDecode(string s)
    {
        s = s.Replace('-', '+').Replace('_', '/');
        while (s.Length % 4 != 0) s += "=";
        return Convert.FromBase64String(s);
    }

    static string B64UrlEncode(byte[] b)
    {
        return Convert.ToBase64String(b).TrimEnd('=').Replace('+', '-').Replace('/', '_');
    }

    Canned Lookup(string method, string path, out string requestedId)
    {
        Canned c;
        string pattern = Pattern(path, out requestedId);
        if (exact.TryGetValue(method + " " + path, out c)) { requestedId = null; return c; }
        if (byPattern.TryGetValue(method + " " + pattern, out c)) return c;
        foreach (var m in new[] { "GET", "PUT", "POST" })
            if (byPattern.TryGetValue(m + " " + pattern, out c)) return c;
        if (byPath.TryGetValue(path, out c)) { requestedId = null; return c; }
        return null;
    }

    void Handle(TcpClient client)
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
                    string method = first[0], target = first[1];
                    int contentLength = 0;
                    bool close = false;
                    for (int i = 1; i < lines.Length; i++)
                    {
                        int idx = lines[i].IndexOf(':');
                        if (idx <= 0) continue;
                        string name = lines[i].Substring(0, idx).Trim().ToLowerInvariant();
                        string val = lines[i].Substring(idx + 1).Trim();
                        if (name == "content-length") int.TryParse(val, out contentLength);
                        if (name == "connection" && val.ToLowerInvariant() == "close") close = true;
                    }
                    var body = new byte[Math.Max(0, Math.Min(contentLength, 1 << 20))];
                    int read = 0;
                    while (read < body.Length)
                    {
                        int n = stream.Read(body, read, body.Length - read);
                        if (n <= 0) return;
                        read += n;
                    }
                    string path = target.TrimStart('/');
                    int q = path.IndexOf('?');
                    string query = q >= 0 ? path.Substring(q + 1) : "";
                    if (q >= 0) path = path.Substring(0, q);

                    int status = 200;
                    string text;
                    string reqId;
                    if (path.Length == 0)
                    {
                        text = "Fireline Emulator for Fractured Space (offline launcher)";
                        log(method + " /");
                    }
                    else
                    {
                        var c = Lookup(method, path, out reqId);
                        if (c != null)
                        {
                            status = c.Status;
                            text = Rewrite(c.Body, reqId != null ? c.ObjectId : null, reqId);
                            log("hit  " + method + " /" + path);
                        }
                        else
                        {
                            text = "{}";
                            string b = Encoding.UTF8.GetString(body, 0, read);
                            if (b.Length > 200) b = b.Substring(0, 200);
                            log("MISS " + method + " /" + path + (query.Length > 0 ? "?" + query : "") + " " + b);
                        }
                    }
                    byte[] payload = Encoding.UTF8.GetBytes(text);
                    string reason = status == 200 ? "OK" : status == 201 ? "Created" : status == 404 ? "Not Found" : "Status";
                    byte[] hb = Encoding.ASCII.GetBytes("HTTP/1.1 " + status + " " + reason + "\r\n" +
                        "Content-Type: application/json\r\nContent-Length: " + payload.Length + "\r\n" +
                        "Connection: " + (close ? "close" : "keep-alive") + "\r\n\r\n");
                    stream.Write(hb, 0, hb.Length);
                    if (method != "HEAD") stream.Write(payload, 0, payload.Length);
                    stream.Flush();
                    if (close) return;
                }
            }
            catch { }
        }
    }

    static string ReadHead(NetworkStream s)
    {
        var buf = new List<byte>(1024);
        while (true)
        {
            int b = s.ReadByte();
            if (b < 0) return null;
            buf.Add((byte)b);
            int n = buf.Count;
            if (n >= 4 && buf[n - 4] == '\r' && buf[n - 3] == '\n' && buf[n - 2] == '\r' && buf[n - 1] == '\n') break;
            if (n > 65536) return null;
        }
        return Encoding.ASCII.GetString(buf.ToArray(), 0, buf.Count - 4);
    }
}
