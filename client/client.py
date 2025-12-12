import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

import dnstunnel

class Client:
    def __init__(self, server_ip: str, server_port: int, domain: str):
        self.tunnel = dnstunnel.DNSTunnelClient(server_ip, server_port, domain)

    def _parse_response(self, data: str) -> str:
        splitted = data.split("|||")
        data = splitted[splitted.index("DATA") + 1]
        return data

    def ack(self):
        response = self.tunnel.send_and_receive("ACK".encode(), timeout=5)
        return response.decode() == "ACK"

    def send_prompt(self, prompt: str) -> str:
        data = f"PROMPT|||{prompt}"
        response = self.tunnel.send_and_receive(data.encode(), timeout=5)
        return response.decode()
    