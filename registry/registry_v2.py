import socket
import time

HOST = "0.0.0.0"
PORT = 5000
TIMEOUT = 9
EVENT_FILE = "/tmp/registry_events.log"

# services[name] = { (ip, port): last_seen_time }
services = {}

open(EVENT_FILE, "w").close()


def emit(event):
    print("EVENT", event, flush=True)
    try:
        with open(EVENT_FILE, "a") as f:
            f.write(event + "\n")
    except OSError:
        pass


def expire_old():
    now = time.time()
    for name in list(services):
        for key in list(services[name]):
            if now - services[name][key] > TIMEOUT:
                del services[name][key]
                emit("EXPIRED|%s|%s|%s" % (name, key[0], key[1]))
        if not services[name]:
            del services[name]


def touch(name, ip, port):
    key = (ip, port)
    is_new = name not in services or key not in services[name]
    services.setdefault(name, {})[key] = time.time()
    if is_new:
        emit("REGISTERED|%s|%s|%s" % (name, ip, port))


def pick(name):
    if name in services and services[name]:
        return next(iter(services[name]))
    return None


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
sock.settimeout(1)
print("Registry v2 listening on UDP port %s (timeout %ss)" % (PORT, TIMEOUT), flush=True)

while True:
    try:
        data, addr = sock.recvfrom(1024)
    except socket.timeout:
        expire_old()
        continue

    expire_old()
    parts = data.decode(errors="replace").strip().split("|")

    try:
        if parts[0] == "ADVERTISE" and len(parts) == 3:
            touch(parts[1], addr[0], int(parts[2]))

        elif parts[0] == "REGISTER" and len(parts) == 4:
            touch(parts[1], parts[2], int(parts[3]))
            sock.sendto(b"REGISTERED", addr)

        elif parts[0] == "DISCOVER" and len(parts) == 2:
            found = pick(parts[1])
            if found:
                reply = "SERVICE|%s|%s|%s" % (parts[1], found[0], found[1])
            else:
                reply = "NOT_FOUND|%s" % parts[1]
            sock.sendto(reply.encode(), addr)

        else:
            sock.sendto(b"INVALID_REQUEST", addr)
    except ValueError:
        sock.sendto(b"INVALID_REQUEST", addr)
