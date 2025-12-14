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
    
    def _build_request(self, command: str, args: list[str] = None):
        return (f"{command}" if args is None else f"{command}|||" + "|||".join(args)).encode()

    def ack(self):
        response = self.tunnel.send_and_receive("ACK".encode(), timeout=5)
        return response.decode() == "ACK"

    def new_chat(self):
        data = self._build_request("NEW")
        response = self.tunnel.send_and_receive(data, timeout=5)
        if response is None:
            return False
        return response == b"success"


    def send_prompt(self, prompt: str) -> str:
        data = self._build_request("PROMPT", [prompt])
        response = self.tunnel.send_and_receive(data, timeout=30)
        return response.decode()
    