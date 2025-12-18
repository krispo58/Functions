import sys
import os
import uuid
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import firebase_transport
import llmapi

class Server:
    SESSION_TIMEOUT = 60  # seconds, session expires if no heartbeat

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.tunnel = firebase_transport.FirebaseTransport(
            os.environ.get("FIREBASE_PROJECT_ID")
        )
        self.tunnel.debug = debug
        self.llm = llmapi.LLM()
        self.commands = {
            "PROMPT": self._prompt,
            "ACK": self._ack,
            "NEW": self._new,
            "HEARTBEAT": self._heartbeat
        }

        # session_id -> last_seen_timestamp
        self.active_sessions = {}

        if debug:
            print(f"[SERVER INIT] FirebaseTransport initialized")
            print(f"Server ID: {self.tunnel.client_id}")

    # ----------------------
    # Message parsing
    # ----------------------
    def _parse_data(self, data: dict) -> tuple:
        """Parse incoming message data."""
        command = data.get("command", "")
        args = data.get("args", [])
        return command, args

    # ----------------------
    # Session management
    # ----------------------
    def _update_session(self, sender_session: str):
        """Update or create session heartbeat."""
        self.active_sessions[sender_session] = time.time()
        if self.debug:
            print(f"[SESSION] Updated session {sender_session[:8]}")

    def _is_session_active(self, sender_session: str) -> bool:
        """Check if a session is still active."""
        last_seen = self.active_sessions.get(sender_session)
        if not last_seen:
            return False
        if time.time() - last_seen > self.SESSION_TIMEOUT:
            del self.active_sessions[sender_session]
            if self.debug:
                print(f"[SESSION] Expired session {sender_session[:8]}")
            return False
        return True

    # ----------------------
    # Request handling
    # ----------------------
    def _handle_request(self, msg: dict):
        """Handle incoming request message."""
        sender = msg.get('sender', 'unknown')
        msg_data = msg.get('data', {})
        
        sender_session = msg_data.get('sender_session', str(uuid.uuid4()))
        data = msg_data

        # heartbeat/session tracking
        self._update_session(sender_session)

        if self.debug:
            print(f"[RECV] From {sender[:8]} (session {sender_session[:8]}): {data}")

        command, args = self._parse_data(data)
        if self.debug:
            print(f"[HANDLE] Command: {command}, Args: {args}")

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

        # Only send to active sessions
        if self._is_session_active(sender_session):
            response['sender_session'] = sender_session
            self.tunnel.send('client-channel', response)
            if self.debug:
                print(f"[SEND] Response sent: {response}")
        else:
            if self.debug:
                print(f"[SEND] Skipped response for expired session {sender_session[:8]}")

    # ----------------------
    # Commands
    # ----------------------
    def _prompt(self, args: list) -> str:
        prompt_content = args[0]
        response = self.llm.prompt(prompt_content)
        if self.debug:
            print(f"[PROMPT] LLM response: {response[:100]}{'...' if len(response) > 100 else ''}")
        return response

    def _ack(self, args: list) -> str:
        return "ACK"

    def _new(self, args: list) -> str:
        self.llm.reset_chat_history()
        return "success"

    def _heartbeat(self, args: list) -> str:
        return "alive"

    # ----------------------
    # Start server
    # ----------------------
    def start(self):
        print("[SERVER] Starting Firebase Tunnel Server...")
        self.tunnel.on_message(self._handle_request)
        self.tunnel.start_listening('server-channel', poll_interval=0.5)
        print("[SERVER] Server started.")
        print("Listening on 'server-channel'. Press Ctrl+C to stop.")

        try:
            while True:
                # Cleanup expired sessions periodically
                now = time.time()
                for session, last_seen in list(self.active_sessions.items()):
                    if now - last_seen > self.SESSION_TIMEOUT:
                        del self.active_sessions[session]
                        if self.debug:
                            print(f"[SESSION] Expired session {session[:8]} cleaned up")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            # Clean up any pending messages from this server
            self.tunnel.delete_sender_messages('client-channel', self.tunnel.client_id)
            self.tunnel.stop_listening()
