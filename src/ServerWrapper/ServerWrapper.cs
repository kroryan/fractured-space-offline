// Fractured Space Offline - spserver.exe wrapper.
//
// "Training -> Solo vs AI" makes the game client start
//   spacegame\Binaries\Win64\spserver.exe /Game/Maps/Lobby?game=spacegame.SinglePlayerLobbyGameMode ...
// and read its console output for "lobby_ready", "ecg_fs_sp_server_host=" and
// "ecg_fs_sp_server_port=", then connect to that address.
//
// The installer renames the original server to spserver_original.exe and puts
// this wrapper in its place. The mode comes from environment variables, which
// the offline launcher sets on the game process and the game passes on to us:
//
//   (none) / FSO_COOP_MODE=solo   run the original server unchanged
//   FSO_COOP_MODE=host            run the original server on 127.0.0.1 only
//                                 (FSO_SERVER_URL_EXTRA appended to the map URL);
//                                 the launcher relays approved guests to it
//   FSO_COOP_MODE=guest           start no server: report FSO_COOP_HOST and
//                                 FSO_COOP_PORT, so this client joins the host
//
// Without the launcher (no variables) the game behaves exactly as before.
// C# 5 (compiled with .NET Framework csc).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

[assembly: System.Reflection.AssemblyTitle("Fractured Space Offline server wrapper")]
[assembly: System.Reflection.AssemblyVersion("1.1.0.0")]

static class ServerWrapper
{
    const string Original = "spserver_original.exe";

    static int Main(string[] args)
    {
        string mode = (Environment.GetEnvironmentVariable("FSO_COOP_MODE") ?? "solo").Trim().ToLowerInvariant();
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string status = Environment.GetEnvironmentVariable("FSO_COOP_STATUS"); // file the launcher watches
        try
        {
            if (mode == "guest") return Guest(status);
            return RunServer(Path.Combine(dir, Original), args, mode == "host", status);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("spserver wrapper: " + ex);
            WriteStatus(status, "error " + ex.Message);
            return 1;
        }
    }

    static void Emit(string line)
    {
        Console.Out.WriteLine(line);
        Console.Out.Flush();
    }

    static string Stamp()
    {
        return "[" + DateTime.UtcNow.ToString("yyyy.MM.dd-HH.mm.ss:fff") + "][  0]";
    }

    static void WriteStatus(string file, string text)
    {
        if (string.IsNullOrEmpty(file)) return;
        try { File.WriteAllText(file, text); } catch { }
    }

    // ---- guest: point this client at the host's server ----
    static int Guest(string status)
    {
        string host = Environment.GetEnvironmentVariable("FSO_COOP_HOST") ?? "127.0.0.1";
        string port = Environment.GetEnvironmentVariable("FSO_COOP_PORT") ?? "7777";
        Emit(Stamp() + "LogInit: Fractured Space Offline: joining the co-op host " + host + ":" + port);
        Emit(Stamp() + "SinglePlayerLobbyGameMode: Warning: lobby_ready");
        Emit(Stamp() + "SinglePlayerLobbyGameMode: Warning: ecg_fs_sp_server_host=" + host);
        Emit(Stamp() + "SinglePlayerLobbyGameMode: Warning: ecg_fs_sp_server_port=" + port);
        WriteStatus(status, "guest " + host + ":" + port);
        // The client treats our exit as the server ending: stay until it closes us.
        Thread.Sleep(Timeout.Infinite);
        return 0;
    }

    // ---- solo / host: run the original server ----
    static int RunServer(string exe, string[] args, bool host, string status)
    {
        if (!File.Exists(exe))
        {
            Console.Error.WriteLine("spserver wrapper: missing " + exe);
            return 2;
        }
        var list = new List<string>(args);
        if (host)
        {
            if (list.Count > 0 && !list[0].StartsWith("-"))
                list[0] = Regex.Replace(list[0], @"^[^?]+", "/Game/Maps/ActionConquest/Map_ActionConquest_A3_B6");
            if (list.Count > 0 && !list[0].StartsWith("-"))
                list[0] = Regex.Replace(list[0], @"(?i)(\?game=)[^?&]+", "$1/Game/Blueprints/GameModes/BP_ConquestGameMode_Coop.BP_ConquestGameMode_Coop_C");
            string extra = Environment.GetEnvironmentVariable("FSO_SERVER_URL_EXTRA") ?? "";
            if (extra.Length > 0 && list.Count > 0 && !list[0].StartsWith("-")) list[0] += extra;
            list.Add("-multihome=127.0.0.1");
            string port = Environment.GetEnvironmentVariable("FSO_SERVER_PORT");
            if (!string.IsNullOrEmpty(port)) list.Add("-port=" + port);
        }
        var psi = new ProcessStartInfo(exe, Join(list));
        psi.UseShellExecute = false;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.CreateNoWindow = true;
        psi.WorkingDirectory = Path.GetDirectoryName(exe);

        IntPtr job = CreateKillOnCloseJob();
        var p = Process.Start(psi);
        if (job != IntPtr.Zero) AssignProcessToJobObject(job, p.Handle);

        p.ErrorDataReceived += (s, e) => { if (e.Data != null) { Console.Error.WriteLine(e.Data); } };
        p.BeginErrorReadLine();
        string line;
        bool readyEmitted = false;
        while ((line = p.StandardOutput.ReadLine()) != null)
        {
            Emit(line);
            if (host && !readyEmitted && line.IndexOf("IpNetDriver listening on port", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                string port = Environment.GetEnvironmentVariable("FSO_SERVER_PORT") ?? "7777";
                Emit(Stamp() + "SinglePlayerLobbyGameMode: Warning: lobby_ready");
                Emit(Stamp() + "SinglePlayerLobbyGameMode: Warning: ecg_fs_sp_server_host=127.0.0.1");
                Emit(Stamp() + "SinglePlayerLobbyGameMode: Warning: ecg_fs_sp_server_port=" + port);
                WriteStatus(status, "host 127.0.0.1:" + port);
                readyEmitted = true;
            }
            if (host)
            {
                int i = line.IndexOf("ecg_fs_sp_server_port=", StringComparison.Ordinal);
                if (i >= 0) WriteStatus(status, "host 127.0.0.1:" + line.Substring(i + 22).Trim());
            }
        }
        p.WaitForExit();
        WriteStatus(status, "ended " + p.ExitCode);
        return p.ExitCode;
    }

    static string Join(IEnumerable<string> args)
    {
        var sb = new StringBuilder();
        foreach (var a in args)
        {
            if (sb.Length > 0) sb.Append(' ');
            if (a.Length > 0 && a.IndexOfAny(new[] { ' ', '\t', '"' }) < 0) sb.Append(a);
            else sb.Append('"').Append(a.Replace("\"", "\\\"")).Append('"');
        }
        return sb.ToString();
    }

    // The server dies with this wrapper (the client stops the process it started: us).
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimit
    {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters { public ulong a, b, c, d, e, f; }

    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimit
    {
        public BasicLimit Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern IntPtr CreateJobObject(IntPtr a, string name);
    [DllImport("kernel32.dll")] static extern bool SetInformationJobObject(IntPtr job, int cls, ref ExtendedLimit info, int len);
    [DllImport("kernel32.dll")] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    static IntPtr CreateKillOnCloseJob()
    {
        try
        {
            IntPtr job = CreateJobObject(IntPtr.Zero, null);
            var info = new ExtendedLimit();
            info.Basic.LimitFlags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            SetInformationJobObject(job, 9, ref info, Marshal.SizeOf(typeof(ExtendedLimit)));
            return job;
        }
        catch { return IntPtr.Zero; }
    }
}
