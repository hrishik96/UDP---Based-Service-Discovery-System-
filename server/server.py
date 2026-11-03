import socket

HOST = "0.0.0.0"
PORT = 5001

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))

print(f"Video service server listening on port {PORT}...")

while True:
    data, addr = server.recvfrom(1024)
    message = data.decode().strip()

    print(f"Received from {addr}: {message}")

    if message == "REQUEST|video":
        response = "SUCCESS|video|Video service is available"
    else:
        response = "ERROR|Unknown request"

    server.sendto(response.encode(), addr)
