import dnstunnel

def handle_data(session_id, data, addr):
    print(f"Received from {addr}: {data.decode()}")
    if data.decode() == "PING":
        response = "PONG".encode()
        server.queue_response(session_id, response)
        print("Got ping. Sent pong.")

server_ip = "0.0.0.0"
server_port = 7777
domain = "example.com"

server = dnstunnel.DNSTunnelServer(server_ip, server_port, domain)

server.on_data_received = handle_data
server.start()