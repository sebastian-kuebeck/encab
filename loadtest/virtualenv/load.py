import time
import psutil
import humanize
from datetime import datetime

psutil.cpu_percent

while True:
    t = datetime.now()
    cpu = psutil.cpu_percent(interval=0)
    used = humanize.naturalsize(psutil.virtual_memory().used)
    print(f"{t}: CPU load {cpu} %, memory used: {used}", flush=True)
    time.sleep(0.01)
    