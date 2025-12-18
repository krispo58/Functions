import requests
import json
import time
import threading
import uuid
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timezone


class FirebaseTransport:
    """
    Firestore REST transport using ONLY Firestore security rules.
    No API key. No OAuth. No service accounts.
    """

    def __init__(self, project_id: str, password: str = "GigaPassword"):
        self.project_id = project_id
        self.password = password
        self.base_url = (
            f"https://firestore.googleapis.com/v1/projects/"
            f"{project_id}/databases/(default)/documents"
        )
        self.client_id = str(uuid.uuid4())
        self.running = False
        self.listener_thread = None
        self.message_handlers = []

    def _get_headers(self) -> Dict[str, str]:
        return {'Content-Type': 'application/json'}

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
        return {'stringValue': str(data)}

    def _from_firestore_value(self, value: Dict) -> Any:
        if 'stringValue' in value:
            return value['stringValue']
        if 'booleanValue' in value:
            return value['booleanValue']
        if 'integerValue' in value:
            return int(value['integerValue'])
        if 'doubleValue' in value:
            return value['doubleValue']
        if 'mapValue' in value:
            return {k: self._from_firestore_value(v)
                    for k, v in value['mapValue'].get('fields', {}).items()}
        if 'arrayValue' in value:
            return [self._from_firestore_value(v)
                    for v in value['arrayValue'].get('values', [])]
        if 'timestampValue' in value:
            return value['timestampValue']
        return None
    
    def _delete_message(self, doc_name: str) -> bool:
        """Delete a single document by its full Firestore path."""
        try:
            url = f"https://firestore.googleapis.com{doc_name.split('firestore.googleapis.com')[-1]}"
            url = self._add_api_key(url)
            response = requests.delete(url, headers=self._get_headers(), timeout=5)
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"Delete error: {e}")
            return False

    def send(self, channel: str, data: Any) -> bool:
        message_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        document = {
            'fields': {
                'key': self._to_firestore_value(self.password),
                'id': self._to_firestore_value(message_id),
                'channel': self._to_firestore_value(channel),
                'timestamp': {'timestampValue': timestamp},
                'sender': self._to_firestore_value(self.client_id),
                'data': self._to_firestore_value(data),
            }
        }

        url = f"{self.base_url}/messages?documentId={channel}_{message_id}"
        r = requests.post(url, headers=self._get_headers(), json=document, timeout=10)
        print("SEND STATUS:", r.status_code, r.text)
        return r.status_code in (200, 201)


    def receive(self, channel: str, timeout: Optional[float] = None) -> Optional[Dict]:
        start_time = time.time()
        last_seen_id = None

        while True:
            try:
                url = f"{self.base_url}/messages"
                url = self._add_api_key(url)
                response = requests.get(url, headers=self._get_headers(), timeout=5)

                if response.status_code == 200:
                    result = response.json()
                    documents = result.get("documents", [])

                    channel_docs = []
                    for doc in documents:
                        fields = doc.get("fields", {})
                        doc_channel = self._from_firestore_value(fields.get("channel", {}))
                        if doc_channel == channel:
                            channel_docs.append((doc, fields))

                    # Sort by timestamp (newest first)
                    channel_docs.sort(
                        key=lambda x: self._from_firestore_value(x[1].get("timestamp", {})),
                        reverse=True
                    )

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
                                "metadata": self._from_firestore_value(fields.get("metadata", {}))
                            }

                            # Auto-cleanup
                            doc_name = doc.get("name")
                            if doc_name:
                                self._delete_message(doc_name)

                            return message

                if timeout and (time.time() - start_time) > timeout:
                    return None

                time.sleep(0.5)
            except Exception as e:
                print(f"Receive error: {e}")
                if timeout and (time.time() - start_time) > timeout:
                    return None

    def stop_listening(self):
        self.running = False
