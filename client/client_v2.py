import socket
import sys
import time

REGISTRY_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
SERVICE = sys.argv[2] if len(sys.argv) > 2 else "video"
REGISTRY = (REGISTRY_IP, 5000)
ATTEMPTS = 4

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)

for attempt in range(1, ATTEMPTS + 1):
    start = time.time()
    sock.sendto(("DISCOVER|%s" % SERVICE).encode(), REGISTRY)
    try:
        data, _ = sock.recvfrom(1024)
    except socket.timeout:
        print("Attempt %d: registry did not respond" % attempt)
        continue

    latency = (time.time() - start) * 1000
    reply = data.decode(errors="replace").strip()
    print("Registry response:", reply)
    print("Discovery latency: %.2f ms" % latency)

    parts = reply.split("|")
    if parts[0] != "SERVICE" or len(parts) != 4:
        print("Service was not found.")
        break

    server = (parts[2], int(parts[3]))
    sock.sendto(("REQUEST|%s" % SERVICE).encode(), server)
    try:
        data, _ = sock.recvfrom(1024)
        print("Service response:", data.decode(errors="replace").strip())
        break
    except socket.timeout:
        print("Attempt %d: server %s:%s not responding, rediscovering..."
              % (attempt, server[0], server[1]))
        time.sleep(2)
else:
    print("Service unavailable after all attempts.")
