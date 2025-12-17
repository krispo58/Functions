import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebasetunnel
import llmapi
import time

class Server:
    def __init__(self, database_url: str, auth_token: str = None, debug: bool = False):
        self.debug = debug
        self.tunnel = firebasetunnel.FirebaseTransport(database_url, auth_token)
        self.llm = llmapi.LLM()
        self.commands = {
            "PROMPT": self._prompt,
            "ACK": self._ack,
            "NEW": self._new
        }
        if debug:
            print(f"Server initialized with Firebase: {database_url}")
            print(f"Server ID: {self.tunnel.client_id}")
    
    def _parse_data(self, data: dict) -> tuple:
        """Parse the incoming message data."""
        # Firebase sends structured data, not raw strings
        command = data.get("command", "")
        args = data.get("args", [])
        return (command, args)
    
    def _handle_request(self, msg: dict):
        """Handle incoming request message."""
        sender = msg['sender']
        sender_session = msg.get('sender_session')
        data = msg['data']
        
        if self.debug:
            print(f"Received data from {sender[:8]}: {data}")
        
        # Parse command and args
        command, args = self._parse_data(data)
        print(f"Handling command: {command} with args: {args}")
        
        # Execute command
        try:
            response_data = self.commands[command](args)
            response = {
                "status": "success",
                "data": response_data,
                "command": command
            }
        except KeyError:
            response = {
                "status": "error",
                "error": f"Unknown command: {command}",
                "command": command
            }
        except Exception as e:
            response = {
                "status": "error",
                "error": str(e),
                "command": command
            }
        
        # Send response back to client
        # Only if client session is still active
        if self.tunnel._is_session_active(sender_session):
            self.tunnel.send('client-channel', response)
            if self.debug:
                print(f"Sent response: {response}")
        else:
            print(f"Ignored request from expired session: {sender[:8]}")
    
    def _prompt(self, args: list) -> str:
        print("Processing PROMPT command... arguments:", args)
        prompt_content = args[0]
        response = self.llm.prompt(prompt_content)
        print("LLM response:", response[:100] + "..." if len(response) > 100 else response)
        return response
    
    def _ack(self, args: list) -> str:
        return "ACK"
    
    def _new(self, args: list) -> str:
        self.llm.reset_chat_history()
        return "success"
    
    def start(self):
        print("Starting Firebase Tunnel Server...")
        self.tunnel.on_message(self._handle_request)
        self.tunnel.start_listening('server-channel', poll_interval=0.5)
        self.tunnel.start_heartbeat()  # Keep server session alive
        print("Firebase Tunnel Server started.")
        print("Listening on 'server-channel'")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            self.tunnel.stop_listening()