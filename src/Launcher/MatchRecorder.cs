using System;
using System.IO;
using System.Text;

sealed class MatchRecorder
{
    readonly string file;
    readonly ProfileStore profile;
    readonly Action<string> log;
    long offset;
    string pending = "";
    public MatchRecorder(string path, ProfileStore store, Action<string> logger)
    {
        file = path; profile = store; log = logger;
        offset = File.Exists(file) ? new FileInfo(file).Length : 0;
    }
    public void Poll()
    {
        try
        {
            if (!File.Exists(file)) return;
            using (var input = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            {
                if (input.Length < offset) offset = 0;
                input.Position = offset;
                using (var reader = new StreamReader(input, Encoding.UTF8, true, 1024, true)) pending += reader.ReadToEnd();
                offset = input.Position;
            }
            int end;
            while ((end = pending.IndexOf('\n')) >= 0)
            {
                string line = pending.Substring(0, end).Trim().Trim('\uFEFF');
                pending = pending.Substring(end + 1);
                if (line.Length > 0) profile.RecordMatch(line);
            }
        }
        catch (Exception error) { log("Match statistics: " + error.Message); }
    }
}
