import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebase_transport
import llmapi
import time


class Server:
    MAIN_CHANNEL = 'server-channel'
    BACKUP_CHANNEL = 'backup-channel'

    def __init__(self, project_id: str = None, debug: bool = False, backup: bool = False):
        """
        Initialize the server.

        Args:
            project_id: Firebase project ID (defaults to FIREBASE_PROJECT_ID env var)
            debug: Enable debug logging
            backup: Run as a backup server: identical to the main server, but it
                listens on its own channel. Clients choose which one to talk to.
        """
        self.debug = debug
        self.backup = backup
        self.channel = self.BACKUP_CHANNEL if backup else self.MAIN_CHANNEL
        
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
        sender = msg.get('sender', 'unknown')
        data = msg.get('data') or {}

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
        if not args or not args[0]:
            raise ValueError("PROMPT command requires a non-empty prompt argument")
        prompt_content = args[0]
        response = self.llm.prompt(prompt_content)
        if self.debug:
            print("LLM response:", response[:100] + "..." if len(response) > 100 else response)
        return response
    
    def _ack(self, args: list) -> str:
        """Process ACK command."""
        self._new([])  # Reset chat history on ACK to ensure clean state
        return "ACK"
    
    def _new(self, args: list) -> str:
        """Process NEW command."""
        self.llm.reset_chat_history()
        self.llm.reset_judge_history()
        self.llm.use_openai = False  # Reset to OpenRouter (the default)
        return "success"
    
    def _switch(self, args: list) -> str:
        """Process SWITCH command to toggle between OpenRouter and OpenAI."""
        return self.llm.toggle_llm()
    
    def _judge_handler(self, args: list) -> str:
        """Process JUDGE command."""
        if self.debug:
            print("Processing JUDGE command... arguments:", args)
        if not args or not args[0]:
            raise ValueError("JUDGE command requires a non-empty prompt argument")
        prompt_content = args[0]
        response = self.llm.judge(prompt_content)
        if self.debug:
            print("Judge response:", response[:100] + "..." if len(response) > 100 else response)
        return response
    
    def start(self):
        """Start the server and listen for incoming requests."""
        print("Starting Firebase Tunnel Server...")
        self.tunnel.on_message(self._handle_request)
        self.tunnel.start_listening(self.channel, poll_interval=0.5)
        self.tunnel.start_heartbeat()
        self.tunnel.start_cleanup()
        print("Firebase Tunnel Server started.")
        print(f"Listening on '{self.channel}'" + (" (backup server)" if self.backup else ""))
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(1)
                # Safety net: the main thread must never sit idle while the
                # listener is dead, otherwise the process looks alive but is deaf.
                if not self.tunnel.is_listening():
                    print("[SERVER] Listener thread is not running; restarting it")
                    self.tunnel._listener_running = False
                    self.tunnel.start_listening(self.channel, poll_interval=0.5)
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            self.tunnel.stop_listening()
            self.tunnel.stop_heartbeat()
            self.tunnel.stop_cleanup()
            print("[SERVER] Shutdown complete")