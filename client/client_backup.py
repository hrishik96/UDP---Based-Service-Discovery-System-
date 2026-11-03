import socket

REGISTRY = ("127.0.0.1", 5000)

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(3)

service = input("Enter service name to discover: ")

# Ask the registry to discover the service
message = f"DISCOVER|{service}"
client.sendto(message.encode(), REGISTRY)

try:
    data, addr = client.recvfrom(1024)
    response = data.decode().strip()

    print("Registry response:", response)

    parts = response.split("|")

    if parts[0] == "SERVICE" and len(parts) == 4:
        server_ip = parts[2]
        server_port = int(parts[3])

        # Send a request to the discovered service
        request = f"REQUEST|{service}"
        client.sendto(request.encode(), (server_ip, server_port))

        data, addr = client.recvfrom(1024)
        print("Service response:", data.decode())

    else:
        print("Service was not found.")

except socket.timeout:
    print("No response received. Check that the registry and server are running.")

client.close()

