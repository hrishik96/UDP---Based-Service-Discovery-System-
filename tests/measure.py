import os
import socket
import sys
import threading
import time

REGISTRY_IP = sys.argv[1]
SERVICE = sys.argv[2]
CLIENTS = int(sys.argv[3])
REQUESTS = int(sys.argv[4])
LABEL = sys.argv[5]

latencies = []
lost = [0]
lock = threading.Lock()


def worker():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    for _ in range(REQUESTS):
        start = time.time()
        sock.sendto(("DISCOVER|%s" % SERVICE).encode(), (REGISTRY_IP, 5000))
        try:
            sock.recvfrom(1024)
            ms = (time.time() - start) * 1000
            with lock:
                latencies.append(ms)
        except socket.timeout:
            with lock:
                lost[0] += 1
        time.sleep(0.05)
    sock.close()


threads = [threading.Thread(target=worker) for _ in range(CLIENTS)]
for t in threads:
    t.start()
for t in threads:
    t.join()

latencies.sort()
total = CLIENTS * REQUESTS
ok = len(latencies)
if ok:
    mean = sum(latencies) / ok
    p95 = latencies[min(ok - 1, int(ok * 0.95))]
    low = latencies[0]
    high = latencies[-1]
else:
    mean = p95 = low = high = 0.0

print("controller=%s clients=%d requests=%d lost=%d" % (LABEL, CLIENTS, total, lost[0]))
print("latency ms: mean=%.2f min=%.2f p95=%.2f max=%.2f" % (mean, low, p95, high))

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(out_dir, exist_ok=True)
path = os.path.join(out_dir, "latency.csv")
new_file = not os.path.exists(path)
with open(path, "a") as f:
    if new_file:
        f.write("controller,clients,requests,lost,mean_ms,min_ms,p95_ms,max_ms\n")
    f.write("%s,%d,%d,%d,%.2f,%.2f,%.2f,%.2f\n"
            % (LABEL, CLIENTS, total, lost[0], mean, low, p95, high))
