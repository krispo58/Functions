import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebase_transport
import time
import threading
from typing import Optional


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
        # The client only expects traffic right after its own send(): poll fast while a
        # request is pending (up to the 360 s answer timeout), otherwise barely at all.
        self.tunnel.start_listening('client-channel', poll_interval=0.5, idle_interval=60.0,
                                    ladder=[(10.0, 0.5), (400.0, 2.0)], bump_on_receive=False)
        self.tunnel.start_heartbeat()
        self.tunnel.start_cleanup()
        
        # Which server the requests go to: 'server-channel' (main) or 'backup-channel'
        self.channel = 'server-channel'

        # Response handling
        self.pending_response = None
        self.response_event = threading.Event()
        
        # Give listener time to initialize
        time.sleep(0.5)
    
    def _handle_response(self, msg: dict):
        """Handle incoming response from server."""
        self.pending_response = msg.get('data')
        self.response_event.set()
    
    def _send_and_wait(self, command: str, args: list = None, timeout: float = 360) -> Optional[dict]:
        """
        Send command and wait for response.

        Returns the response dict on success, or None if sending failed or
        no response arrived within the timeout.
        """
        # Clear previous response
        self.pending_response = None
        self.response_event.clear()

        # Build and send request
        request = {
            "command": command,
            "args": args or []
        }
        try:
            self.tunnel.send(self.channel, request)
        except Exception as e:
            print(f"Error sending '{command}': {e}")
            return None

        # Wait for response
        if self.response_event.wait(timeout=timeout):
            return self.pending_response
        else:
            print(f"Timed out waiting for response to '{command}'")
            return None

    def ack(self) -> bool:
        """Test connection with ACK command."""
        response = self._send_and_wait("ACK", timeout=30)
        if not isinstance(response, dict):
            return False
        return response.get("status") == "success" and response.get("data") == "ACK"

    def new_chat(self) -> bool:
        """Start a new chat session."""
        response = self._send_and_wait("NEW")
        if not isinstance(response, dict):
            return False
        return response.get("status") == "success" and response.get("data") == "success"
    
    def send_prompt(self, prompt: str) -> str:
        """Send a prompt to the LLM and get response."""
        response = self._send_and_wait("PROMPT", [prompt], timeout=360)
        if not isinstance(response, dict):
            return "timeout"

        if response.get("status") == "success":
            return response.get("data")
        else:
            error = response.get("error", "Unknown error")
            print(f"Error: {error}")
            return "error"

    def switch(self) -> Optional[str]:
        """Switch between OpenRouter and OpenAI."""
        response = self._send_and_wait("SWITCH", timeout=30)
        if not isinstance(response, dict):
            return None

        if response.get("status") == "success":
            return response.get("data")
        else:
            error = response.get("error", "Unknown error")
            print(f"Error: {error}")
            return None

    def switch_server(self) -> Optional[str]:
        """
        Toggle between the main server and the backup server.

        Purely client side: it just changes which channel requests are sent to. The
        new server is pinged first (ACK, which also starts a fresh chat there), so if
        it isn't running nothing changes. Returns the server now in use, or None.
        """
        old_channel = self.channel
        new_channel = 'backup-channel' if old_channel == 'server-channel' else 'server-channel'

        self.channel = new_channel
        if not self.ack():
            self.channel = old_channel
            return None
        return "Backup server" if new_channel == 'backup-channel' else "Main server"

    def fallback(self) -> Optional[str]:
        """Trigger fallback by switching LLM."""
        return self.switch()

    def judge(self, prompt: str) -> str:
        """Send a prompt to the judge and get evaluation."""
        response = self._send_and_wait("JUDGE", [prompt], timeout=360)
        if not isinstance(response, dict):
            return "timeout"

        if response.get("status") == "success":
            return response.get("data")
        else:
            error = response.get("error", "Unknown error")
            print(f"Error: {error}")
            return f"Error: {error}"
    
    def close(self):
        """Clean up and stop listening."""
        self.tunnel.stop_listening()
        self.tunnel.stop_heartbeat()
        self.tunnel.stop_cleanup()