import requests
import json
import time
import threading
import uuid
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timezone


class FirebaseTransport:
    """
    A transport layer that uses Firebase Realtime Database REST API v1.
    Uses only firebase.googleapis.com domain for all operations.
    """

    def __init__(self, project_id: str):
        """
        Initialize the Firebase transport layer.

        Args:
            project_id: Your Firebase project ID
        """
        self.project_id = project_id
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        self.client_id = str(uuid.uuid4())
        self.running = False
        self.listener_thread = None
        self.message_handlers = []
        self.last_message_time = None
        self.received_message_ids = set()  # Track received message IDs to prevent duplicates

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {'Content-Type': 'application/json'}

    def _to_firestore_value(self, data: Any) -> Dict:
        """Convert Python data to Firestore value format."""
        if isinstance(data, str):
            return {'stringValue': data}
        elif isinstance(data, bool):
            return {'booleanValue': data}
        elif isinstance(data, int):
            return {'integerValue': str(data)}
        elif isinstance(data, float):
            return {'doubleValue': data}
        elif isinstance(data, dict):
            fields = {k: self._to_firestore_value(v) for k, v in data.items()}
            return {'mapValue': {'fields': fields}}
        elif isinstance(data, list):
            values = [self._to_firestore_value(item) for item in data]
            return {'arrayValue': {'values': values}}
        elif data is None:
            return {'nullValue': None}
        else:
            return {'stringValue': str(data)}

    def _from_firestore_value(self, value: Dict) -> Any:
        """Convert Firestore value format to Python data."""
        if 'stringValue' in value:
            return value['stringValue']
        elif 'booleanValue' in value:
            return value['booleanValue']
        elif 'integerValue' in value:
            return int(value['integerValue'])
        elif 'doubleValue' in value:
            return value['doubleValue']
        elif 'mapValue' in value:
            fields = value['mapValue'].get('fields', {})
            return {k: self._from_firestore_value(v) for k, v in fields.items()}
        elif 'arrayValue' in value:
            values = value['arrayValue'].get('values', [])
            return [self._from_firestore_value(item) for item in values]
        elif 'nullValue' in value:
            return None
        elif 'timestampValue' in value:
            return value['timestampValue']
        else:
            return None

    # ----------------------
    # Send and Receive Functions
    # ----------------------
    def send(self, channel: str, data: Dict) -> bool:
        """
        Send data to a Firestore collection (channel).
        
        Args:
            channel: The collection name to send data to (e.g., 'server-channel', 'client-channel')
            data: Dictionary containing the message data
            
        Returns:
            bool: True if send was successful, False otherwise
        """
        try:
            # Create a new document with auto-generated ID
            doc_id = str(uuid.uuid4())
            
            # Prepare the message with metadata
            message = {
                'sender': self.client_id,
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'channel': channel
            }
            
            # Convert to Firestore format
            fields = {}
            for key, value in message.items():
                fields[key] = self._to_firestore_value(value)
            
            # Build Firestore API request - use query parameter for documentId
            url = f"{self.base_url}/{channel}"
            payload = {'fields': fields}
            params = {'documentId': doc_id}
            
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                params=params,
                timeout=10
            )
            
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[SEND] To channel '{channel}': Status {response.status_code}")
            
            return response.status_code in [200, 201]
        except Exception as e:
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[SEND ERROR] Failed to send to '{channel}': {e}")
            return False

    def receive(self, channel: str, poll_interval: float = 1.0) -> Dict:
        """
        Receive a single message from a Firestore collection (channel).
        Blocks until a new message is available or timeout occurs.
        
        Args:
            channel: The collection name to receive from
            poll_interval: Time in seconds to wait between polls
            
        Returns:
            dict: The received message data, or None if no message received
        """
        try:
            last_check = self.last_message_time or 0
            
            # Query Firestore collection
            url = f"{self.base_url}?collectionId={channel}"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            documents = response.json().get('documents', [])
            
            # Find the latest message that hasn't been received yet
            latest_message = None
            latest_timestamp = last_check
            latest_doc_id = None
            
            for doc in documents:
                fields = doc.get('fields', {})
                timestamp_str = fields.get('timestamp', {}).get('stringValue', '')
                doc_id = doc.get('name', '').split('/')[-1]
                
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
                    if timestamp > latest_timestamp and doc_id not in self.received_message_ids:
                        latest_timestamp = timestamp
                        latest_message = doc
                        latest_doc_id = doc_id
                except:
                    pass
            
            if latest_message and latest_doc_id:
                self.last_message_time = latest_timestamp
                self.received_message_ids.add(latest_doc_id)
                fields = latest_message.get('fields', {})
                
                # Extract and convert message data
                message = {
                    'sender': self._from_firestore_value(fields.get('sender', {})),
                    'data': self._from_firestore_value(fields.get('data', {})),
                    'timestamp': self._from_firestore_value(fields.get('timestamp', {})),
                }
                
                # Delete the message from Firestore to prevent duplicate processing
                self.delete(channel, latest_doc_id)
                
                return message
            
            return None
        except Exception as e:
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[RECEIVE ERROR] Failed to receive from '{channel}': {e}")
            return None

    def start_listening(self, channel: str, callback: Optional[Callable] = None, poll_interval: float = 1.0):
        """
        Start listening for messages on a channel in a background thread.
        
        Args:
            channel: The collection name to listen to
            callback: Optional callback function to call when messages arrive
            poll_interval: Time in seconds between polls
        """
        if self.running:
            return
        
        self.running = True
        self.listener_thread = threading.Thread(
            target=self._listen_loop,
            args=(channel, callback, poll_interval),
            daemon=True
        )
        self.listener_thread.start()

    def stop_listening(self, cleanup_channel: Optional[str] = None):
        """
        Stop listening for messages.
        
        Args:
            cleanup_channel: Optional channel to clean up messages from when stopping
        """
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5)
        
        # Cleanup orphaned messages from this sender if specified
        if cleanup_channel:
            self.delete_sender_messages(cleanup_channel, self.client_id)

    def _listen_loop(self, channel: str, callback: Optional[Callable], poll_interval: float):
        """Background listening loop."""
        while self.running:
            try:
                message = self.receive(channel, poll_interval)
                if message:
                    # Call all registered handlers
                    for handler in self.message_handlers:
                        try:
                            handler(message)
                        except Exception as e:
                            if self.debug if hasattr(self, 'debug') else False:
                                print(f"[HANDLER ERROR] {e}")
                    
                    # Call provided callback
                    if callback:
                        try:
                            callback(message)
                        except Exception as e:
                            if self.debug if hasattr(self, 'debug') else False:
                                print(f"[CALLBACK ERROR] {e}")
                
                time.sleep(poll_interval)
            except Exception as e:
                if self.debug if hasattr(self, 'debug') else False:
                    print(f"[LISTEN ERROR] {e}")
                time.sleep(poll_interval)

    def on_message(self, handler: Callable):
        """
        Register a handler to be called when a message is received.
        
        Args:
            handler: Callable that takes a message dict as argument
        """
        self.message_handlers.append(handler)

    # ----------------------
    # Delete and Cleanup Functions
    # ----------------------
    def delete(self, channel: str, doc_id: str) -> bool:
        """
        Delete a document from a Firestore collection.
        
        Args:
            channel: The collection name
            doc_id: The document ID to delete
            
        Returns:
            bool: True if delete was successful, False otherwise
        """
        try:
            url = f"{self.base_url}/{channel}/{doc_id}"
            response = requests.delete(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[DELETE] Document {doc_id} from '{channel}': Status {response.status_code}")
            
            return response.status_code in [200, 204]
        except Exception as e:
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[DELETE ERROR] Failed to delete from '{channel}': {e}")
            return False

    def clear_channel(self, channel: str) -> int:
        """
        Delete all messages from a channel.
        
        Args:
            channel: The collection name to clear
            
        Returns:
            int: Number of documents deleted
        """
        try:
            url = f"{self.base_url}?collectionId={channel}"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                return 0
            
            documents = response.json().get('documents', [])
            deleted_count = 0
            
            for doc in documents:
                doc_id = doc.get('name', '').split('/')[-1]
                if self.delete(channel, doc_id):
                    deleted_count += 1
            
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[CLEANUP] Deleted {deleted_count} messages from '{channel}'")
            
            return deleted_count
        except Exception as e:
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[CLEANUP ERROR] Failed to clear channel '{channel}': {e}")
            return 0

    def delete_sender_messages(self, channel: str, sender_id: str) -> int:
        """
        Delete all messages from a specific sender in a channel.
        Useful for cleanup when a client disconnects.
        
        Args:
            channel: The collection name
            sender_id: The sender ID to delete messages from
            
        Returns:
            int: Number of documents deleted
        """
        try:
            url = f"{self.base_url}?collectionId={channel}"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                return 0
            
            documents = response.json().get('documents', [])
            deleted_count = 0
            
            for doc in documents:
                fields = doc.get('fields', {})
                doc_sender = self._from_firestore_value(fields.get('sender', {}))
                doc_id = doc.get('name', '').split('/')[-1]
                
                if doc_sender == sender_id:
                    if self.delete(channel, doc_id):
                        deleted_count += 1
            
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[CLEANUP] Deleted {deleted_count} messages from sender {sender_id[:8]} in '{channel}'")
            
            return deleted_count
        except Exception as e:
            if self.debug if hasattr(self, 'debug') else False:
                print(f"[CLEANUP ERROR] Failed to delete sender messages: {e}")
            return 0

    
