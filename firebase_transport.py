import requests
import time
import threading
import uuid
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timezone

class FirebaseTransport:
    """
    Transport layer for Firebase Firestore.
    Supports sending, receiving, and async listening with auto-cleanup.
    """
    
    def __init__(self, project_id: str, password: str = "GigaPassword"):
        self.project_id = project_id
        self.password = password
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        self.client_id = str(uuid.uuid4())
        self.running = False
        self.listener_thread = None
        self.message_handlers = []

    # ----------------------
    # Firestore value helpers
    # ----------------------
    def _to_firestore_value(self, data: Any) -> Dict:
        if isinstance(data, str):
            return {'stringValue': data}
        elif isinstance(data, bool):
            return {'booleanValue': data}
        elif isinstance(data, int):
            return {'integerValue': str(data)}
        elif isinstance(data, float):
            return {'doubleValue': data}
        elif isinstance(data, dict):
            return {'mapValue': {'fields': {k: self._to_firestore_value(v) for k, v in data.items()}}}
        elif isinstance(data, list):
            return {'arrayValue': {'values': [self._to_firestore_value(v) for v in data]}}
        elif data is None:
            return {'nullValue': None}
        else:
            return {'stringValue': str(data)}

    def _from_firestore_value(self, value: Dict) -> Any:
        if 'stringValue' in value:
            return value['stringValue']
        elif 'booleanValue' in value:
            return value['booleanValue']
        elif 'integerValue' in value:
            return int(value['integerValue'])
        elif 'doubleValue' in value:
            return value['doubleValue']
        elif 'mapValue' in value:
            return {k: self._from_firestore_value(v) for k, v in value['mapValue'].get('fields', {}).items()}
        elif 'arrayValue' in value:
            return [self._from_firestore_value(v) for v in value['arrayValue'].get('values', [])]
        elif 'nullValue' in value:
            return None
        elif 'timestampValue' in value:
            return value['timestampValue']
        else:
            return None

    def _get_headers(self) -> Dict[str, str]:
        return {'Content-Type': 'application/json'}

    def _delete_message(self, doc_name: str) -> bool:
        try:
            # doc_name format: "projects/PROJECT_ID/databases/(default)/documents/messages/DOC_ID"
            # Need to construct: https://firestore.googleapis.com/v1/projects/PROJECT_ID/databases/(default)/documents/messages/DOC_ID
            if doc_name.startswith('projects/'):
                url = f"https://firestore.googleapis.com/v1/{doc_name}"
            else:
                # Fallback: extract path after domain
                url = f"https://firestore.googleapis.com/v1/{doc_name.split('documents/')[-1]}" if 'documents/' in doc_name else doc_name
            response = requests.delete(url, headers=self._get_headers(), timeout=5)
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"Delete error: {e}")
            return False

    # ----------------------
    # Send & receive
    # ----------------------
    def send(self, channel: str, data: Any) -> bool:
        message_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        document_id = f"{channel}_{message_id}"
        document = {
            'fields': {
                'key': self._to_firestore_value(self.password),
                'id': self._to_firestore_value(message_id),
                'channel': self._to_firestore_value(channel),
                'timestamp': {'timestampValue': timestamp},
                'sender': self._to_firestore_value(self.client_id),
                'data': self._to_firestore_value(data)
            }
        }
        try:
            url = f"{self.base_url}/messages?documentId={document_id}"
            response = requests.post(url, headers=self._get_headers(), json=document, timeout=10)
            if response.status_code not in [200, 201]:
                print(f"SEND STATUS: {response.status_code} {response.text}")
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"Send error: {e}")
            return False

    def receive(self, channel: str, timeout: Optional[float] = None) -> Optional[Dict]:
        start_time = time.time()
        last_seen_id = None
        while True:
            try:
                url = f"{self.base_url}/messages"
                response = requests.get(url, headers=self._get_headers(), timeout=5)
                if response.status_code == 200:
                    documents = response.json().get("documents", [])
                    channel_docs = []
                    for doc in documents:
                        fields = doc.get("fields", {})
                        if self._from_firestore_value(fields.get("channel", {})) == channel:
                            channel_docs.append((doc, fields))
                    channel_docs.sort(key=lambda x: self._from_firestore_value(x[1].get("timestamp", {})), reverse=True)
                    for doc, fields in channel_docs:
                        msg_id = self._from_firestore_value(fields.get("id", {}))
                        sender = self._from_firestore_value(fields.get("sender", {}))
                        if msg_id != last_seen_id and sender != self.client_id:
                            last_seen_id = msg_id
                            message = {
                                "id": msg_id,
                                "timestamp": self._from_firestore_value(fields.get("timestamp", {})),
                                "sender": sender,
                                "data": self._from_firestore_value(fields.get("data", {})),
                                "doc_name": doc.get("name")
                            }
                            # Auto-cleanup
                            if message.get("doc_name"):
                                self._delete_message(message["doc_name"])
                            return message
                if timeout and (time.time() - start_time) > timeout:
                    return None
                time.sleep(0.5)
            except Exception as e:
                print(f"Receive error: {e}")
                if timeout and (time.time() - start_time) > timeout:
                    return None
                time.sleep(1)

    # ----------------------
    # Listener (async)
    # ----------------------
    def _listen_loop(self, channel: str, poll_interval: float):
        seen_ids = set()
        while self.running:
            try:
                url = f"{self.base_url}/messages"
                response = requests.get(url, headers=self._get_headers(), timeout=5)
                if response.status_code == 200:
                    documents = response.json().get("documents", [])
                    channel_docs = []
                    for doc in documents:
                        fields = doc.get("fields", {})
                        if self._from_firestore_value(fields.get("channel", {})) == channel:
                            channel_docs.append((doc, fields))
                    channel_docs.sort(key=lambda x: self._from_firestore_value(x[1].get("timestamp", {})))
                    new_messages = []
                    for doc, fields in channel_docs:
                        msg_id = self._from_firestore_value(fields.get("id", {}))
                        sender = self._from_firestore_value(fields.get("sender", {}))
                        if msg_id not in seen_ids and sender != self.client_id:
                            seen_ids.add(msg_id)
                            new_messages.append({
                                "id": msg_id,
                                "timestamp": self._from_firestore_value(fields.get("timestamp", {})),
                                "sender": sender,
                                "data": self._from_firestore_value(fields.get("data", {})),
                                "doc_name": doc.get("name")
                            })
                    for msg in new_messages:
                        for handler in self.message_handlers:
                            try:
                                handler(msg)
                            except Exception as e:
                                print(f"Handler error: {e}")
                        if msg.get("doc_name"):
                            self._delete_message(msg["doc_name"])
                time.sleep(poll_interval)
            except Exception as e:
                print(f"Listen error: {e}")
                time.sleep(poll_interval)

    def on_message(self, handler: Callable[[Dict], None]):
        self.message_handlers.append(handler)

    def start_listening(self, channel: str, poll_interval: float = 2.0):
        if self.running:
            return
        self.running = True
        self.listener_thread = threading.Thread(
            target=self._listen_loop,
            args=(channel, poll_interval),
            daemon=True
        )
        self.listener_thread.start()

    def stop_listening(self):
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5)
