import time
import psutil
import humanize
from datetime import datetime

psutil.cpu_percent

while True:
    t = datetime.now()
    cpu = psutil.cpu_percent(interval=0)
    used = humanize.naturalsize(psutil.virtual_memory().used)

    with open("load.log", "w") as fp:
        while True:
            print(f"{t}: CPU load {cpu} %, memory used: {used}", flush=True, file=fp)
            time.sleep(0.5)
