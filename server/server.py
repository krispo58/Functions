import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

import dnstunnel
import llmapi

class Server:
    def __init__(self, port: int, debug: bool = False, domain: str = "ordbokene.no"):
        self.debug = debug
        self.tunnel = dnstunnel.DNSTunnelServer("0.0.0.0", port, domain)
        self.llm = llmapi.LLM()
        self.commands = {
            "PROMPT": self._prompt,
            "ACK": self._ack
        }

        if debug:
            print(f"Server initialized on 0.0.0.0:{port}")

    def _parse_data(self, data: str) -> tuple:
        splitted = data.split("|||")
        #id = splitted[0]
        command = splitted[0]
        if len(splitted) < 2:
            return (command, [])
        return (command, splitted[1:])
        #return (id, command, splitted[2:])

    def _handle_request(self, session_id: int, data: bytes, addr: str) -> str:
        if self.debug:
            print(f"Received data from {addr}: {data}")
        #id, command, args = self._parse_data(data)
        data = data.decode()
        command, args = self._parse_data(data)
        print(f"Handling command: {command} with args: {args}")
        response = self.commands[command](args).encode()
        self.tunnel.queue_response(session_id, response)


    def _prompt(self, args: list) -> str:
        print("Processing PROMPT command... arguments:", args)
        prompt_content = args[0]
        response = self.llm.prompt(prompt_content)
        print("LLM response:", response)
        return response
    
    def _ack(self, args: list) -> str:
        return "ACK"

    def start(self):
        print("Starting DNS Tunnel Server...")
        self.tunnel.on_data_received = self._handle_request
        print("DNS Tunnel Server started.")
        self.tunnel.start()
