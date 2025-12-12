import dnstunnel

server_ip = "127.0.0.1"
server_port = 7777
domain = "example.com"

client = dnstunnel.DNSTunnelClient(server_ip, server_port, domain)

client.send("Hello server!".encode())
print("Sent message to server successfully.")

res = client.send_and_receive("PING".encode())
if res.decode() == "PONG":
    print("Sent ping to server and received pong successfully.")
else:
    print("Failed to receive pong from server.")