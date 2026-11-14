"""Shows whether iOS limits the bandwidth of a background command, apart from limiting its CPU.

The download reads plain HTTP from a raw socket and discards it: no TLS, no decryption, no disk
writes. That needs so little CPU that a drop in speed after leaving the app is a network limit.

Run `background python3 background-network-probe.py`, stay in the app for 15 seconds, use another
app for 30 seconds, return, then read netprobe.log. It discards up to a few GB of data; use Wi-Fi.
`cpu` instead hashes on one thread and on four, to show whether the CPU limit is per thread.
"""
import hashlib, socket, sys, threading, time
from urllib.parse import urlsplit

URLS = ["http://cachefly.cachefly.net/100mb.test",
        "http://ipv4.download.thinkbroadband.com/1GB.zip",
        "http://mirror.nforce.com/pub/speedtests/1000mb.bin",
        "http://speedtest.belwue.net/1G"]
numbers = [int(a) for a in sys.argv[1:] if a.isdigit()]
seconds = numbers[0] if numbers else 60
received = 0
busy = 0.0  # CPU seconds the download thread has used
errors = []

def fetch(url, until):
    """Read one response until it ends or the deadline passes; return the bytes received."""
    global received, busy
    parts, buffer, total = urlsplit(url), bytearray(1 << 20), 0
    with socket.create_connection((parts.hostname, 80), timeout=15) as connection:
        connection.sendall(f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}\r\nConnection: close\r\n\r\n".encode())
        while time.time() < until and (count := connection.recv_into(buffer)):
            total += count
            received += count
            busy = time.thread_time()
    return total

def download(url):
    while True:
        try:
            fetch(url, float("inf"))
        except Exception as error:
            errors.append(repr(error))
            time.sleep(1)

def hashed(threads, duration=0.3):
    """MB hashed by this many threads at once; hashing releases Python's lock."""
    block, counts = bytes(1 << 20), [0] * threads
    def work(i):
        until = time.perf_counter() + duration
        while time.perf_counter() < until:
            hashlib.sha256(block)
            counts[i] += 1
    workers = [threading.Thread(target=work, args=(i,)) for i in range(threads)]
    for w in workers: w.start()
    for w in workers: w.join()
    return sum(counts)

def spin():
    count, until = 0, time.perf_counter() + 0.1
    while time.perf_counter() < until:
        count += 1
    return count

cpu = "cpu" in sys.argv
if not cpu:
    speeds = {}
    for url in URLS:
        try:
            speeds[url] = fetch(url, time.time() + 2)
        except Exception as error:
            speeds[url] = 0
    url = max(speeds, key=speeds.get)
    print(f"Using {urlsplit(url).hostname} ({speeds[url] / 2 / 1048576:.1f} MB/s in a 2 s trial). Switch apps after 15 s.", flush=True)
    received, busy = 0, 0.0  # the trial ran on this thread; the download thread starts from zero
    threading.Thread(target=download, args=(url,), daemon=True).start()

start = last = time.time()
previous, used = 0, busy
with open("netprobe.log", "w") as log:
    while time.time() - start < seconds:
        if cpu:
            line = f"hash 1 thread {hashed(1) / 0.3:5.0f} MB/s, 4 threads {hashed(4) / 0.3:5.0f} MB/s, spin {spin():8d}"
        else:
            line = f"spin {spin():8d}"
        time.sleep(max(0, 1 - (time.time() - last)))
        now = time.time()
        if not cpu:
            got, previous = received - previous, received
            share, used = (busy - used) / (now - last), busy
            line = f"{got / 1048576 / (now - last):6.1f} MB/s, download thread busy {share:4.0%}, " + line
        log.write(f"{time.strftime('%H:%M:%S')} +{now - last:4.1f}s {line}{' ' + errors.pop(0) if errors else ''}\n")
        log.flush()
        last = now
print(f"Done in {time.time() - start:.0f}s" + ("" if cpu else f", {received // 1048576} MB discarded") + ". See netprobe.log")
