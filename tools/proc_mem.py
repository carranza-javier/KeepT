"""Memory of a running process as Task Manager shows it (private working set) plus commit.
    python tools/proc_mem.py KeepT.exe
"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys

k32 = ctypes.windll.kernel32
k32.OpenProcess.restype = wt.HANDLE
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]


class PMC2(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [(n, ctypes.c_size_t) for n in (
        "PeakWorkingSetSize", "WorkingSetSize", "a", "b", "c", "d", "PagefileUsage", "PeakPagefileUsage",
        "PrivateUsage", "PrivateWorkingSetSize", "SharedCommitUsage")]


out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {sys.argv[1]}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
for line in out.strip().splitlines():
    pid = int(line.split(",")[1].strip('"'))
    h = k32.OpenProcess(0x1000 | 0x0400, False, pid)
    c = PMC2()
    c.cb = ctypes.sizeof(c)
    ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
    print(f"pid {pid}: Task Manager memory (private working set) {c.PrivateWorkingSetSize / 2**20:.0f} MB, "
          f"commit {c.PrivateUsage / 2**20:.0f} MB")
