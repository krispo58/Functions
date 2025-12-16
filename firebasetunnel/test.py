import requests
import json
import time
import threading
import uuid
from typing import Callable, Optional, Dict, Any
from datetime import datetime

class FirebaseTransport:
    """
    A transport layer that uses Firebase Realtime Database as a tunnel.
    Supports bidirectional communication through firebase.googleapis.com
    """
    
    def __init__(self, database_url: str, auth_token: Optional[str] = None):
        """
        Initialize the Firebase transport layer.
        
        Args:
            database_url: Firebase Realtime Database URL (e.g., https://your-project.firebaseio.com)
            auth_token: Optional Firebase auth token or database secret
        """
        self.database_url = database_url.rstrip('/')
        self.auth_token = auth_token
        self.client_id = str(uuid.uuid4())
        self.running = False
        self.listener_thread = None
        self.message_handlers = []
        self.last_message_id = None
        
    def _get_url(self, path: str) -> str:
        """Construct Firebase REST API URL with auth if available."""
        url = f"{self.database_url}/{path}.json"
        if self.auth_token:
            url += f"?auth={self.auth_token}"
        return url
    
    def send(self, channel: str, data: Any, metadata: Optional[Dict] = None) -> bool:
        """
        Send data through the Firebase tunnel.
        
        Args:
            channel: Channel name to send on
            data: Data to send (will be JSON serialized)
            metadata: Optional metadata to include
            
        Returns:
            bool: True if successful, False otherwise
        """
        message = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'sender': self.client_id,
            'data': data,
            'metadata': metadata or {}
        }
        
        try:
            url = self._get_url(f"channels/{channel}/messages")
            response = requests.post(url, json=message, timeout=10)
            
            if response.status_code != 200:
                print(f"Send failed: HTTP {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False
            
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False
    
    def receive(self, channel: str, timeout: Optional[float] = None) -> Optional[Dict]:
        """
        Receive a single message from a channel (blocking).
        
        Args:
            channel: Channel name to receive from
            timeout: Optional timeout in seconds
            
        Returns:
            Dict: Message data or None if timeout/error
        """
        start_time = time.time()
        
        while True:
            try:
                url = self._get_url(f"channels/{channel}/messages")
                url += "&orderBy=\"$key\"&limitToLast=1"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    messages = response.json()
                    if messages:
                        msg_id, msg_data = list(messages.items())[0]
                        if msg_id != self.last_message_id and msg_data['sender'] != self.client_id:
                            self.last_message_id = msg_id
                            return msg_data
                
                if timeout and (time.time() - start_time) > timeout:
                    return None
                    
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Receive error: {e}")
                if timeout and (time.time() - start_time) > timeout:
                    return None
                time.sleep(1)
    
    def on_message(self, handler: Callable[[Dict], None]):
        """
        Register a message handler callback.
        
        Args:
            handler: Function to call when message received
        """
        self.message_handlers.append(handler)
    
    def start_listening(self, channel: str, poll_interval: float = 1.0):
        """
        Start listening for messages on a channel in background thread.
        
        Args:
            channel: Channel name to listen on
            poll_interval: How often to poll for new messages (seconds)
        """
        if self.running:
            return
        
        self.running = True
        self.listener_thread = threading.Thread(
            target=self._listen_loop,
            args=(channel, poll_interval),
            daemon=True
        )
        self.listener_thread.start()
    
    def _listen_loop(self, channel: str, poll_interval: float):
        """Internal listening loop."""
        last_check = None
        
        while self.running:
            try:
                url = self._get_url(f"channels/{channel}/messages")
                if last_check:
                    url += f'&orderBy="timestamp"&startAt="{last_check}"'
                else:
                    url += '&orderBy="timestamp"&limitToLast=10'
                
                response = requests.get(url, timeout=5)
                
                if response.status_code != 200:
                    print(f"Listen error: HTTP {response.status_code}")
                    print(f"URL: {url.split('?')[0]}")  # Don't log auth token
                    time.sleep(poll_interval)
                    continue
                
                if response.status_code == 200:
                    messages = response.json()
                    if messages:
                        for msg_id, msg_data in sorted(messages.items(), 
                                                       key=lambda x: x[1].get('timestamp', '')):
                            if msg_data['sender'] != self.client_id:
                                for handler in self.message_handlers:
                                    try:
                                        handler(msg_data)
                                    except Exception as e:
                                        print(f"Handler error: {e}")
                        
                        last_check = list(messages.values())[-1]['timestamp']
                
                time.sleep(poll_interval)
                
            except Exception as e:
                print(f"Listen error: {e}")
                time.sleep(poll_interval)
    
    def stop_listening(self):
        """Stop the background listener thread."""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5)
    
    def clear_channel(self, channel: str) -> bool:
        """
        Clear all messages from a channel.
        
        Args:
            channel: Channel name to clear
            
        Returns:
            bool: True if successful
        """
        try:
            url = self._get_url(f"channels/{channel}")
            response = requests.delete(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Clear error: {e}")
            return False


# ============================================================================
# SERVER EXAMPLE - Run this first
# ============================================================================
class EchoServer:
    """Simple echo server that responds to client requests."""
    
    def __init__(self, database_url: str, auth_token: Optional[str] = None):
        self.transport = FirebaseTransport(database_url, auth_token)
        self.transport.on_message(self.handle_request)
        print(f"[SERVER] Initialized with ID: {self.transport.client_id[:8]}")
    
    def handle_request(self, msg: Dict):
        """Handle incoming requests from clients."""
        data = msg['data']
        sender = msg['sender'][:8]
        
        print(f"[SERVER] Received from {sender}: {data}")
        
        # Process different request types
        if data.get('type') == 'ping':
            response = {
                'type': 'pong',
                'original': data.get('message', ''),
                'server_time': datetime.utcnow().isoformat()
            }
        elif data.get('type') == 'echo':
            response = {
                'type': 'echo_response',
                'echoed': data.get('message', ''),
                'length': len(data.get('message', ''))
            }
        elif data.get('type') == 'compute':
            a = data.get('a', 0)
            b = data.get('b', 0)
            response = {
                'type': 'compute_response',
                'result': a + b,
                'operation': 'add'
            }
        else:
            response = {
                'type': 'error',
                'message': 'Unknown request type'
            }
        
        # Send response back
        self.transport.send('client-channel', response)
        print(f"[SERVER] Sent response: {response}")
    
    def start(self):
        """Start the server listening loop."""
        print("[SERVER] Starting server...")
        self.transport.start_listening('server-channel', poll_interval=0.5)
        print("[SERVER] Listening on 'server-channel'")
        print("[SERVER] Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            self.transport.stop_listening()


# ============================================================================
# CLIENT EXAMPLE - Run this in a separate terminal/process
# ============================================================================
class TestClient:
    """Test client that sends requests to the server."""
    
    def __init__(self, database_url: str, auth_token: Optional[str] = None):
        self.transport = FirebaseTransport(database_url, auth_token)
        self.transport.on_message(self.handle_response)
        self.responses_received = []
        print(f"[CLIENT] Initialized with ID: {self.transport.client_id[:8]}")
    
    def handle_response(self, msg: Dict):
        """Handle responses from server."""
        data = msg['data']
        sender = msg['sender'][:8]
        print(f"[CLIENT] Response from {sender}: {data}")
        self.responses_received.append(data)
    
    def send_request(self, request_data: Dict):
        """Send a request to the server."""
        print(f"[CLIENT] Sending: {request_data}")
        self.transport.send('server-channel', request_data)
    
    def run_tests(self):
        """Run a series of test requests."""
        print("[CLIENT] Starting listener...")
        self.transport.start_listening('client-channel', poll_interval=0.5)
        print("[CLIENT] Listening on 'client-channel'")
        
        time.sleep(1)  # Wait for listener to initialize
        
        # Test 1: Ping
        print("\n[CLIENT] Test 1: Ping")
        self.send_request({'type': 'ping', 'message': 'Hello server!'})
        time.sleep(2)
        
        # Test 2: Echo
        print("\n[CLIENT] Test 2: Echo")
        self.send_request({'type': 'echo', 'message': 'This should be echoed back'})
        time.sleep(2)
        
        # Test 3: Compute
        print("\n[CLIENT] Test 3: Compute")
        self.send_request({'type': 'compute', 'a': 15, 'b': 27})
        time.sleep(2)
        
        # Test 4: Invalid request
        print("\n[CLIENT] Test 4: Invalid request")
        self.send_request({'type': 'unknown', 'data': 'test'})
        time.sleep(2)
        
        print(f"\n[CLIENT] Tests complete! Received {len(self.responses_received)} responses")
        self.transport.stop_listening()


# ============================================================================
# MAIN - Choose which to run
# ============================================================================
if __name__ == "__main__":
    import sys
    
    # Configuration - UPDATE THESE VALUES
    DATABASE_URL = "https://my-awesome-project-3c43d-default-rtdb.europe-west1.firebasedatabase.app/"
    AUTH_TOKEN = None  # Or your auth token/secret
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python firebase_transport.py server   # Run as server")
        print("  python firebase_transport.py client   # Run as client")
        print("  python firebase_transport.py test     # Test connection")
        print("  python firebase_transport.py clear    # Clear channels")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == "server":
        server = EchoServer(DATABASE_URL, AUTH_TOKEN)
        server.start()
    
    elif mode == "client":
        client = TestClient(DATABASE_URL, AUTH_TOKEN)
        client.run_tests()
    
    elif mode == "test":
        # Quick connection test
        print("Testing Firebase connection...")
        transport = FirebaseTransport(DATABASE_URL, AUTH_TOKEN)
        
        # Try to write
        print("1. Testing write...")
        success = transport.send("test", {"hello": "world"})
        print(f"   Write: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        # Try to read
        print("2. Testing read...")
        try:
            url = transport._get_url("test")
            response = requests.get(url, timeout=5)
            print(f"   Read: {'✓ SUCCESS' if response.status_code == 200 else '✗ FAILED'}")
            if response.status_code == 200:
                print(f"   Data: {response.json()}")
            else:
                print(f"   Error: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            print(f"   Read: ✗ FAILED - {e}")
        
        print("\nIf tests failed, check:")
        print("1. Database URL is correct (should end with .firebaseio.com)")
        print("2. Database rules allow read/write")
        print("3. If using auth, token is valid")
    
    elif mode == "clear":
        print("Clearing channels...")
        transport = FirebaseTransport(DATABASE_URL, AUTH_TOKEN)
        transport.clear_channel("server-channel")
        transport.clear_channel("client-channel")
        print("Channels cleared!")
    
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)