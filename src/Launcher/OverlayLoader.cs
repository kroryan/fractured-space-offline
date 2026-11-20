using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

static class OverlayLoader
{
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr VirtualAllocEx(IntPtr process, IntPtr address, UIntPtr size, uint type, uint protect);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool WriteProcessMemory(IntPtr process, IntPtr address, byte[] bytes, UIntPtr size, out UIntPtr written);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr module, string name);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern IntPtr GetModuleHandle(string name);
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr CreateRemoteThread(IntPtr process, IntPtr attributes, UIntPtr stack, IntPtr start, IntPtr arg, uint flags, IntPtr id);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr handle, uint timeout);
    [DllImport("kernel32.dll")] static extern bool GetExitCodeThread(IntPtr thread, out uint code);
    [DllImport("kernel32.dll")] static extern bool VirtualFreeEx(IntPtr process, IntPtr address, UIntPtr size, uint type);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    public static void Load(Process game, string dll)
    {
        if (!File.Exists(dll)) throw new FileNotFoundException("F1 menu DLL missing", dll);
        IntPtr process = OpenProcess(0x43A, false, game.Id);
        if (process == IntPtr.Zero) throw new Win32Exception();
        IntPtr memory = IntPtr.Zero, thread = IntPtr.Zero;
        bool completed = false;
        try
        {
            byte[] path = Encoding.Unicode.GetBytes(Path.GetFullPath(dll) + "\0");
            memory = VirtualAllocEx(process, IntPtr.Zero, (UIntPtr)path.Length, 0x3000, 4);
            UIntPtr written;
            if (memory == IntPtr.Zero || !WriteProcessMemory(process, memory, path, (UIntPtr)path.Length, out written) || written.ToUInt64() != (ulong)path.Length) throw new Win32Exception();
            thread = CreateRemoteThread(process, IntPtr.Zero, UIntPtr.Zero, GetProcAddress(GetModuleHandle("kernel32.dll"), "LoadLibraryW"), memory, 0, IntPtr.Zero);
            if (thread == IntPtr.Zero) throw new Win32Exception();
            completed = WaitForSingleObject(thread, 15000) == 0;
            uint code;
            if (!completed || !GetExitCodeThread(thread, out code) || code == 0) throw new Exception("F1 DLL did not load");
        }
        finally
        {
            // Keep the path allocated if the remote loader is still using it.
            if (memory != IntPtr.Zero && completed) VirtualFreeEx(process, memory, UIntPtr.Zero, 0x8000);
            if (thread != IntPtr.Zero) CloseHandle(thread);
            CloseHandle(process);
        }
    }
}
