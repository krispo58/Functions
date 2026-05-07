import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebase_transport
import llmapi
import time


class Server:
    def __init__(self, project_id: str = None, debug: bool = False):
        """
        Initialize the server.
        
        Args:
            project_id: Firebase project ID (defaults to FIREBASE_PROJECT_ID env var)
            debug: Enable debug logging
        """
        self.debug = debug
        
        if project_id is None:
            project_id = os.environ.get("FIREBASE_PROJECT_ID")
            if not project_id:
                raise ValueError("project_id must be provided or FIREBASE_PROJECT_ID env var set")
        
        self.tunnel = firebase_transport.FirebaseTransport(project_id)
        self.tunnel.debug = debug
        self.llm = llmapi.LLM()
        self.commands = {
            "PROMPT": self._prompt,
            "ACK": self._ack,
            "NEW": self._new,
            "SWITCH": self._switch,
            "JUDGE": self._judge_handler
        }
        if debug:
            print(f"Server initialized with Firebase project: {project_id}")
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
        data = msg['data']
        
        if self.debug:
            print(f"Received data from {sender[:8]}: {data}")
        
        # Parse command and args
        command, args = self._parse_data(data)
        if self.debug:
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
        try:
            self.tunnel.send('client-channel', response, msg_type='response')
            if self.debug:
                print(f"Sent response: {response}")
        except Exception as e:
            if self.debug:
                print(f"Error sending response: {e}")
    
    def _prompt(self, args: list) -> str:
        """Process PROMPT command."""
        if self.debug:
            print("Processing PROMPT command... arguments:", args)
        prompt_content = args[0]
        response = self.llm.prompt(prompt_content)
        if self.debug:
            print("LLM response:", response[:100] + "..." if len(response) > 100 else response)
        return response
    
    def _ack(self, args: list) -> str:
        """Process ACK command."""
        self._new([])  # Reset chat history on ACK to ensure clean state
        self.llm.use_fallback = True  # Reset to Groq on reconnect
        return "ACK"
    
    def _new(self, args: list) -> str:
        """Process NEW command."""
        self.llm.reset_chat_history()
        self.llm.use_fallback = True  # Reset to Groq
        return "success"
    
    def _switch(self, args: list) -> str:
        """Process SWITCH command to toggle between OpenAI and Groq."""
        return self.llm.toggle_llm()
    
    def _judge_handler(self, args: list) -> str:
        """Process JUDGE command."""
        if self.debug:
            print("Processing JUDGE command... arguments:", args)
        prompt_content = args[0]
        response = self.llm.judge(prompt_content)
        if self.debug:
            print("Judge response:", response[:100] + "..." if len(response) > 100 else response)
        return response
    
    def start(self):
        """Start the server and listen for incoming requests."""
        print("Starting Firebase Tunnel Server...")
        self.tunnel.on_message(self._handle_request)
        self.tunnel.start_listening('server-channel', poll_interval=0.5)
        self.tunnel.start_heartbeat()
        self.tunnel.start_cleanup()
        print("Firebase Tunnel Server started.")
        print("Listening on 'server-channel'")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            self.tunnel.stop_listening()
            self.tunnel.stop_heartbeat()
            self.tunnel.stop_cleanup()
            print("[SERVER] Shutdown complete")