import socket

HOST = "0.0.0.0"
PORT = 5000

services = {}

registry = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
registry.bind((HOST, PORT))

print(f"Service registry listening on port {PORT}...")

while True:
    data, addr = registry.recvfrom(1024)
    message = data.decode().strip()
    parts = message.split("|")

    if parts[0] == "REGISTER" and len(parts) == 4:
        service, ip, port = parts[1], parts[2], int(parts[3])

        services[service] = (ip, port)
        print(f"Registered {service} at {ip}:{port}")

        registry.sendto(b"REGISTERED", addr)

    elif parts[0] == "DISCOVER" and len(parts) == 2:
        service = parts[1]

        if service in services:
            ip, port = services[service]
            response = f"SERVICE|{service}|{ip}|{port}"
        else:
            response = f"NOT_FOUND|{service}"

        registry.sendto(response.encode(), addr)

    else:
        registry.sendto(b"INVALID_REQUEST", addr)

