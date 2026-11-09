import socket
import sys
import time

REGISTRY_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
NAME = sys.argv[2] if len(sys.argv) > 2 else "video"
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 5001
ADVERTISE_EVERY = 3

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.settimeout(1)

print("Server v2: service '%s' on UDP %d, advertising to %s every %ds"
      % (NAME, PORT, REGISTRY_IP, ADVERTISE_EVERY), flush=True)

last_advert = 0
while True:
    now = time.time()
    if now - last_advert >= ADVERTISE_EVERY:
        advert = "ADVERTISE|%s|%d" % (NAME, PORT)
        sock.sendto(advert.encode(), (REGISTRY_IP, 5000))
        last_advert = now

    try:
        data, addr = sock.recvfrom(1024)
    except socket.timeout:
        continue

    message = data.decode(errors="replace").strip()
    print("Received from %s: %s" % (addr, message), flush=True)

    if message == "REQUEST|%s" % NAME:
        reply = "SUCCESS|%s|served by port %d" % (NAME, PORT)
    else:
        reply = "ERROR|Unknown request"
    sock.sendto(reply.encode(), addr)
