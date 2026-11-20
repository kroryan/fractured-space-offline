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
    public sealed class JoinResult
    {
        public string PlayerId;
        public int Team;
    }

    readonly TcpListener listener;
    readonly string stateFile;
    readonly string teamsFile;
    readonly int partySize;
    readonly int hostTeamSize;
    readonly Func<string, int, bool> approve;
    readonly object gate = new object();
    Dictionary<string, string> guests;
    Dictionary<string, int> guestTeams;
    readonly Dictionary<string, int> sessionTeams = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    readonly Dictionary<Guid, int> pendingTeams = new Dictionary<Guid, int>();
    readonly HashSet<string> allowedPeers = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    volatile bool stopped;
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    public CoopAdmission(IPAddress bindAddress, string statePath, string teamStatePath,
                         int expectedPlayers, int expectedHostTeamSize,
                         Func<string, int, bool> approval)
    {
        stateFile = statePath;
        teamsFile = teamStatePath;
        partySize = Math.Max(2, Math.Min(4, expectedPlayers));
        hostTeamSize = Math.Max(1, Math.Min(partySize, expectedHostTeamSize));
        approve = approval;
        guests = LoadGuests();
        guestTeams = LoadTeams();
        listener = new TcpListener(bindAddress, 8090);
        listener.Start();
        var t = new Thread(AcceptLoop) { IsBackground = true, Name = "FSO co-op admission" };
        t.Start();
    }

    Dictionary<string, string> LoadGuests()
    {
        try { return Json.Deserialize<Dictionary<string, string>>(File.ReadAllText(stateFile, Encoding.UTF8)) ?? new Dictionary<string, string>(); }
        catch { return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase); }
    }

    Dictionary<string, int> LoadTeams()
    {
        try { return Json.Deserialize<Dictionary<string, int>>(File.ReadAllText(teamsFile, Encoding.UTF8)) ?? new Dictionary<string, int>(); }
        catch { return new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase); }
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

    int ReserveTeam(Guid reservation)
    {
        int teamOneUsed = 0, teamTwoUsed = 0;
        foreach (int team in sessionTeams.Values)
        { if (team == 1) teamOneUsed++; else if (team == 2) teamTwoUsed++; }
        foreach (int team in pendingTeams.Values)
        {
            if (team == 1) teamOneUsed++; else if (team == 2) teamTwoUsed++;
        }
        int teamOneCapacity = hostTeamSize - 1; // The host occupies team 1.
        int teamTwoCapacity = partySize - hostTeamSize;
        int selected = teamOneUsed < teamOneCapacity ? 1 : teamTwoUsed < teamTwoCapacity ? 2 : 0;
        if (selected != 0) pendingTeams[reservation] = selected;
        return selected;
    }

    void Handle(TcpClient c)
    {
        using (c)
        {
            c.ReceiveTimeout = 30000; c.SendTimeout = 30000;
            Guid reservation = Guid.NewGuid();
            bool reserved = false;
            try
            {
                var stream = c.GetStream();
                var sr = new StreamReader(stream, Encoding.UTF8, false, 1024, true);
                var sw = new StreamWriter(stream, new UTF8Encoding(false), 1024, true) { AutoFlush = true };
                string line = sr.ReadLine();
                if (line == null || line.Length > 4096) { Reply(sw, "rejected", "", 0); return; }
                var request = Json.Deserialize<Dictionary<string, object>>(line);
                if (!request.ContainsKey("op") || Convert.ToString(request["op"]) != "join") { Reply(sw, "rejected", "", 0); return; }
                string prior = request.ContainsKey("id") ? Convert.ToString(request["id"]) : "";
                string id;
                string peer = ((IPEndPoint)c.Client.RemoteEndPoint).Address.ToString();
                lock (gate)
                {
                    if (guests.TryGetValue(prior, out id))
                    {
                        int savedTeam;
                        if (!sessionTeams.TryGetValue(id, out savedTeam))
                        {
                            savedTeam = ReserveTeam(reservation);
                            if (savedTeam == 0) { Reply(sw, "full", "", 0); return; }
                            pendingTeams.Remove(reservation);
                            sessionTeams[id] = savedTeam;
                            guestTeams[id] = savedTeam;
                            string dir = Path.GetDirectoryName(teamsFile);
                            if (!String.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                            File.WriteAllText(teamsFile, Json.Serialize(guestTeams), Encoding.UTF8);
                        }
                        allowedPeers.Add(peer);
                        Reply(sw, "accepted", id, savedTeam);
                        return;
                    }
                    int team = ReserveTeam(reservation);
                    if (team == 0) { Reply(sw, "full", "", 0); return; }
                    reserved = true;
                }

                int assignedTeam;
                lock (gate) assignedTeam = pendingTeams[reservation];
                if (!approve(peer, assignedTeam))
                {
                    lock (gate) pendingTeams.Remove(reservation);
                    reserved = false;
                    Reply(sw, "rejected", "", 0);
                    return;
                }
                id = Guid.NewGuid().ToString();
                lock (gate)
                {
                    guests[id] = id;
                    guestTeams[id] = assignedTeam;
                    sessionTeams[id] = assignedTeam;
                    allowedPeers.Add(peer);
                    pendingTeams.Remove(reservation);
                    reserved = false;
                    string dir = Path.GetDirectoryName(stateFile);
                    if (!String.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                    File.WriteAllText(stateFile, Json.Serialize(guests), Encoding.UTF8);
                    File.WriteAllText(teamsFile, Json.Serialize(guestTeams), Encoding.UTF8);
                }
                Reply(sw, "accepted", id, assignedTeam);
            }
            catch { }
            finally { if (reserved) lock (gate) pendingTeams.Remove(reservation); }
        }
    }

    public bool IsAllowed(IPAddress address)
    {
        string ip = address.IsIPv4MappedToIPv6 ? address.MapToIPv4().ToString() : address.ToString();
        lock (gate) return allowedPeers.Contains(ip);
    }

    static void Reply(StreamWriter w, string status, string id, int team)
    {
        w.WriteLine(Json.Serialize(new Dictionary<string, object> {
            { "status", status }, { "id", id }, { "team", team }
        }));
    }

    public void Dispose()
    {
        stopped = true;
        try { listener.Stop(); } catch { }
    }

    public static JoinResult Request(string host, string savedId, int timeoutMs)
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
            if (response == null || Convert.ToString(response["status"]) != "accepted")
            {
                if (response != null && Convert.ToString(response["status"]) == "full")
                    throw new InvalidOperationException("The host's selected co-op player capacity is full.");
                throw new UnauthorizedAccessException("The host rejected the join request.");
            }
            object teamValue;
            int team = response.TryGetValue("team", out teamValue) ? Convert.ToInt32(teamValue) : 2;
            return new JoinResult { PlayerId = Convert.ToString(response["id"]), Team = team };
        }
    }
}
