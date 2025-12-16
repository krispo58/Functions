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
            return response.status_code == 200
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