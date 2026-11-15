"""Shows whether a script's `progress` calls reach the Live Activity of an auto-backgrounded command.

Run `python3 background-progress-test.py` (no `background` prefix), leave a-Shell within a few seconds and
watch the Live Activity for two minutes. The bar should move in steps and the text should read
"subprocess 7/60", later "os.system 37/60". Text that only shows a clock means the reports are
not getting through; the method named in the text is the one that works.
"""
import os, subprocess, sys, time

steps = int(sys.argv[1]) if len(sys.argv) > 1 else 60

def by_subprocess(step):
    return subprocess.run(["progress", f"{step}/{steps}", f"subprocess {step}/{steps}"]).returncode

def by_system(step):
    return os.system(f"progress {step}/{steps} os.system {step}/{steps}")

print(f"Reporting {steps} steps, one every 2 s. Leave a-Shell now.", flush=True)
for step in range(1, steps + 1):
    time.sleep(2)
    method = by_subprocess if step <= steps // 2 else by_system
    try:
        status = method(step)
    except Exception as error:
        status = repr(error)
    print(f"{time.strftime('%H:%M:%S')} step {step:3d} {method.__name__} -> {status}", flush=True)
print("Done.")
