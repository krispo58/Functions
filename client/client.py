import sys
import os
import time
import threading
import uuid
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebase_transport

class Client:
    HEARTBEAT_INTERVAL = 10  # seconds

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.client_id = str(uuid.uuid4())
        self.sender_session = str(uuid.uuid4())

        self.tunnel = firebase_transport.FirebaseTransport(
            os.environ.get("FIREBASE_PROJECT_ID")
        )
        self.tunnel.debug = debug
        self.tunnel.on_message(self._handle_response)

        # Response handling
        self.pending_response = None
        self.response_event = threading.Event()

        # Start listening
        self.tunnel.start_listening('client-channel', poll_interval=0.5)

        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        # Give listener time to initialize
        time.sleep(0.5)

    # ----------------------
    # Heartbeat
    # ----------------------
    def _heartbeat_loop(self):
        while True:
            try:
                self._send_command("HEARTBEAT", [])
            except Exception as e:
                if self.debug:
                    print(f"[HEARTBEAT] Error: {e}")
            time.sleep(self.HEARTBEAT_INTERVAL)

    # ----------------------
    # Message handling
    # ----------------------
    def _handle_response(self, msg: dict):
        """Handle incoming response from server."""
        # Extract data from message structure
        data = msg.get('data', {})
        
        # Only accept messages that are responses (have sender_session matching)
        if isinstance(data, dict) and data.get("sender_session") != self.sender_session:
            return

        self.pending_response = data
        self.response_event.set()

    def _send_command(self, command: str, args: list = None):
        """Send a command to the server."""
        request = {
            "command": command,
            "args": args or [],
            "sender_session": self.sender_session,
            "sender": self.client_id
        }
        return self.tunnel.send('server-channel', request)

    # ----------------------
    # Public API
    # ----------------------
    def _send_and_wait(self, command: str, args: list = None, timeout: float = 30):
        """Send command and wait for response."""
        self.pending_response = None
        self.response_event.clear()

        self._send_command(command, args)

        if self.response_event.wait(timeout=timeout):
            return self.pending_response
        else:
            if self.debug:
                print(f"[TIMEOUT] Command {command} timed out")
            return None

    def ack(self) -> bool:
        response = self._send_and_wait("ACK", timeout=10)
        return response is not None and response.get("status") == "success" and response.get("data") == "ACK"

    def new_chat(self) -> bool:
        response = self._send_and_wait("NEW", timeout=10)
        return response is not None and response.get("status") == "success" and response.get("data") == "success"

    def send_prompt(self, prompt: str) -> str:
        response = self._send_and_wait("PROMPT", [prompt], timeout=30)
        if response is None:
            return None

        if response.get("status") == "success":
            return response.get("data")
        else:
            error = response.get("error", "Unknown error")
            print(f"[ERROR] {error}")
            return None

    def close(self):
        """Clean up and stop listening."""
        # Clean up any pending messages from this client in server-channel
        self.tunnel.delete_sender_messages('server-channel', self.tunnel.client_id)
        self.tunnel.stop_listening()
