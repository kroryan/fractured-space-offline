using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Threading;

// Forwards the game's UDP server port to a loopback-only spserver. Incoming
// peers must first be admitted over TCP; unapproved datagrams are discarded.
sealed class UdpRelay : IDisposable
{
    readonly UdpClient socket;
    readonly CoopAdmission admission;
    readonly IPEndPoint server = new IPEndPoint(IPAddress.Loopback, 7777);
    readonly Dictionary<IPEndPoint, UdpClient> routes = new Dictionary<IPEndPoint, UdpClient>(new EndpointComparer());
    volatile bool stopped;

    public UdpRelay(CoopAdmission gate, IPAddress bindAddress, int port)
    {
        admission = gate;
        socket = new UdpClient(new IPEndPoint(bindAddress, port));
        new Thread(ReceiveLoop) { IsBackground = true, Name = "FSO UDP relay" }.Start();
    }

    void ReceiveLoop()
    {
        while (!stopped)
        {
            IPEndPoint remote = new IPEndPoint(IPAddress.Any, 0);
            byte[] data;
            try { data = socket.Receive(ref remote); } catch { return; }
            if (admission.IsAllowed(remote.Address))
            {
                var key = new IPEndPoint(remote.Address, remote.Port);
                UdpClient upstream;
                lock (routes)
                {
                    if (!routes.TryGetValue(key, out upstream))
                    {
                        upstream = new UdpClient(new IPEndPoint(IPAddress.Any, 0));
                        routes.Add(key, upstream);
                        var peer = key;
                        ThreadPool.QueueUserWorkItem(_ => UpstreamLoop(upstream, peer));
                    }
                }
                try { upstream.Send(data, data.Length, server); } catch { }
            }
        }
    }

    void UpstreamLoop(UdpClient upstream, IPEndPoint peer)
    {
        while (!stopped)
        {
            IPEndPoint from = new IPEndPoint(IPAddress.Any, 0);
            byte[] data;
            try { data = upstream.Receive(ref from); } catch { return; }
            try { socket.Send(data, data.Length, peer); } catch { return; }
        }
    }

    public void Dispose()
    {
        stopped = true;
        try { socket.Close(); } catch { }
        lock (routes) { foreach (var s in routes.Values) try { s.Close(); } catch { } routes.Clear(); }
    }

    sealed class EndpointComparer : IEqualityComparer<IPEndPoint>
    {
        public bool Equals(IPEndPoint a, IPEndPoint b) { return a != null && b != null && a.Port == b.Port && a.Address.Equals(b.Address); }
        public int GetHashCode(IPEndPoint e) { return e.Address.GetHashCode() ^ e.Port; }
    }
}
