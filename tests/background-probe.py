"""Records what a background command actually gets from iOS: run time, CPU and network.

Run `background python3 background-probe.py`, leave the app for a few minutes, then read bgprobe.log.
A gap between lines means the whole app was paused. Lines that keep coming with 0 kB mean
only the network stopped. A falling spin count means the CPU was throttled.
"""
import sys, threading, time, urllib.request

URL = "https://proof.ovh.net/files/1Gb.dat"
seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 240
received = 0
errors = []

def download():
    global received
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
start = last = time.time()
previous = 0
gaps = stalled = 0
with open("bgprobe.log", "w") as log:
    while time.time() - start < seconds:
        spins, until = 0, time.perf_counter() + 0.1
        while time.perf_counter() < until:
            spins += 1
        time.sleep(max(0, 1 - (time.time() - last)))
        now = time.time()
        gap = now - last
        got, previous = received - previous, received
        gaps += gap > 3
        stalled += got == 0
        note = (" PAUSED" if gap > 3 else "") + (" " + errors.pop(0) if errors else "")
        log.write(f"{time.strftime('%H:%M:%S')} +{gap:5.1f}s {got // 1024:6d} kB spin {spins:8d}{note}\n")
        log.flush()
        last = now
print(f"{gaps} pauses, {stalled} seconds without data, {received // 1048576} MB in {time.time() - start:.0f}s. See bgprobe.log")
