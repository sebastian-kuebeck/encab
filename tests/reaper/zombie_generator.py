import os
import sys
import time

ttl = 2;
for i in range(0, 4):
    pid = os.fork()

    if pid == 0:
        sys.exit(0);
    else:
        print(f"Forked pid: {pid}")

time.sleep(ttl);
os.wait()
