using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

// Personal mutable data is separate from the recorded inventory and account unlocks.
class ProfileStore
{
    readonly object gate = new object();
    readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
    readonly string file;
    Dictionary<string, object> saved;
    readonly Dictionary<string, object> defaults = new Dictionary<string, object>();
    static readonly HashSet<string> Stats = new HashSet<string> { "player_stats", "player_mode_stats", "ship_stats", "combo_stats" };
    public ProfileStore(string directory, string identity)
    {
        if (identity.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 || identity.Contains("/") || identity.Contains("\\")) throw new InvalidDataException("Invalid player identity");
        Directory.CreateDirectory(directory);
        file = Path.Combine(directory, identity + ".json");
        saved = File.Exists(file) ? json.Deserialize<Dictionary<string, object>>(File.ReadAllText(file)) : new Dictionary<string, object>();
    }
    static string TypeOf(string path)
    {
        var p = path.Split('/'); return p.Length > 1 && p[0] == "o" ? p[1] : "";
    }
    public void Register(string path, byte[] body)
    {
        string type = TypeOf(path);
        if (!Stats.Contains(type) && type != "player_wallet") return;
        var value = json.DeserializeObject(Encoding.UTF8.GetString(body));
        if (Stats.Contains(type)) Clear(value);
        if (type == "player_wallet") ((Dictionary<string, object>)value)["sp_games_played"] = 0;
        defaults[path] = value;
    }
    static void Clear(object value)
    {
        var d = value as Dictionary<string, object>;
        if (d != null)
        {
            foreach (string key in new List<string>(d.Keys))
            {
                if (key.StartsWith("_") || key == "page" || key == "mmrVersion") continue;
                object v = d[key];
                if (v is int || v is long || v is decimal || v is double) d[key] = 0;
                else if (key == "lastCompletedMatches" || key == "topMasteries") d[key] = new object[0];
                else if (key.StartsWith("last") && v is string && ((string)v).EndsWith("GMT")) d[key] = "Mon, 01 Jan 2001 00:00:00 GMT";
                else Clear(v);
            }
            d.Remove("next_page");
        }
        var list = value as object[];
        if (list != null) foreach (object child in list) Clear(child);
    }
    void Save()
    {
        string temp = file + ".tmp";
        File.WriteAllText(temp, json.Serialize(saved), Encoding.UTF8);
        if (File.Exists(file)) File.Replace(temp, file, file + ".bak"); else File.Move(temp, file);
    }
    public bool Handle(string method, string path, byte[] body, out byte[] result)
    {
        lock (gate)
        {
            result = null;
            string key = path;
            if (!defaults.ContainsKey(key))
            {
                string type = TypeOf(path);
                if (!Stats.Contains(type) && type != "player_wallet") return false;
                foreach (string candidate in defaults.Keys)
                    if (TypeOf(candidate) == type && candidate.Split('/').Length == path.Split('/').Length) { key = candidate; break; }
            }
            if (!defaults.ContainsKey(key)) return false;
            object value = saved.ContainsKey(key) ? saved[key] : defaults[key];
            if (method == "PUT" || method == "PATCH")
            {
                var patch = json.DeserializeObject(Encoding.UTF8.GetString(body)) as Dictionary<string, object>;
                var target = json.DeserializeObject(json.Serialize(value)) as Dictionary<string, object>;
                if (patch == null || target == null) throw new InvalidDataException("Invalid profile update");
                foreach (var pair in patch)
                    if (!pair.Key.StartsWith("_") && pair.Key != "owner") target[pair.Key] = pair.Value;
                saved[key] = value = target; Save();
            }
            result = Encoding.UTF8.GetBytes(json.Serialize(value)); return true;
        }
    }
    public string Action(string action)
    {
        lock (gate)
        {
            if (action == "reset_stats")
            {
                foreach (string key in new List<string>(saved.Keys)) if (Stats.Contains(TypeOf(key))) saved.Remove(key);
                saved.Remove("_reports"); Save(); return "Statistics reset. Log in again to refresh.";
            }
            foreach (string key in defaults.Keys)
            {
                if (TypeOf(key) != "player_wallet") continue;
                var wallet = json.DeserializeObject(json.Serialize(saved.ContainsKey(key) ? saved[key] : defaults[key])) as Dictionary<string, object>;
                if (action == "level_68") wallet["xp"] = 2292942;
                else if (action == "credits_100k") wallet["sc"] = Math.Min(900000000L, Convert.ToInt64(wallet["sc"]) + 100000);
                else if (action == "credits_max") wallet["sc"] = 900000000;
                else if (action == "unlock_ships") return "All ships are already unlocked in the offline inventory.";
                else throw new InvalidDataException("Unknown menu action");
                saved[key] = wallet; Save(); return "Profile saved. Log in again to refresh.";
            }
            throw new InvalidDataException("Wallet unavailable");
        }
    }

    public void RecordMatch(string line)
    {
        lock (gate)
        {
            var report = json.DeserializeObject(line) as Dictionary<string, object>;
            var info = report["info"] as Dictionary<string, object>;
            var result = report["result"] as Dictionary<string, object>;
            string id = Convert.ToString(info["MatchId"]);
            if (String.IsNullOrEmpty(id)) return;
            var matches = saved.ContainsKey("_matches") ? new List<object>((object[])json.DeserializeObject(json.Serialize(saved["_matches"]))) : new List<object>();
            if (matches.Contains(id)) return;
            var stats = new Dictionary<string, long>();
            object raw;
            if (result.TryGetValue("StatsAmount", out raw) && raw is object[])
            foreach (Dictionary<string, object> stat in (object[])raw)
            {
                object amount;
                if (stat.TryGetValue("Amount", out amount) || stat.TryGetValue("StatAmount", out amount))
                    stats[Convert.ToString(stat["StatName"])] = Math.Max(0, Convert.ToInt64(amount));
            }
            bool won = result.ContainsKey("MatchResult") ? Convert.ToInt32(result["MatchResult"]) == 0 : result.ContainsKey("bDidWin") && Convert.ToBoolean(result["bDidWin"]);
            foreach (string key in defaults.Keys)
            {
                if (TypeOf(key) != "player_stats") continue;
                var value = json.DeserializeObject(json.Serialize(saved.ContainsKey(key) ? saved[key] : defaults[key])) as Dictionary<string, object>;
                Add(value, "gamesPlayed", 1); Add(value, "gamesCompleted", 1);
                if (won) Add(value, "gameWins", 1);
                var fields = new Dictionary<string, string> { {"Deaths", "deaths"}, {"Kills", "kills"}, {"Captures", "captures"}, {"InflictedDamage", "damageInflicted"}, {"DamageReceived", "damageReceived"} };
                foreach (var pair in fields) if (stats.ContainsKey(pair.Key)) Add(value, pair.Value, stats[pair.Key]);
                saved[key] = value;
            }
            var reports = saved.ContainsKey("_reports") ? saved["_reports"] as Dictionary<string, object> : new Dictionary<string, object>();
            reports[id] = report; saved["_reports"] = reports;
            matches.Add(id); saved["_matches"] = matches.ToArray(); Save();
        }
    }
    static void Add(Dictionary<string, object> target, string key, long value)
    {
        target[key] = (target.ContainsKey(key) ? Convert.ToInt64(target[key]) : 0) + value;
    }
}
