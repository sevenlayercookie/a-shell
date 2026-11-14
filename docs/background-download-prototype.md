# Background download prototype

This branch is kept for reference and is not meant to be merged. It adds a
`download` command that hands one URL to a background `URLSession`, to test
whether the system download service is faster than downloading inside a-Shell
while the app is not on screen. It was not: both slow down to the same range.

All measurements below were taken on 14 November 2026 on one iPhone running
iOS 26 with TestFlight builds 612 and 613. Speeds are in megabytes per second.

## What a background command gets

Measured with `tests/background-probe.py` and
`tests/background-network-probe.py`, run as `background python3 ...` under a
continued processing task.

- **CPU:** each thread runs at about one eighth of its foreground speed while
  another app or the Home Screen is in front. The drop and the recovery each
  take about a second. Raising the thread from default to user-initiated
  priority changed nothing.
- **Suspension:** the app kept running. One 4-second pause was seen in about
  twelve minutes of runs.
- **Network on a slow link (1-2 MB/s):** no clear limit. With another app in
  use the speed fell 35-40%, which was mostly that app's own traffic; on the
  Home Screen it fell about 15%, which is within the noise.
- **Network on a fast link:** 37 MB/s on screen fell to 25 MB/s and then to
  about 11 MB/s in the background, with stalls of several seconds, and returned
  to 31 MB/s within a second of coming back. The download thread was busy 2-4%
  of the time, so the CPU limit does not explain it.
- **Four connections instead of one:** inconclusive. The link only gave 9 MB/s
  on screen during that run. The total stayed near 10 MB/s for the first minute
  in the background and sagged to about 6 MB/s after 90 seconds.

## The prototype

`download [-o file] url` starts the transfer, prints the speed once a second
and writes each line to `download.log`. `download cancel` stops it. Ctrl-C
stops the command but not the transfer. It handles one download at a time and
keeps no state across launches. The code is in `a-Shell/DownloadCommand.swift`.

Plain HTTP is refused with an App Transport Security error. The Info.plist sets
`NSAllowsArbitraryLoads`, but iOS ignores it because
`NSAllowsArbitraryLoadsInWebContent` is also present. Python downloads are not
subject to that policy.

## Results

Both runs fetched `https://mirror.nforce.com/pub/speedtests/1000mb.bin`.

| Run | On screen | Away from a-Shell |
|---|---|---|
| `download`, app suspended | about 11 MB/s | at least 6.0 MB/s (846 MB in 140 s) |
| `background download`, app kept alive | about 11.5 MB/s | about 5.9 MB/s (313 MB in 53 s) |
| In-app Python downloads, for comparison | 9-37 MB/s | 6-11 MB/s |

Caveats:

- The suspended run is a lower bound. The prototype cannot see when the
  transfer finished while the app was suspended.
- The server gave 11 MB/s on screen during these runs, not the 37 MB/s seen
  earlier, so there was less room for a difference.
- In the second run, stalls to under 1 MB/s also happened after returning to
  the app, so some stalling comes from the Wi-Fi or the server.

## Conclusion

The system service slows down the same way as in-app downloads, which suggests
the limit applies to network traffic whenever a-Shell is not the app on screen.
That cause is not proven. A full version of the command was estimated at two to
three days and was not built.

Not tested: whether an audio, Picture in Picture or location background mode
changes the CPU or network limits.
