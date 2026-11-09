import socket
import sys

ip = sys.argv[1]
port = int(sys.argv[2])
count = int(sys.argv[3])

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.05)
replies = 0
for _ in range(count):
    sock.sendto(b"REQUEST|video", (ip, port))
    try:
        sock.recvfrom(1024)
        replies += 1
    except socket.timeout:
        pass
print("sent=%d replies=%d" % (count, replies))
