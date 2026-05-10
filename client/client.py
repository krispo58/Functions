import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebase_transport
import time
import threading


class Client:
    def __init__(self, project_id: str = None):
        """
        Initialize the client.
        
        Args:
            project_id: Firebase project ID (defaults to FIREBASE_PROJECT_ID env var)
        """
        if project_id is None:
            project_id = os.environ.get("FIREBASE_PROJECT_ID")
            if not project_id:
                raise ValueError("project_id must be provided or FIREBASE_PROJECT_ID env var set")
        
        self.tunnel = firebase_transport.FirebaseTransport(project_id)
        self.tunnel.on_message(self._handle_response)
        
        # Start listening for responses
        self.tunnel.start_listening('client-channel', poll_interval=0.5)
        self.tunnel.start_heartbeat()
        self.tunnel.start_cleanup()
        
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
    
    def _send_and_wait(self, command: str, args: list = None, timeout: float = 360) -> dict:
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
            return "timeout"
    
    def ack(self) -> bool:
        """Test connection with ACK command."""
        response = self._send_and_wait("ACK", timeout=30)
        if response is None:
            return False
        return response.get("status") == "success" and response.get("data") == "ACK"
    
    def new_chat(self) -> bool:
        """Start a new chat session."""
        response = self._send_and_wait("NEW")
        if response is None:
            return False
        return response.get("status") == "success" and response.get("data") == "success"
    
    def send_prompt(self, prompt: str) -> str:
        """Send a prompt to the LLM and get response."""
        response = self._send_and_wait("PROMPT", [prompt], timeout=360)
        if response is None:
            return "timeout"

        if response.get("status") == "success":
            return response.get("data")
        else:
            error = response.get("error", "Unknown error")
            print(f"Error: {error}")
            return "error"
    
    def switch(self) -> str:
        """Switch between OpenAI and Groq."""
        response = self._send_and_wait("SWITCH", timeout=30)
        if response is None:
            return None
        
        if response.get("status") == "success":
            return response.get("data")
        else:
            error = response.get("error", "Unknown error")
            print(f"Error: {error}")
            return None
    
    def fallback(self) -> str:
        """Trigger fallback by switching LLM."""
        return self.switch()
    
    def judge(self, prompt: str) -> str:
        """Send a prompt to the judge and get evaluation."""
        response = self._send_and_wait("JUDGE", [prompt], timeout=360)
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
        self.tunnel.stop_heartbeat()
        self.tunnel.stop_cleanup()