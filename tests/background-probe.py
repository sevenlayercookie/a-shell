"""Records what a background command actually gets from iOS: run time, CPU and network.

Run `background python3 background-probe.py`, leave the app for a few minutes, then read bgprobe.log.
A gap between lines means the whole app was paused. Lines that keep coming with 0 kB mean
only the network stopped. A falling spin count means the CPU was throttled.

`background python3 background-probe.py 90 boost` raises the probe's threads to user-initiated
priority, to see whether the throttling follows the thread priority.
"""
import ctypes, statistics, sys, threading, time, urllib.request

URL = "https://proof.ovh.net/files/1Gb.dat"
seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 240
boost = "boost" in sys.argv
received = 0
errors = []
libc = ctypes.CDLL(None)

def priority():
    if boost:
        libc.pthread_set_qos_class_self_np(0x19, 0)  # QOS_CLASS_USER_INITIATED
    return libc.qos_class_self()

def download():
    global received
    priority()
    while True:
        try:
            with urllib.request.urlopen(URL, timeout=20) as response:
                while chunk := response.read(64 * 1024):
                    received += len(chunk)
                    time.sleep(0.05)  # about 1 MB/s, so the file outlasts the test
        except Exception as error:
            errors.append(f"{time.strftime('%H:%M:%S')} {error!r}")
            time.sleep(1)

threading.Thread(target=download, daemon=True).start()
before = libc.qos_class_self()
start = last = time.time()
previous = 0
gaps = stalled = 0
counts = []
with open("bgprobe.log", "w") as log:
    log.write(f"priority class {before:#x} -> {priority():#x}\n")
    while time.time() - start < seconds:
        spins, until = 0, time.perf_counter() + 0.1
        while time.perf_counter() < until:
            spins += 1
        time.sleep(max(0, 1 - (time.time() - last)))
        now = time.time()
        gap = now - last
        got, previous = received - previous, received
        counts.append(spins)
        gaps += gap > 3
        stalled += got == 0
        note = (" PAUSED" if gap > 3 else "") + (" " + errors.pop(0) if errors else "")
        log.write(f"{time.strftime('%H:%M:%S')} +{gap:5.1f}s {got // 1024:6d} kB spin {spins:8d}{note}\n")
        log.flush()
        last = now
print(f"{gaps} pauses, {stalled} seconds without data, {received // 1048576} MB in {time.time() - start:.0f}s, "
      f"spin first 3s {max(counts[:3])}, median {statistics.median(counts):.0f}. See bgprobe.log")
