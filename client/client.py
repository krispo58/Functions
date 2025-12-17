import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebasetunnel
import time
import threading

class Client:
    def __init__(self, database_url: str, auth_token: str = None):
        self.tunnel = firebasetunnel.FirebaseTransport(database_url, auth_token)
        self.tunnel.on_message(self._handle_response)
        
        # Start listening for responses
        self.tunnel.start_listening('client-channel', poll_interval=0.5)
        self.tunnel.start_heartbeat()
        
        # Response handling
        self.pending_response = None
        self.response_event = threading.Event()
        
        # Give listener time to initialize
        time.sleep(0.5)
    
    def _handle_response(self, msg: dict):
        """Handle incoming response from server."""
        data = msg['data']
        self.pending_response = data
        self.response_event.set()
    
    def _send_and_wait(self, command: str, args: list = None, timeout: float = 30) -> dict:
        """Send command and wait for response."""
        # Clear previous response
        self.pending_response = None
        self.response_event.clear()
        
        # Build and send request
        request = {
            "command": command,
            "args": args or []
        }
        self.tunnel.send('server-channel', request)
        
        # Wait for response
        if self.response_event.wait(timeout=timeout):
            return self.pending_response
        else:
            return None
    
    def ack(self) -> bool:
        """Test connection with ACK command."""
        response = self._send_and_wait("ACK", timeout=10)
        if response is None:
            return False
        return response.get("status") == "success" and response.get("data") == "ACK"
    
    def new_chat(self) -> bool:
        """Start a new chat session."""
        response = self._send_and_wait("NEW", timeout=10)
        if response is None:
            return False
        return response.get("status") == "success" and response.get("data") == "success"
    
    def send_prompt(self, prompt: str) -> str:
        """Send a prompt to the LLM and get response."""
        response = self._send_and_wait("PROMPT", [prompt], timeout=30)
        if response is None:
            return None
        
        if response.get("status") == "success":
            return response.get("data")
        else:
            error = response.get("error", "Unknown error")
            print(f"Error: {error}")
            return None
    
    def close(self):
        """Clean up and stop listening."""
        self.tunnel.stop_listening()