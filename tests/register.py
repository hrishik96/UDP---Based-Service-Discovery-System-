import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3)
s.sendto(b"REGISTER|video|10.0.0.2|5001", ("10.0.0.1", 5000))
print("Registry replied:", s.recvfrom(1024)[0].decode())

