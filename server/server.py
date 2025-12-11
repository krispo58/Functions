import dnstunnel

def handle_data(session_id, data, addr):
    print("Received data:", data)
    server.queue_response(session_id, b"Response from server")

server = dnstunnel.DNSTunnelServer("0.0.0.0", 7777, "example.com")
server.on_data_received = handle_data
server.start()