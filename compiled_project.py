# Compiled Python Project
# This file was automatically generated


# === Module: compiled_project ===
# Compiled Python Project
# This file was automatically generated


# === Module: dnstunnel ===
#!/usr/bin/env python3
"""
DNS Tunnel Library - Pure Transport Layer
Provides DNSTunnelClient and DNSTunnelServer as network communication primitives.
You build your application logic on top of these classes.
"""

import socket
import base64
import struct
import random
import time
import threading
from typing import Optional, Callable
from collections import defaultdict

# ============================================================================
# DNS TUNNEL CLIENT - Pure Transport Layer
# ============================================================================

class DNSTunnelClient:
    """
    DNS Tunnel Client - Handles only network communication.
    
    Use this to send/receive raw bytes through DNS queries.
    Build your application protocol on top.
    """
    
    def __init__(self, server_ip: str, server_port: int, domain: str):
        """
        Initialize DNS tunnel client.
        
        Args:
            server_ip: IP address of tunnel server
            server_port: Port number of tunnel server
            domain: Domain to use for queries (e.g., "tunnel.example.com")
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.domain = domain.rstrip('.').lower()
        self.session_id = random.randint(1000, 9999)
        self.timeout = 5
    
    def send(self, data: bytes, chunk_delay: float = 0.05) -> bool:
        """
        Send raw bytes through DNS tunnel.
        
        Args:
            data: Bytes to send
            chunk_delay: Delay between chunks in seconds
            
        Returns:
            True if successful, False otherwise
        """
        chunks = self._encode_data(data)
        total_chunks = len(chunks)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        
        try:
            for i, chunk in enumerate(chunks):
                subdomain = f"{self.session_id}-{i}-{total_chunks}-{chunk}"
                query = self._create_dns_query(subdomain)
                sock.sendto(query, (self.server_ip, self.server_port))
                
                try:
                    response, _ = sock.recvfrom(512)
                except socket.timeout:
                    pass
                
                time.sleep(chunk_delay)
            
            return True
        except Exception as e:
            print(f"[DNSTunnelClient] Send error: {e}")
            return False
        finally:
            sock.close()
    
    def receive(self, timeout: Optional[int] = None, poll_interval: float = 0.5) -> Optional[bytes]:
        """
        Receive raw bytes through DNS tunnel.
        Automatically handles chunked responses and polls until data is ready.
        
        Args:
            timeout: Total timeout in seconds (uses default if None)
            poll_interval: How often to poll for response in seconds
            
        Returns:
            Received bytes or None if no data/timeout
        """
        total_timeout = timeout or self.timeout
        start_time = time.time()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)  # Short timeout per query
        
        try:
            # Keep polling until we get data or timeout
            while (time.time() - start_time) < total_timeout:
                try:
                    # Request response
                    subdomain = f"recv-{self.session_id}"
                    query = self._create_dns_query(subdomain, query_type=16)
                    sock.sendto(query, (self.server_ip, self.server_port))
                    
                    response, _ = sock.recvfrom(512)
                    data = self._parse_dns_response(response)
                    
                    if not data:
                        # No data yet, wait and try again
                        time.sleep(poll_interval)
                        continue
                    
                    # Check if this is a chunked response
                    if ':' in data and data.count(':') >= 2:
                        parts = data.split(':', 2)
                        try:
                            current_chunk = int(parts[0])
                            total_chunks = int(parts[1])
                            chunk_data = parts[2]
                            
                            # Multi-chunk response
                            all_chunks = [None] * total_chunks
                            all_chunks[current_chunk] = chunk_data
                            
                            # Request remaining chunks
                            for i in range(total_chunks):
                                if i == current_chunk:
                                    continue
                                
                                subdomain = f"recv-{self.session_id}-{i}"
                                query = self._create_dns_query(subdomain, query_type=16)
                                sock.sendto(query, (self.server_ip, self.server_port))
                                
                                response, _ = sock.recvfrom(512)
                                chunk_response = self._parse_dns_response(response)
                                
                                if chunk_response and ':' in chunk_response:
                                    chunk_parts = chunk_response.split(':', 2)
                                    chunk_idx = int(chunk_parts[0])
                                    all_chunks[chunk_idx] = chunk_parts[2]
                            
                            # Reassemble
                            complete_data = ''.join(c for c in all_chunks if c)
                            padding = (8 - len(complete_data) % 8) % 8
                            complete_data += '=' * padding
                            return base64.b32decode(complete_data.upper())
                            
                        except (ValueError, IndexError):
                            # Not a chunked response format, treat as single response
                            pass
                    
                    # Single chunk response (original behavior)
                    padding = (8 - len(data) % 8) % 8
                    data += '=' * padding
                    return base64.b32decode(data.upper())
                
                except socket.timeout:
                    # Query timed out, wait and try again
                    time.sleep(poll_interval)
                    continue
            
            # Total timeout reached
            return None
            
        except Exception as e:
            print(f"[DNSTunnelClient] Receive error: {e}")
            return None
        finally:
            sock.close()
    
    def send_and_receive(self, data: bytes, wait_time: float = 0.5, 
                         timeout: Optional[int] = None) -> Optional[bytes]:
        """
        Convenience method: send data and wait for response.
        
        Args:
            data: Data to send
            wait_time: Time to wait between send and receive
            timeout: Receive timeout
            
        Returns:
            Response bytes or None
        """
        if self.send(data):
            time.sleep(wait_time)
            return self.receive(timeout)
        return None
    
    # Internal methods
    def _encode_data(self, data: bytes, chunk_size: int = 32) -> list:
        """Encode data into DNS-safe chunks."""
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        return [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
    
    def _create_dns_query(self, subdomain: str, query_type: int = 1) -> bytes:
        """Create DNS query packet."""
        transaction_id = random.randint(0, 65535)
        flags = 0x0100
        header = struct.pack('!HHHHHH', transaction_id, flags, 1, 0, 0, 0)
        
        full_domain = f"{subdomain}.{self.domain}"
        question = b''
        for label in full_domain.split('.'):
            question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'
        question += struct.pack('!HH', query_type, 1)
        
        return header + question
    
    def _parse_dns_response(self, response: bytes) -> Optional[str]:
        """Parse DNS response and extract data."""
        try:
            offset = 12
            while response[offset] != 0:
                offset += response[offset] + 1
            offset += 5
            if len(response) <= offset:
                return None
            if response[offset] & 0xC0:
                offset += 2
            else:
                while response[offset] != 0:
                    offset += response[offset] + 1
                offset += 1
            offset += 8
            data_len = struct.unpack('!H', response[offset:offset+2])[0]
            offset += 2
            data = response[offset:offset+data_len]
            
            # TXT records can have multiple strings, each prefixed with length byte
            # Concatenate all strings
            result = []
            i = 0
            while i < len(data):
                str_len = data[i]
                i += 1
                if i + str_len > len(data):
                    break
                result.append(data[i:i+str_len].decode('ascii', errors='ignore'))
                i += str_len
            
            return ''.join(result) if result else None
        except:
            return None


# ============================================================================
# DNS TUNNEL SERVER - Pure Transport Layer
# ============================================================================

class DNSTunnelServer:
    """
    DNS Tunnel Server - Handles only network communication.
    
    Set a callback to receive data from clients.
    Use queue_response() to send data back to clients.
    """
    
    def __init__(self, listen_ip: str, listen_port: int, domain: str):
        """
        Initialize DNS tunnel server.
        
        Args:
            listen_ip: IP to bind to (e.g., "127.0.0.1" or "0.0.0.0")
            listen_port: Port to listen on
            domain: Domain to accept queries for
        """
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.domain = domain.rstrip('.').lower()
        
        # Internal state
        self.sessions = defaultdict(dict)
        self.session_metadata = {}
        self.response_queue = {}
        self.running = False
        self.sock = None
        
        # Callback for when complete data is received
        self.on_data_received: Optional[Callable[[int, bytes, tuple], None]] = None
    
    def queue_response(self, session_id: int, data: bytes):
        """
        Queue data to send back to a client.
        Large data is automatically chunked.
        
        Args:
            session_id: Session ID of the client
            data: Raw bytes to send
        """
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        
        # Split into chunks if data is too large (max ~400 chars per DNS response)
        # This accounts for DNS packet overhead
        chunk_size = 400
        chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
        
        if len(chunks) == 1:
            # Single chunk - store as before
            self.response_queue[session_id] = encoded
        else:
            # Multiple chunks - store with metadata
            self.response_queue[session_id] = {
                'chunks': chunks,
                'total': len(chunks)
            }
    
    def start(self, blocking: bool = True):
        """
        Start the DNS tunnel server.
        
        Args:
            blocking: If True, blocks until stopped. If False, runs in background thread.
        """
        if blocking:
            self._run()
        else:
            thread = threading.Thread(target=self._run, daemon=True)
            thread.start()
    
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.sock:
            self.sock.close()
    
    # Internal methods
    def _run(self):
        """Main server loop."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.sock.bind((self.listen_ip, self.listen_port))
            self.running = True
            self.sock.settimeout(0.1)
            
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(512)
                    threading.Thread(target=self._handle_query, args=(data, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    break
        except Exception as e:
            print(f"[DNSTunnelServer] Error: {e}")
        finally:
            self.stop()
    
    def _handle_query(self, data: bytes, addr: tuple):
        """Handle incoming DNS query."""
        parsed = self._parse_dns_query(data)
        if not parsed:
            return
        
        transaction_id, query_name, query_type = parsed
        decoded = self._decode_subdomain(query_name)
        
        if not decoded:
            response = self._create_dns_response(transaction_id, query_name, query_type)
            self.sock.sendto(response, addr)
            return
        
        session_id, chunk_num, total_chunks, chunk_data = decoded
        
        # Handle receive request (both initial and specific chunks)
        if chunk_data.startswith("RECV"):
            response_data_obj = self.response_queue.get(session_id)
            
            # Extract chunk number if specified
            requested_chunk = 0
            if chunk_data.startswith("RECV-"):
                try:
                    requested_chunk = int(chunk_data.split('-')[1])
                except:
                    requested_chunk = 0
            
            # Check if this is a chunked response
            if isinstance(response_data_obj, dict):
                # Multi-chunk response
                chunks = response_data_obj['chunks']
                total = response_data_obj['total']
                
                if requested_chunk < len(chunks):
                    response_data = f"{requested_chunk}:{total}:{chunks[requested_chunk]}"
                else:
                    response_data = None
            else:
                # Single chunk response (original behavior)
                response_data = response_data_obj
            
            response = self._create_dns_response(transaction_id, query_name, 
                                                query_type, response_data)
            self.sock.sendto(response, addr)
            
            # Only delete if it was a single-chunk response and this was the initial request
            if response_data and not isinstance(response_data_obj, dict) and chunk_data == "RECV":
                del self.response_queue[session_id]
            
            return
        
        # Store chunk
        self.sessions[session_id][chunk_num] = chunk_data
        self.session_metadata[session_id] = (total_chunks, time.time())
        
        # Try to assemble complete message
        complete_data = self._assemble_session_data(session_id)
        if complete_data:
            # Call user's callback
            if self.on_data_received:
                self.on_data_received(session_id, complete_data, addr)
            
            # Clean up session
            del self.sessions[session_id]
            del self.session_metadata[session_id]
        
        # Send response
        response = self._create_dns_response(transaction_id, query_name, query_type)
        self.sock.sendto(response, addr)
    
    def _decode_subdomain(self, query_name: str):
        """Decode data from subdomain."""
        try:
            if not query_name.endswith(self.domain):
                return None
            subdomain = query_name[:-len(self.domain)-1]
            if subdomain.startswith('recv-'):
                parts = subdomain.split('-')
                session_id = int(parts[1])
                # Check if requesting specific chunk: recv-SESSION-CHUNKNUM
                if len(parts) >= 3:
                    return (session_id, -1, -1, f"RECV-{parts[2]}")
                return (session_id, -1, -1, "RECV")
            parts = subdomain.split('-', 3)
            if len(parts) != 4:
                return None
            return int(parts[0]), int(parts[1]), int(parts[2]), parts[3]
        except:
            return None
    
    def _assemble_session_data(self, session_id: int) -> Optional[bytes]:
        """Assemble complete message from chunks."""
        if session_id not in self.session_metadata:
            return None
        total_chunks, _ = self.session_metadata[session_id]
        session_data = self.sessions[session_id]
        if len(session_data) != total_chunks:
            return None
        encoded_data = ''.join(session_data[i] for i in range(total_chunks))
        try:
            padding = (8 - len(encoded_data) % 8) % 8
            encoded_data += '=' * padding
            return base64.b32decode(encoded_data.upper())
        except:
            return None
    
    def _parse_dns_query(self, data: bytes):
        """Parse DNS query packet."""
        try:
            if len(data) < 12:
                return None
            transaction_id = struct.unpack('!H', data[0:2])[0]
            offset = 12
            labels = []
            while offset < len(data) and data[offset] != 0:
                length = data[offset]
                offset += 1
                labels.append(data[offset:offset+length].decode('ascii', errors='ignore'))
                offset += length
            query_name = '.'.join(labels).lower()
            offset += 1
            query_type = struct.unpack('!H', data[offset:offset+2])[0]
            return transaction_id, query_name, query_type
        except:
            return None
    
    def _create_dns_response(self, transaction_id: int, query_name: str, 
                            query_type: int, response_data: Optional[str] = None) -> bytes:
        """Create DNS response packet."""
        flags = 0x8180
        header = struct.pack('!HHHHHH', transaction_id, flags, 1, 1, 0, 0)
        
        question = b''
        for label in query_name.split('.'):
            if label:
                question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'
        question += struct.pack('!HH', query_type, 1)
        
        answer = b'\xc0\x0c'
        answer += struct.pack('!HHI', query_type, 1, 300)
        
        if query_type == 1:
            ip_bytes = socket.inet_aton("127.0.0.1")
            answer += struct.pack('!H', 4) + ip_bytes
        elif query_type == 16:
            if response_data:
                txt_data = response_data.encode('ascii')
                
                # TXT records can have multiple strings, each max 255 bytes
                # Split into chunks if needed
                chunks = []
                max_chunk = 255
                for i in range(0, len(txt_data), max_chunk):
                    chunk = txt_data[i:i+max_chunk]
                    chunks.append(struct.pack('B', len(chunk)) + chunk)
                
                txt_record = b''.join(chunks)
                answer += struct.pack('!H', len(txt_record)) + txt_record
            else:
                answer += struct.pack('!H', 1) + b'\x00'
        
        return header + question + answer

# === Module: firestoreRest ===
import requests
import uuid


def encode_fields(data):
    out = {}
    for k, v in data.items():
        if isinstance(v, bool):
            out[k] = {"booleanValue": v}
        elif isinstance(v, int):
            out[k] = {"integerValue": str(v)}
        elif isinstance(v, float):
            out[k] = {"doubleValue": v}
        elif isinstance(v, dict):
            out[k] = {"mapValue": {"fields": encode_fields(v)}}
        elif isinstance(v, list):
            out[k] = {
                "arrayValue": {
                    "values": [encode_fields({"_": i})["_"] for i in v]
                }
            }
        else:
            out[k] = {"stringValue": str(v)}
    return out


def decode_fields(fields):
    out = {}
    for k, v in fields.items():
        if "stringValue" in v:
            out[k] = v["stringValue"]
        elif "integerValue" in v:
            out[k] = int(v["integerValue"])
        elif "doubleValue" in v:
            out[k] = v["doubleValue"]
        elif "booleanValue" in v:
            out[k] = v["booleanValue"]
        elif "mapValue" in v:
            out[k] = decode_fields(v["mapValue"]["fields"])
        elif "arrayValue" in v:
            out[k] = [decode_fields({"_": i})["_"] for i in v["arrayValue"].get("values", [])]
    return out

class FirestoreREST:
    def __init__(self, project_id, database="(default)"):
        self.base = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/{database}/documents"

    def collection(self, name):
        return CollectionRef(self.base, name)


class CollectionRef:
    def __init__(self, base, name):
        self.url = f"{base}/{name}"

    def document(self, doc_id=None):
        if doc_id is None:
            doc_id = str(uuid.uuid4())
        return DocumentRef(f"{self.url}/{doc_id}", doc_id)

    def add(self, data):
        payload = {"fields": encode_fields(data)}
        r = requests.post(self.url, json=payload)
        r.raise_for_status()
        return r.json()

    def stream(self):
        r = requests.get(self.url)
        r.raise_for_status()
        docs = r.json().get("documents", [])
        for d in docs:
            yield {
                "id": d["name"].split("/")[-1],
                "data": decode_fields(d["fields"])
            }


class DocumentRef:
    def __init__(self, url, doc_id):
        self.url = url
        self.id = doc_id

    def set(self, data):
        payload = {"fields": encode_fields(data)}
        r = requests.patch(self.url, json=payload)
        r.raise_for_status()

    def update(self, data):
        self.set(data)

    def get(self):
        r = requests.get(self.url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return decode_fields(r.json()["fields"])

    def delete(self):
        r = requests.delete(self.url)
        r.raise_for_status()




# === Module: firebase_transport ===
"""
Firestore-based transport layer for client-server communication.

This module provides a socket-like abstraction over Firestore collections,
allowing clients and servers to communicate through document-based messaging.

Communication Model:
- Messages flow through two collections: 'server-channel' and 'client-channel'
- Each message is a document with: id, sender, timestamp, type, and data
- Listeners poll collections for new messages (configurable interval)
- Message IDs are generated server-side to ensure uniqueness
- Messages are cleaned up after being read (optional TTL support)
"""

import uuid
import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Callable, Optional, Dict, Any
import sys
import os
import random

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# MESSAGE MODEL
# ============================================================================

@dataclass
class Message:
    """
    Represents a single message transmitted through the transport.
    
    Attributes:
        id: Unique message identifier (generated server-side)
        sender: UUID of the sender (client_id or server_id)
        timestamp: ISO 8601 timestamp of message creation
        type: Message type ('request', 'response', 'heartbeat', 'ack')
        data: Arbitrary payload (dict)
        ttl_seconds: Time-to-live before message cleanup (None = no cleanup)
    """
    id: str
    sender: str
    timestamp: str
    type: str
    data: dict
    ttl_seconds: Optional[int] = None

    def to_firestore(self) -> dict:
        """Convert message to Firestore document format."""
        doc = asdict(self)
        # Remove None ttl to keep documents clean
        if doc['ttl_seconds'] is None:
            del doc['ttl_seconds']
        return doc

    @staticmethod
    def from_firestore(doc_id: str, fields: dict) -> 'Message':
        """Create Message from Firestore document."""
        return Message(
            id=doc_id,
            sender=fields.get('sender', ''),
            timestamp=fields.get('timestamp', ''),
            type=fields.get('type', ''),
            data=fields.get('data', {}),
            ttl_seconds=fields.get('ttl_seconds')
        )

    def is_expired(self) -> bool:
        """Check if message has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        msg_time = datetime.fromisoformat(self.timestamp)
        expiry_time = msg_time + timedelta(seconds=self.ttl_seconds)
        return datetime.now(msg_time.tzinfo) > expiry_time


# ============================================================================
# TRANSPORT LAYER
# ============================================================================

class FirebaseTransport:
    """
    Socket-like transport layer using Firestore as the communication medium.
    
    Usage:
        # Initialize
        transport = FirebaseTransport(project_id="my-project")
        
        # Set up message handler
        transport.on_message(lambda msg: print(msg['data']))
        
        # Start listening on a channel
        transport.start_listening('client-channel', poll_interval=0.5)
        
        # Send message to a channel
        transport.send('server-channel', {'command': 'ping'})
        
        # Start heartbeat to keep session alive
        transport.start_heartbeat()
    """

    def __init__(self, project_id: str, database: str = "(default)"):
        """
        Initialize the transport layer.
        
        Args:
            project_id: Firebase project ID
            database: Firestore database name (default is usually correct)
        """
        self.project_id = project_id
        self.client_id = str(uuid.uuid4())
        self.debug = False
        
        # Initialize Firestore REST client
        self.fs = firestoreRest.FirestoreREST(project_id, database)
        
        # Message callback
        self._message_callback: Optional[Callable] = None
        
        # Listener state
        self._listener_running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._listener_lock = threading.Lock()
        self._last_seen_timestamps: Dict[str, float] = {}
        
        # Session management
        self._session_active = False
        self._heartbeat_running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._session_timeout = 60  # 60 seconds of inactivity = session expired
        self._last_activity_time = time.time()
        
        # Retry configuration
        self._max_retries = 3
        self._base_retry_delay = 0.5  # seconds
        
        # Message cleanup
        self._cleanup_running = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_interval = 30  # Check for expired messages every 30 seconds

    def on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback to handle incoming messages.
        
        Args:
            callback: Function that takes a message dict as argument
        """
        self._message_callback = callback

    def _retry_operation(self, operation, *args, operation_name: str = "operation"):
        """
        Execute an operation with exponential backoff retry.
        
        Args:
            operation: Callable to execute
            *args: Arguments to pass to operation
            operation_name: Name for debugging
            
        Returns:
            Result of operation or None if all retries exhausted
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self._max_retries):
            try:
                return operation(*args)
            except Exception as e:
                last_exception = e
                
                if attempt < self._max_retries - 1:
                    # Exponential backoff with jitter
                    delay = self._base_retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    if self.debug:
                        print(f"[TRANSPORT] Retry {attempt + 1}/{self._max_retries} for {operation_name} "
                              f"after {delay:.2f}s (Error: {str(e)[:50]})")
                    time.sleep(delay)
        
        error_msg = f"[TRANSPORT] Failed {operation_name} after {self._max_retries} attempts: {str(last_exception)}"
        if self.debug:
            print(error_msg)
        raise last_exception

    def start_listening(self, channel: str, poll_interval: float = 0.5) -> None:
        """
        Start listening for messages on a channel.
        
        Args:
            channel: Channel name ('server-channel' or 'client-channel')
            poll_interval: Time in seconds between polls for new messages
        """
        if self._listener_running:
            if self.debug:
                print(f"[TRANSPORT] Listener already running on {channel}")
            return

        self._listener_running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            args=(channel, poll_interval),
            daemon=True
        )
        self._listener_thread.start()
        if self.debug:
            print(f"[TRANSPORT] Started listening on '{channel}'")

    def stop_listening(self) -> None:
        """Stop the message listener."""
        self._listener_running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=5)
        if self.debug:
            print("[TRANSPORT] Stopped listening")

    def send(self, channel: str, data: dict, msg_type: str = 'request') -> str:
        """
        Send a message to a channel.
        
        Args:
            channel: Channel name ('server-channel' or 'client-channel')
            data: Message payload (dict)
            msg_type: Message type identifier
            
        Returns:
            Message ID of the sent message
            
        Raises:
            Exception: If message could not be sent after retries
        """
        msg = Message(
            id=str(uuid.uuid4()),
            sender=self.client_id,
            timestamp=datetime.now().isoformat(),
            type=msg_type,
            data=data,
            ttl_seconds=300  # 5 minute cleanup
        )

        def _do_send():
            collection = self.fs.collection(channel)
            doc_ref = collection.document(msg.id)
            doc_ref.set(msg.to_firestore())
            self._last_activity_time = time.time()
        
        try:
            self._retry_operation(_do_send, operation_name=f"send to '{channel}'")
            
            if self.debug:
                print(f"[TRANSPORT] Sent message {msg.id[:8]} to '{channel}'")
            
            return msg.id
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error sending message: {e}")
            raise

    def _listen_loop(self, channel: str, poll_interval: float) -> None:
        """
        Poll the channel for new messages (runs in background thread).
        
        Args:
            channel: Channel to listen on
            poll_interval: Polling interval in seconds
        """
        consecutive_errors = 0
        
        try:
            while self._listener_running:
                try:
                    def _do_stream():
                        collection = self.fs.collection(channel)
                        return list(collection.stream())
                    
                    docs = self._retry_operation(_do_stream, operation_name=f"stream from '{channel}'")
                    consecutive_errors = 0  # Reset on success
                    
                    for doc in docs:
                        doc_id = doc['id']
                        fields = doc['data']
                        
                        # Parse message
                        try:
                            msg = Message.from_firestore(doc_id, fields)
                            
                            # Skip if we've already processed this message
                            msg_timestamp = datetime.fromisoformat(msg.timestamp).timestamp()
                            if doc_id in self._last_seen_timestamps:
                                if self._last_seen_timestamps[doc_id] >= msg_timestamp:
                                    continue
                            
                            # Skip expired messages
                            if msg.is_expired():
                                continue
                            
                            # Update tracking and dispatch
                            self._last_seen_timestamps[doc_id] = msg_timestamp
                            self._last_activity_time = time.time()
                            
                            if self._message_callback:
                                callback_msg = {
                                    'id': msg.id,
                                    'sender': msg.sender,
                                    'timestamp': msg.timestamp,
                                    'type': msg.type,
                                    'data': msg.data
                                }
                                if self.debug:
                                    print(f"[TRANSPORT] Received message {msg.id[:8]} from '{channel}'")
                                
                                self._message_callback(callback_msg)
                        
                        except Exception as e:
                            if self.debug:
                                print(f"[TRANSPORT] Error parsing message {doc_id}: {e}")
                    
                    # Sleep before next poll
                    time.sleep(poll_interval)
                
                except Exception as e:
                    consecutive_errors += 1
                    if self.debug:
                        print(f"[TRANSPORT] Error in listener loop (consecutive: {consecutive_errors}): {e}")
                    
                    # Back off longer if consecutive errors
                    backoff = min(poll_interval * (consecutive_errors ** 2), 10.0)
                    time.sleep(backoff)
        
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Critical error in listener: {e}")
            self._listener_running = False

    def get_client_id(self) -> str:
        """Get this transport's unique client ID."""
        return self.client_id

    def start_heartbeat(self) -> None:
        """
        Start heartbeat to keep session alive.
        Periodically sends heartbeat messages to prevent session timeout.
        """
        if self._heartbeat_running:
            if self.debug:
                print("[TRANSPORT] Heartbeat already running")
            return
        
        self._session_active = True
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self._heartbeat_thread.start()
        if self.debug:
            print("[TRANSPORT] Started heartbeat")

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat."""
        self._heartbeat_running = False
        self._session_active = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        if self.debug:
            print("[TRANSPORT] Stopped heartbeat")

    def _heartbeat_loop(self) -> None:
        """Periodically update activity time to keep session alive."""
        try:
            while self._heartbeat_running:
                self._last_activity_time = time.time()
                time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error in heartbeat loop: {e}")
            self._heartbeat_running = False

    def _is_session_active(self, client_id: str = None) -> bool:
        """
        Check if a session is still active.
        
        Args:
            client_id: Session ID to check (defaults to self.client_id)
            
        Returns:
            True if session is active (hasn't timed out)
        """
        if client_id is None:
            client_id = self.client_id
        
        if client_id != self.client_id:
            # Can't track other sessions, assume active if heartbeat running
            return self._session_active
        
        if not self._session_active:
            return False
        
        elapsed = time.time() - self._last_activity_time
        is_active = elapsed < self._session_timeout
        
        if not is_active and self.debug:
            print(f"[TRANSPORT] Session expired after {elapsed:.1f}s of inactivity")
        
        return is_active

    def start_cleanup(self) -> None:
        """
        Start background cleanup thread to remove expired messages.
        This runs independently of the listener.
        """
        if self._cleanup_running:
            if self.debug:
                print("[TRANSPORT] Cleanup already running")
            return
        
        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
        if self.debug:
            print("[TRANSPORT] Started message cleanup")

    def stop_cleanup(self) -> None:
        """Stop the cleanup thread."""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        if self.debug:
            print("[TRANSPORT] Stopped message cleanup")

    def _cleanup_loop(self) -> None:
        """Periodically clean up expired messages from all channels."""
        channels = ['server-channel', 'client-channel']
        
        try:
            while self._cleanup_running:
                for channel in channels:
                    try:
                        self._cleanup_channel(channel)
                    except Exception as e:
                        if self.debug:
                            print(f"[TRANSPORT] Error cleaning {channel}: {e}")
                
                time.sleep(self._cleanup_interval)
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error in cleanup loop: {e}")
            self._cleanup_running = False

    def _cleanup_channel(self, channel: str) -> None:
        """Remove expired messages from a channel."""
        try:
            def _do_stream():
                collection = self.fs.collection(channel)
                return list(collection.stream())
            
            docs = self._retry_operation(_do_stream, operation_name=f"cleanup stream from '{channel}'")
            
            deleted_count = 0
            for doc in docs:
                doc_id = doc['id']
                fields = doc['data']
                
                try:
                    msg = Message.from_firestore(doc_id, fields)
                    if msg.is_expired():
                        def _do_delete():
                            collection = self.fs.collection(channel)
                            doc_ref = collection.document(doc_id)
                            doc_ref.delete()
                        
                        self._retry_operation(_do_delete, operation_name=f"delete from '{channel}'")
                        deleted_count += 1
                
                except Exception as e:
                    if self.debug:
                        print(f"[TRANSPORT] Error checking expiry of {doc_id}: {e}")
            
            if deleted_count > 0 and self.debug:
                print(f"[TRANSPORT] Cleaned up {deleted_count} expired messages from '{channel}'")
        
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error cleaning up channel {channel}: {e}")

    def __repr__(self) -> str:
        """String representation."""
        return f"FirebaseTransport(project_id={self.project_id}, client_id={self.client_id[:8]})"


# === Module: Install ===
import os
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

class PythonCompiler:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.files: Dict[str, str] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        
    def find_python_files(self, exclude_patterns: List[str] = None) -> List[Path]:
        """Find all Python files in the project."""
        if exclude_patterns is None:
            exclude_patterns = ['__pycache__', '.venv', 'venv', '.git', 'tests']
        
        py_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            for file in files:
                if file.endswith('.py'):
                    py_files.append(Path(root) / file)
        
        return py_files
    
    def parse_imports(self, content: str, file_path: Path) -> Set[str]:
        """Extract local imports from a Python file."""
        local_imports = set()
        
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        local_imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:  # Absolute import
                        local_imports.add(node.module.split('.')[0])
        except SyntaxError:
            print(f"Warning: Syntax error in {file_path}")
        
        return local_imports
    
    def remove_imports(self, content: str, local_modules: Set[str]) -> str:
        """Remove local imports from the code."""
        lines = []
        tree = ast.parse(content)
        
        # Track which lines to keep
        lines_to_remove = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in local_modules:
                        lines_to_remove.add(node.lineno)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in local_modules:
                    lines_to_remove.add(node.lineno)
        
        # Rebuild content without local imports
        content_lines = content.split('\n')
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result)
    
    def remove_main_blocks(self, content: str) -> str:
        """Remove if __name__ == '__main__' blocks and main() function definitions."""
        tree = ast.parse(content)
        content_lines = content.split('\n')
        lines_to_remove = set()
        
        for node in tree.body:
            # Remove if __name__ == '__main__' blocks
            if isinstance(node, ast.If):
                # Check if it's a __name__ == '__main__' check
                if self._is_main_guard(node.test):
                    # Mark all lines in this block for removal
                    start_line = node.lineno
                    end_line = node.end_lineno
                    for line_num in range(start_line, end_line + 1):
                        lines_to_remove.add(line_num)
            
            # Remove main() function definitions
            elif isinstance(node, ast.FunctionDef) and node.name == 'main':
                start_line = node.lineno
                end_line = node.end_lineno
                for line_num in range(start_line, end_line + 1):
                    lines_to_remove.add(line_num)
        
        # Rebuild content without main blocks
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result)
    
    def _is_main_guard(self, node) -> bool:
        """Check if an AST node is a __name__ == '__main__' check."""
        if isinstance(node, ast.Compare):
            # Check for __name__ == '__main__' or '__main__' == __name__
            if isinstance(node.left, ast.Name) and node.left.id == '__name__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value == '__main__':
                            return True
            elif isinstance(node.left, ast.Constant) and node.left.value == '__main__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Name) and comp.id == '__name__':
                            return True
        return False
    
    def get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        relative = file_path.relative_to(self.project_root)
        parts = list(relative.parts[:-1]) + [relative.stem]
        if parts[-1] == '__init__':
            parts = parts[:-1]
        return '.'.join(parts) if parts else '__main__'
    
    def topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        """Sort modules by dependencies."""
        visited = set()
        result = []
        
        def visit(node):
            if node in visited:
                return
            visited.add(node)
            for dep in graph.get(node, set()):
                if dep in graph:  # Only visit if it's a local module
                    visit(dep)
            result.append(node)
        
        for node in graph:
            visit(node)
        
        return result
    
    def compile_project(self, exclude_patterns: List[str] = None, entry_point: str = None) -> str:
        """Compile all Python files into a single executable string.
        
        Args:
            exclude_patterns: List of directory/file patterns to exclude
            entry_point: Path to entry point file (e.g., 'main.py' or 'src/app.py')
                        Only this file will keep its main() and if __name__ == '__main__' blocks
        """
        py_files = self.find_python_files(exclude_patterns)
        
        # Determine the entry point module name
        entry_module = None
        if entry_point:
            entry_path = self.project_root / entry_point
            if entry_path.exists():
                entry_module = self.get_module_name(entry_path)
        
        # Read all files and build dependency graph
        module_contents = {}
        local_modules = set()
        
        for file_path in py_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            module_name = self.get_module_name(file_path)
            module_contents[module_name] = content
            local_modules.add(module_name)
            
            imports = self.parse_imports(content, file_path)
            self.dependencies[module_name] = imports
        
        # Sort modules by dependencies
        sorted_modules = self.topological_sort(self.dependencies)
        
        # Build combined code
        compiled_parts = []
        compiled_parts.append("# Compiled Python Project\n")
        compiled_parts.append("# This file was automatically generated\n\n")
        
        for module_name in sorted_modules:
            if module_name in module_contents:
                content = module_contents[module_name]
                
                # Remove local imports
                cleaned_content = self.remove_imports(content, local_modules)
                
                # Remove main blocks unless this is the entry point
                if module_name != entry_module:
                    cleaned_content = self.remove_main_blocks(cleaned_content)
                
                compiled_parts.append(f"\n# === Module: {module_name} ===\n")
                compiled_parts.append(cleaned_content)
                compiled_parts.append("\n")
        
        return ''.join(compiled_parts)


# Example usage

# === Module: client.client ===
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
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
        self.tunnel.stop_heartbeat()
        self.tunnel.stop_cleanup()

# === Module: client.main ===
import time
import client as networkclient
import wordwrapper
import pythoncom
import pywintypes
import os

os.environ["FIREBASE_PROJECT_ID"] = "my-awesome-project-3c43d"



#server_ip ="51.175.238.64"
#server_port = 7777
#domain = "ordbokene.no"

word = wordwrapper.WordWrapper(visible=True)
client = networkclient.Client(debug=True)
word_is_open = True
stop = False

def reset(args: list[str]):
    if client.new_chat():
        word.write_start("word")
    else:
        word.write_start("sentence")


def test(args: list[str]):
    word.write_end("t")
    word.replace_text("::test::", "")

def stop_program(args: list[str]):
    global stop
    stop = True

commands = {
    "stop": stop_program,
    "new": reset,
    "reset": reset,
    "test": test
}
def find_prompt_replace(word: wordwrapper.WordWrapper):
    word.make_hidden_visible()
    prompt = word.get_block("--", "--")
    prompt = prompt if isinstance(prompt, str) else prompt[0]

    if prompt is None:
        return
    r = client.send_prompt(prompt)
    word.replace_blocks(f"--", "--", "") #Delete prompt from document
    word.replace_block(",,", ",,", r)

def handle_deactivated(word: wordwrapper.WordWrapper):
    global word_is_open

    try:
        word.make_hidden_visible()
        word.replace_blocks("", ";;;", "")

        prompt = word.get_block("--", "--") is not None
        command = word.get_block("::", "::")
        
        print(prompt, command)


        if prompt:
                find_prompt_replace(word)
        if command is not None:
            command = command if isinstance(command, str) else command[0]
            commands[command]([word.get_block(",,", ",,")])
            word.replace_blocks("::", "::", "")
        print("Flashing taskbar")
        word.flash_taskbar(1)
    except pywintypes.com_error as e:
        print("Word disconnected, waiting for reconnect...")
        print(e)
        word_is_open = False



# === Module: client.wordwrapper ===
import win32com.client as win32
import pythoncom
import win32gui
import win32process
import win32con
import win32api
import ctypes
from ctypes import wintypes, Structure
from ctypes import windll, CFUNCTYPE, c_int, c_void_p, POINTER, c_uint, c_bool


class FLASHWINFO(Structure):
    """Structure for FlashWindowEx API."""
    _fields_ = [("cbSize", c_uint),
                ("hwnd", c_void_p),
                ("dwFlags", c_uint),
                ("uCount", c_uint),
                ("dwTimeout", c_uint)]


# Flash window flags
FLASHW_STOP = 0
FLASHW_CAPTION = 1
FLASHW_TRAY = 2
FLASHW_ALL = 3
FLASHW_TIMER = 4
FLASHW_TIMERNOFG = 12


class WordWrapper:
    def __init__(self, visible=False):
        pythoncom.CoInitialize()

        try:
            self.word = win32.GetActiveObject("Word.Application")
        except:
            try:
                self.word = win32.gencache.EnsureDispatch("Word.Application")
            except:
                raise Exception("Could not start or connect to Word application. Is word installed?")

        self.word.Visible = visible
        self.doc = None

        # event callbacks
        self.on_word_activated = None
        self.on_word_deactivated = None

        self._last_active_was_word = False

        # start listening to window focus changes
        self._start_focus_hook()

    def _is_word_window(self, hwnd):
        """Check if the foreground window belongs to WINWORD.EXE."""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            return "WINWORD.EXE" in exe_path.upper()
        except:
            return False

    def _start_focus_hook(self):
        """Hooks foreground window change."""
        WinEventProcType = CFUNCTYPE(
            None, c_void_p, c_int, c_void_p, c_int, c_int, c_int, c_int
        )

        def callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            is_word = self._is_word_window(hwnd)

            # Word just became active
            if is_word and not self._last_active_was_word:
                self._last_active_was_word = True
                if self.on_word_activated:
                    self.on_word_activated(self)

            # Word just got unfocused
            if not is_word and self._last_active_was_word:
                self._last_active_was_word = False
                if self.on_word_deactivated:
                    self.on_word_deactivated(self)

        self._win_event_proc = WinEventProcType(callback)

        windll.user32.SetWinEventHook(
            win32con.EVENT_SYSTEM_FOREGROUND,
            win32con.EVENT_SYSTEM_FOREGROUND,
            0,
            self._win_event_proc,
            0,
            0,
            win32con.WINEVENT_OUTOFCONTEXT
        )

    def try_reconnect(self):
        try:
            self.word = win32.GetActiveObject("Word.Application")
            self.use_active_doc()
            return True
        except:
            return False   

    def get_text(self, start: int = None, end: int = None) -> str:
        """Get text from the document or range."""
        if not self.doc:
            raise Exception("No document loaded bro.")

        if start is None or end is None:
            rng = self.doc.Content
        else:
            rng = self.doc.Range(start, end)

        return rng.Text

    def list_open_docs(self):
        docs = []
        for i in range(1, self.word.Documents.Count + 1):
            docs.append(self.word.Documents.Item(i).FullName)
        return docs

    def use_active_doc(self):
        """Use the currently active Word document."""
        if self.word.Documents.Count == 0:
            raise Exception("No documents are open in Word, bro.")
        self.doc = self.word.ActiveDocument
        return self.doc

    def open_doc(self, path):
        """Open a document (or attach if already open)."""
        for i in range(1, self.word.Documents.Count + 1):
            doc = self.word.Documents.Item(i)
            if doc.FullName.lower() == path.lower():
                self.doc = doc
                return self.doc

        self.doc = self.word.Documents.Open(path)
        return self.doc
    
    def open_new_doc(self):
        """
        Creates a new blank Word document and sets it as the active doc.
        """
        self.doc = self.word.Documents.Add()
        return self.doc

    def write_end(self, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range()
        rng.Font.Hidden = False
        rng.InsertAfter(text)

    def write_start(self, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(0, 0)
        rng.Font.Hidden = False
        rng.InsertBefore(text)

    def insert_at(self, start, end, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(start, end)
        rng.Font.Hidden = False
        rng.Text = text

    def replace_text(self, old, new):
        """
        Replaces all occurrences of old text with new text.
        Works with long replacement text by using Range.Text instead of Find.Replacement.
        """
        if not self.doc:
            raise Exception("No document loaded bro.")
        
        rng = self.doc.Content
        full_text = rng.Text
        
        # If old text not found, return early
        if old not in full_text:
            return False
        
        # Find and replace each occurrence
        while True:
            full_text = self.doc.Content.Text
            start_idx = full_text.find(old)
            
            if start_idx == -1:
                break
            
            # Replace using Range.Text for long text support
            replace_rng = self.doc.Range(start_idx, start_idx + len(old))
            replace_rng.Font.Hidden = False
            replace_rng.Text = new
        
        return True

    def replace_blocks(self, prefix="###", suffix="###", replacement="hello world"):
        """
        Replaces all occurrences of content wrapped in prefix...suffix.
        Works with large replacement text.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        replaced_count = 0
        
        while True:
            rng = self.doc.Content
            full_text = rng.Text

            start_idx = full_text.find(prefix)
            if start_idx == -1:
                break

            end_idx = full_text.find(suffix, start_idx + len(prefix))
            if end_idx == -1:
                break

            replace_rng = self.doc.Range(start_idx, end_idx + len(suffix))
            replace_rng.Font.Hidden = False
            replace_rng.Text = replacement
            replaced_count += 1

        return replaced_count

    def get_blocks(self, prefix="###", suffix="###", ):
        """
        Returns a list of all text content inside prefix...suffix blocks.
        Returns None list if none found.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text
        
        blocks = []
        search_pos = 0
        
        while True:
            start = full_text.find(prefix, search_pos)
            if start == -1:
                break
            
            start += len(prefix)
            end = full_text.find(suffix, start)
            if end == -1:
                break
            
            blocks.append(full_text[start:end])
            search_pos = end + len(suffix)

        if len(blocks) == 0:
            return None

        return blocks

    def replace_block(self, prefix="###", suffix="###", replacement="hello world"):
        """
        Replaces the first occurrence of content wrapped in prefix...suffix.
        Works with large replacement text.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text

        start_idx = full_text.find(prefix)
        if start_idx == -1:
            return False

        end_idx = full_text.find(suffix, start_idx + len(prefix))
        if end_idx == -1:
            return False

        replace_rng = self.doc.Range(start_idx, end_idx + len(suffix))
        replace_rng.Font.Hidden = False
        replace_rng.Text = replacement

        return True

    def get_block(self, prefix="###", suffix="###"):
        """
        Returns the text inside  the first occurance of prefix...suffix.
        Returns None if not found.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text

        start = full_text.find(prefix)
        if start == -1:
            return None

        start += len(prefix)
        end = full_text.find(suffix, start)
        if end == -1:
            return None

        return full_text[start:end]

    def make_hidden_visible(self):
        """Makes all hidden text in the document visible."""
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Content
        rng.Font.Hidden = False

    def save(self):
        if self.doc:
            self.doc.Save()

    def flash_taskbar(self, count=3, timeout=500):
        """
        Flashes the Word icon in the taskbar.
        
        Args:
            count: Number of times to flash (default: 3)
            timeout: Duration in milliseconds between flashes (default: 500)
        """
        try:
            hwnd = self.word.hwnd
            fwinfo = FLASHWINFO()
            fwinfo.cbSize = ctypes.sizeof(FLASHWINFO)
            fwinfo.hwnd = hwnd
            fwinfo.dwFlags = FLASHW_ALL
            fwinfo.uCount = count
            fwinfo.dwTimeout = timeout
            
            windll.user32.FlashWindowEx(ctypes.byref(fwinfo))
            return True
        except:
            return False

    def close_doc(self):
        if self.doc:
            self.doc.Close()
            self.doc = None

    def quit(self):
        self.word.Quit()
        self.word = None


# === Module: dnstunnel ===
#!/usr/bin/env python3
"""
DNS Tunnel Library - Pure Transport Layer
Provides DNSTunnelClient and DNSTunnelServer as network communication primitives.
You build your application logic on top of these classes.
"""

import socket
import base64
import struct
import random
import time
import threading
from typing import Optional, Callable
from collections import defaultdict

# ============================================================================
# DNS TUNNEL CLIENT - Pure Transport Layer
# ============================================================================

class DNSTunnelClient:
    """
    DNS Tunnel Client - Handles only network communication.
    
    Use this to send/receive raw bytes through DNS queries.
    Build your application protocol on top.
    """
    
    def __init__(self, server_ip: str, server_port: int, domain: str):
        """
        Initialize DNS tunnel client.
        
        Args:
            server_ip: IP address of tunnel server
            server_port: Port number of tunnel server
            domain: Domain to use for queries (e.g., "tunnel.example.com")
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.domain = domain.rstrip('.').lower()
        self.session_id = random.randint(1000, 9999)
        self.timeout = 5
    
    def send(self, data: bytes, chunk_delay: float = 0.05) -> bool:
        """
        Send raw bytes through DNS tunnel.
        
        Args:
            data: Bytes to send
            chunk_delay: Delay between chunks in seconds
            
        Returns:
            True if successful, False otherwise
        """
        chunks = self._encode_data(data)
        total_chunks = len(chunks)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        
        try:
            for i, chunk in enumerate(chunks):
                subdomain = f"{self.session_id}-{i}-{total_chunks}-{chunk}"
                query = self._create_dns_query(subdomain)
                sock.sendto(query, (self.server_ip, self.server_port))
                
                try:
                    response, _ = sock.recvfrom(512)
                except socket.timeout:
                    pass
                
                time.sleep(chunk_delay)
            
            return True
        except Exception as e:
            print(f"[DNSTunnelClient] Send error: {e}")
            return False
        finally:
            sock.close()
    
    def receive(self, timeout: Optional[int] = None, poll_interval: float = 0.5) -> Optional[bytes]:
        """
        Receive raw bytes through DNS tunnel.
        Automatically handles chunked responses and polls until data is ready.
        
        Args:
            timeout: Total timeout in seconds (uses default if None)
            poll_interval: How often to poll for response in seconds
            
        Returns:
            Received bytes or None if no data/timeout
        """
        total_timeout = timeout or self.timeout
        start_time = time.time()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)  # Short timeout per query
        
        try:
            # Keep polling until we get data or timeout
            while (time.time() - start_time) < total_timeout:
                try:
                    # Request response
                    subdomain = f"recv-{self.session_id}"
                    query = self._create_dns_query(subdomain, query_type=16)
                    sock.sendto(query, (self.server_ip, self.server_port))
                    
                    response, _ = sock.recvfrom(512)
                    data = self._parse_dns_response(response)
                    
                    if not data:
                        # No data yet, wait and try again
                        time.sleep(poll_interval)
                        continue
                    
                    # Check if this is a chunked response
                    if ':' in data and data.count(':') >= 2:
                        parts = data.split(':', 2)
                        try:
                            current_chunk = int(parts[0])
                            total_chunks = int(parts[1])
                            chunk_data = parts[2]
                            
                            # Multi-chunk response
                            all_chunks = [None] * total_chunks
                            all_chunks[current_chunk] = chunk_data
                            
                            # Request remaining chunks
                            for i in range(total_chunks):
                                if i == current_chunk:
                                    continue
                                
                                subdomain = f"recv-{self.session_id}-{i}"
                                query = self._create_dns_query(subdomain, query_type=16)
                                sock.sendto(query, (self.server_ip, self.server_port))
                                
                                response, _ = sock.recvfrom(512)
                                chunk_response = self._parse_dns_response(response)
                                
                                if chunk_response and ':' in chunk_response:
                                    chunk_parts = chunk_response.split(':', 2)
                                    chunk_idx = int(chunk_parts[0])
                                    all_chunks[chunk_idx] = chunk_parts[2]
                            
                            # Reassemble
                            complete_data = ''.join(c for c in all_chunks if c)
                            padding = (8 - len(complete_data) % 8) % 8
                            complete_data += '=' * padding
                            return base64.b32decode(complete_data.upper())
                            
                        except (ValueError, IndexError):
                            # Not a chunked response format, treat as single response
                            pass
                    
                    # Single chunk response (original behavior)
                    padding = (8 - len(data) % 8) % 8
                    data += '=' * padding
                    return base64.b32decode(data.upper())
                
                except socket.timeout:
                    # Query timed out, wait and try again
                    time.sleep(poll_interval)
                    continue
            
            # Total timeout reached
            return None
            
        except Exception as e:
            print(f"[DNSTunnelClient] Receive error: {e}")
            return None
        finally:
            sock.close()
    
    def send_and_receive(self, data: bytes, wait_time: float = 0.5, 
                         timeout: Optional[int] = None) -> Optional[bytes]:
        """
        Convenience method: send data and wait for response.
        
        Args:
            data: Data to send
            wait_time: Time to wait between send and receive
            timeout: Receive timeout
            
        Returns:
            Response bytes or None
        """
        if self.send(data):
            time.sleep(wait_time)
            return self.receive(timeout)
        return None
    
    # Internal methods
    def _encode_data(self, data: bytes, chunk_size: int = 32) -> list:
        """Encode data into DNS-safe chunks."""
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        return [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
    
    def _create_dns_query(self, subdomain: str, query_type: int = 1) -> bytes:
        """Create DNS query packet."""
        transaction_id = random.randint(0, 65535)
        flags = 0x0100
        header = struct.pack('!HHHHHH', transaction_id, flags, 1, 0, 0, 0)
        
        full_domain = f"{subdomain}.{self.domain}"
        question = b''
        for label in full_domain.split('.'):
            question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'
        question += struct.pack('!HH', query_type, 1)
        
        return header + question
    
    def _parse_dns_response(self, response: bytes) -> Optional[str]:
        """Parse DNS response and extract data."""
        try:
            offset = 12
            while response[offset] != 0:
                offset += response[offset] + 1
            offset += 5
            if len(response) <= offset:
                return None
            if response[offset] & 0xC0:
                offset += 2
            else:
                while response[offset] != 0:
                    offset += response[offset] + 1
                offset += 1
            offset += 8
            data_len = struct.unpack('!H', response[offset:offset+2])[0]
            offset += 2
            data = response[offset:offset+data_len]
            
            # TXT records can have multiple strings, each prefixed with length byte
            # Concatenate all strings
            result = []
            i = 0
            while i < len(data):
                str_len = data[i]
                i += 1
                if i + str_len > len(data):
                    break
                result.append(data[i:i+str_len].decode('ascii', errors='ignore'))
                i += str_len
            
            return ''.join(result) if result else None
        except:
            return None


# ============================================================================
# DNS TUNNEL SERVER - Pure Transport Layer
# ============================================================================

class DNSTunnelServer:
    """
    DNS Tunnel Server - Handles only network communication.
    
    Set a callback to receive data from clients.
    Use queue_response() to send data back to clients.
    """
    
    def __init__(self, listen_ip: str, listen_port: int, domain: str):
        """
        Initialize DNS tunnel server.
        
        Args:
            listen_ip: IP to bind to (e.g., "127.0.0.1" or "0.0.0.0")
            listen_port: Port to listen on
            domain: Domain to accept queries for
        """
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.domain = domain.rstrip('.').lower()
        
        # Internal state
        self.sessions = defaultdict(dict)
        self.session_metadata = {}
        self.response_queue = {}
        self.running = False
        self.sock = None
        
        # Callback for when complete data is received
        self.on_data_received: Optional[Callable[[int, bytes, tuple], None]] = None
    
    def queue_response(self, session_id: int, data: bytes):
        """
        Queue data to send back to a client.
        Large data is automatically chunked.
        
        Args:
            session_id: Session ID of the client
            data: Raw bytes to send
        """
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        
        # Split into chunks if data is too large (max ~400 chars per DNS response)
        # This accounts for DNS packet overhead
        chunk_size = 400
        chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
        
        if len(chunks) == 1:
            # Single chunk - store as before
            self.response_queue[session_id] = encoded
        else:
            # Multiple chunks - store with metadata
            self.response_queue[session_id] = {
                'chunks': chunks,
                'total': len(chunks)
            }
    
    def start(self, blocking: bool = True):
        """
        Start the DNS tunnel server.
        
        Args:
            blocking: If True, blocks until stopped. If False, runs in background thread.
        """
        if blocking:
            self._run()
        else:
            thread = threading.Thread(target=self._run, daemon=True)
            thread.start()
    
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.sock:
            self.sock.close()
    
    # Internal methods
    def _run(self):
        """Main server loop."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.sock.bind((self.listen_ip, self.listen_port))
            self.running = True
            self.sock.settimeout(0.1)
            
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(512)
                    threading.Thread(target=self._handle_query, args=(data, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    break
        except Exception as e:
            print(f"[DNSTunnelServer] Error: {e}")
        finally:
            self.stop()
    
    def _handle_query(self, data: bytes, addr: tuple):
        """Handle incoming DNS query."""
        parsed = self._parse_dns_query(data)
        if not parsed:
            return
        
        transaction_id, query_name, query_type = parsed
        decoded = self._decode_subdomain(query_name)
        
        if not decoded:
            response = self._create_dns_response(transaction_id, query_name, query_type)
            self.sock.sendto(response, addr)
            return
        
        session_id, chunk_num, total_chunks, chunk_data = decoded
        
        # Handle receive request (both initial and specific chunks)
        if chunk_data.startswith("RECV"):
            response_data_obj = self.response_queue.get(session_id)
            
            # Extract chunk number if specified
            requested_chunk = 0
            if chunk_data.startswith("RECV-"):
                try:
                    requested_chunk = int(chunk_data.split('-')[1])
                except:
                    requested_chunk = 0
            
            # Check if this is a chunked response
            if isinstance(response_data_obj, dict):
                # Multi-chunk response
                chunks = response_data_obj['chunks']
                total = response_data_obj['total']
                
                if requested_chunk < len(chunks):
                    response_data = f"{requested_chunk}:{total}:{chunks[requested_chunk]}"
                else:
                    response_data = None
            else:
                # Single chunk response (original behavior)
                response_data = response_data_obj
            
            response = self._create_dns_response(transaction_id, query_name, 
                                                query_type, response_data)
            self.sock.sendto(response, addr)
            
            # Only delete if it was a single-chunk response and this was the initial request
            if response_data and not isinstance(response_data_obj, dict) and chunk_data == "RECV":
                del self.response_queue[session_id]
            
            return
        
        # Store chunk
        self.sessions[session_id][chunk_num] = chunk_data
        self.session_metadata[session_id] = (total_chunks, time.time())
        
        # Try to assemble complete message
        complete_data = self._assemble_session_data(session_id)
        if complete_data:
            # Call user's callback
            if self.on_data_received:
                self.on_data_received(session_id, complete_data, addr)
            
            # Clean up session
            del self.sessions[session_id]
            del self.session_metadata[session_id]
        
        # Send response
        response = self._create_dns_response(transaction_id, query_name, query_type)
        self.sock.sendto(response, addr)
    
    def _decode_subdomain(self, query_name: str):
        """Decode data from subdomain."""
        try:
            if not query_name.endswith(self.domain):
                return None
            subdomain = query_name[:-len(self.domain)-1]
            if subdomain.startswith('recv-'):
                parts = subdomain.split('-')
                session_id = int(parts[1])
                # Check if requesting specific chunk: recv-SESSION-CHUNKNUM
                if len(parts) >= 3:
                    return (session_id, -1, -1, f"RECV-{parts[2]}")
                return (session_id, -1, -1, "RECV")
            parts = subdomain.split('-', 3)
            if len(parts) != 4:
                return None
            return int(parts[0]), int(parts[1]), int(parts[2]), parts[3]
        except:
            return None
    
    def _assemble_session_data(self, session_id: int) -> Optional[bytes]:
        """Assemble complete message from chunks."""
        if session_id not in self.session_metadata:
            return None
        total_chunks, _ = self.session_metadata[session_id]
        session_data = self.sessions[session_id]
        if len(session_data) != total_chunks:
            return None
        encoded_data = ''.join(session_data[i] for i in range(total_chunks))
        try:
            padding = (8 - len(encoded_data) % 8) % 8
            encoded_data += '=' * padding
            return base64.b32decode(encoded_data.upper())
        except:
            return None
    
    def _parse_dns_query(self, data: bytes):
        """Parse DNS query packet."""
        try:
            if len(data) < 12:
                return None
            transaction_id = struct.unpack('!H', data[0:2])[0]
            offset = 12
            labels = []
            while offset < len(data) and data[offset] != 0:
                length = data[offset]
                offset += 1
                labels.append(data[offset:offset+length].decode('ascii', errors='ignore'))
                offset += length
            query_name = '.'.join(labels).lower()
            offset += 1
            query_type = struct.unpack('!H', data[offset:offset+2])[0]
            return transaction_id, query_name, query_type
        except:
            return None
    
    def _create_dns_response(self, transaction_id: int, query_name: str, 
                            query_type: int, response_data: Optional[str] = None) -> bytes:
        """Create DNS response packet."""
        flags = 0x8180
        header = struct.pack('!HHHHHH', transaction_id, flags, 1, 1, 0, 0)
        
        question = b''
        for label in query_name.split('.'):
            if label:
                question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'
        question += struct.pack('!HH', query_type, 1)
        
        answer = b'\xc0\x0c'
        answer += struct.pack('!HHI', query_type, 1, 300)
        
        if query_type == 1:
            ip_bytes = socket.inet_aton("127.0.0.1")
            answer += struct.pack('!H', 4) + ip_bytes
        elif query_type == 16:
            if response_data:
                txt_data = response_data.encode('ascii')
                
                # TXT records can have multiple strings, each max 255 bytes
                # Split into chunks if needed
                chunks = []
                max_chunk = 255
                for i in range(0, len(txt_data), max_chunk):
                    chunk = txt_data[i:i+max_chunk]
                    chunks.append(struct.pack('B', len(chunk)) + chunk)
                
                txt_record = b''.join(chunks)
                answer += struct.pack('!H', len(txt_record)) + txt_record
            else:
                answer += struct.pack('!H', 1) + b'\x00'
        
        return header + question + answer

# === Module: firestoreRest ===
import requests
import uuid


def encode_fields(data):
    out = {}
    for k, v in data.items():
        if isinstance(v, bool):
            out[k] = {"booleanValue": v}
        elif isinstance(v, int):
            out[k] = {"integerValue": str(v)}
        elif isinstance(v, float):
            out[k] = {"doubleValue": v}
        elif isinstance(v, dict):
            out[k] = {"mapValue": {"fields": encode_fields(v)}}
        elif isinstance(v, list):
            out[k] = {
                "arrayValue": {
                    "values": [encode_fields({"_": i})["_"] for i in v]
                }
            }
        else:
            out[k] = {"stringValue": str(v)}
    return out


def decode_fields(fields):
    out = {}
    for k, v in fields.items():
        if "stringValue" in v:
            out[k] = v["stringValue"]
        elif "integerValue" in v:
            out[k] = int(v["integerValue"])
        elif "doubleValue" in v:
            out[k] = v["doubleValue"]
        elif "booleanValue" in v:
            out[k] = v["booleanValue"]
        elif "mapValue" in v:
            out[k] = decode_fields(v["mapValue"]["fields"])
        elif "arrayValue" in v:
            out[k] = [decode_fields({"_": i})["_"] for i in v["arrayValue"].get("values", [])]
    return out

class FirestoreREST:
    def __init__(self, project_id, database="(default)"):
        self.base = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/{database}/documents"

    def collection(self, name):
        return CollectionRef(self.base, name)


class CollectionRef:
    def __init__(self, base, name):
        self.url = f"{base}/{name}"

    def document(self, doc_id=None):
        if doc_id is None:
            doc_id = str(uuid.uuid4())
        return DocumentRef(f"{self.url}/{doc_id}", doc_id)

    def add(self, data):
        payload = {"fields": encode_fields(data)}
        r = requests.post(self.url, json=payload)
        r.raise_for_status()
        return r.json()

    def stream(self):
        r = requests.get(self.url)
        r.raise_for_status()
        docs = r.json().get("documents", [])
        for d in docs:
            yield {
                "id": d["name"].split("/")[-1],
                "data": decode_fields(d["fields"])
            }


class DocumentRef:
    def __init__(self, url, doc_id):
        self.url = url
        self.id = doc_id

    def set(self, data):
        payload = {"fields": encode_fields(data)}
        r = requests.patch(self.url, json=payload)
        r.raise_for_status()

    def update(self, data):
        self.set(data)

    def get(self):
        r = requests.get(self.url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return decode_fields(r.json()["fields"])

    def delete(self):
        r = requests.delete(self.url)
        r.raise_for_status()




# === Module: firebase_transport ===
"""
Firestore-based transport layer for client-server communication.

This module provides a socket-like abstraction over Firestore collections,
allowing clients and servers to communicate through document-based messaging.

Communication Model:
- Messages flow through two collections: 'server-channel' and 'client-channel'
- Each message is a document with: id, sender, timestamp, type, and data
- Listeners poll collections for new messages (configurable interval)
- Message IDs are generated server-side to ensure uniqueness
- Messages are cleaned up after being read (optional TTL support)
"""

import uuid
import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Callable, Optional, Dict, Any
import sys
import os
import random

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# MESSAGE MODEL
# ============================================================================

@dataclass
class Message:
    """
    Represents a single message transmitted through the transport.
    
    Attributes:
        id: Unique message identifier (generated server-side)
        sender: UUID of the sender (client_id or server_id)
        timestamp: ISO 8601 timestamp of message creation
        type: Message type ('request', 'response', 'heartbeat', 'ack')
        data: Arbitrary payload (dict)
        ttl_seconds: Time-to-live before message cleanup (None = no cleanup)
    """
    id: str
    sender: str
    timestamp: str
    type: str
    data: dict
    ttl_seconds: Optional[int] = None

    def to_firestore(self) -> dict:
        """Convert message to Firestore document format."""
        doc = asdict(self)
        # Remove None ttl to keep documents clean
        if doc['ttl_seconds'] is None:
            del doc['ttl_seconds']
        return doc

    @staticmethod
    def from_firestore(doc_id: str, fields: dict) -> 'Message':
        """Create Message from Firestore document."""
        return Message(
            id=doc_id,
            sender=fields.get('sender', ''),
            timestamp=fields.get('timestamp', ''),
            type=fields.get('type', ''),
            data=fields.get('data', {}),
            ttl_seconds=fields.get('ttl_seconds')
        )

    def is_expired(self) -> bool:
        """Check if message has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        msg_time = datetime.fromisoformat(self.timestamp)
        expiry_time = msg_time + timedelta(seconds=self.ttl_seconds)
        return datetime.now(msg_time.tzinfo) > expiry_time


# ============================================================================
# TRANSPORT LAYER
# ============================================================================

class FirebaseTransport:
    """
    Socket-like transport layer using Firestore as the communication medium.
    
    Usage:
        # Initialize
        transport = FirebaseTransport(project_id="my-project")
        
        # Set up message handler
        transport.on_message(lambda msg: print(msg['data']))
        
        # Start listening on a channel
        transport.start_listening('client-channel', poll_interval=0.5)
        
        # Send message to a channel
        transport.send('server-channel', {'command': 'ping'})
        
        # Start heartbeat to keep session alive
        transport.start_heartbeat()
    """

    def __init__(self, project_id: str, database: str = "(default)"):
        """
        Initialize the transport layer.
        
        Args:
            project_id: Firebase project ID
            database: Firestore database name (default is usually correct)
        """
        self.project_id = project_id
        self.client_id = str(uuid.uuid4())
        self.debug = False
        
        # Initialize Firestore REST client
        self.fs = FirestoreREST(project_id, database)
        
        # Message callback
        self._message_callback: Optional[Callable] = None
        
        # Listener state
        self._listener_running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._listener_lock = threading.Lock()
        self._last_seen_timestamps: Dict[str, float] = {}
        
        # Session management
        self._session_active = False
        self._heartbeat_running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._session_timeout = 60  # 60 seconds of inactivity = session expired
        self._last_activity_time = time.time()
        
        # Retry configuration
        self._max_retries = 3
        self._base_retry_delay = 0.5  # seconds
        
        # Message cleanup
        self._cleanup_running = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_interval = 30  # Check for expired messages every 30 seconds

    def on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback to handle incoming messages.
        
        Args:
            callback: Function that takes a message dict as argument
        """
        self._message_callback = callback

    def _retry_operation(self, operation, *args, operation_name: str = "operation"):
        """
        Execute an operation with exponential backoff retry.
        
        Args:
            operation: Callable to execute
            *args: Arguments to pass to operation
            operation_name: Name for debugging
            
        Returns:
            Result of operation or None if all retries exhausted
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self._max_retries):
            try:
                return operation(*args)
            except Exception as e:
                last_exception = e
                
                if attempt < self._max_retries - 1:
                    # Exponential backoff with jitter
                    delay = self._base_retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    if self.debug:
                        print(f"[TRANSPORT] Retry {attempt + 1}/{self._max_retries} for {operation_name} "
                              f"after {delay:.2f}s (Error: {str(e)[:50]})")
                    time.sleep(delay)
        
        error_msg = f"[TRANSPORT] Failed {operation_name} after {self._max_retries} attempts: {str(last_exception)}"
        if self.debug:
            print(error_msg)
        raise last_exception

    def start_listening(self, channel: str, poll_interval: float = 0.5) -> None:
        """
        Start listening for messages on a channel.
        
        Args:
            channel: Channel name ('server-channel' or 'client-channel')
            poll_interval: Time in seconds between polls for new messages
        """
        if self._listener_running:
            if self.debug:
                print(f"[TRANSPORT] Listener already running on {channel}")
            return

        self._listener_running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            args=(channel, poll_interval),
            daemon=True
        )
        self._listener_thread.start()
        if self.debug:
            print(f"[TRANSPORT] Started listening on '{channel}'")

    def stop_listening(self) -> None:
        """Stop the message listener."""
        self._listener_running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=5)
        if self.debug:
            print("[TRANSPORT] Stopped listening")

    def send(self, channel: str, data: dict, msg_type: str = 'request') -> str:
        """
        Send a message to a channel.
        
        Args:
            channel: Channel name ('server-channel' or 'client-channel')
            data: Message payload (dict)
            msg_type: Message type identifier
            
        Returns:
            Message ID of the sent message
            
        Raises:
            Exception: If message could not be sent after retries
        """
        msg = Message(
            id=str(uuid.uuid4()),
            sender=self.client_id,
            timestamp=datetime.now().isoformat(),
            type=msg_type,
            data=data,
            ttl_seconds=300  # 5 minute cleanup
        )

        def _do_send():
            collection = self.fs.collection(channel)
            doc_ref = collection.document(msg.id)
            doc_ref.set(msg.to_firestore())
            self._last_activity_time = time.time()
        
        try:
            self._retry_operation(_do_send, operation_name=f"send to '{channel}'")
            
            if self.debug:
                print(f"[TRANSPORT] Sent message {msg.id[:8]} to '{channel}'")
            
            return msg.id
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error sending message: {e}")
            raise

    def _listen_loop(self, channel: str, poll_interval: float) -> None:
        """
        Poll the channel for new messages (runs in background thread).
        
        Args:
            channel: Channel to listen on
            poll_interval: Polling interval in seconds
        """
        consecutive_errors = 0
        
        try:
            while self._listener_running:
                try:
                    def _do_stream():
                        collection = self.fs.collection(channel)
                        return list(collection.stream())
                    
                    docs = self._retry_operation(_do_stream, operation_name=f"stream from '{channel}'")
                    consecutive_errors = 0  # Reset on success
                    
                    for doc in docs:
                        doc_id = doc['id']
                        fields = doc['data']
                        
                        # Parse message
                        try:
                            msg = Message.from_firestore(doc_id, fields)
                            
                            # Skip if we've already processed this message
                            msg_timestamp = datetime.fromisoformat(msg.timestamp).timestamp()
                            if doc_id in self._last_seen_timestamps:
                                if self._last_seen_timestamps[doc_id] >= msg_timestamp:
                                    continue
                            
                            # Skip expired messages
                            if msg.is_expired():
                                continue
                            
                            # Update tracking and dispatch
                            self._last_seen_timestamps[doc_id] = msg_timestamp
                            self._last_activity_time = time.time()
                            
                            if self._message_callback:
                                callback_msg = {
                                    'id': msg.id,
                                    'sender': msg.sender,
                                    'timestamp': msg.timestamp,
                                    'type': msg.type,
                                    'data': msg.data
                                }
                                if self.debug:
                                    print(f"[TRANSPORT] Received message {msg.id[:8]} from '{channel}'")
                                
                                self._message_callback(callback_msg)
                        
                        except Exception as e:
                            if self.debug:
                                print(f"[TRANSPORT] Error parsing message {doc_id}: {e}")
                    
                    # Sleep before next poll
                    time.sleep(poll_interval)
                
                except Exception as e:
                    consecutive_errors += 1
                    if self.debug:
                        print(f"[TRANSPORT] Error in listener loop (consecutive: {consecutive_errors}): {e}")
                    
                    # Back off longer if consecutive errors
                    backoff = min(poll_interval * (consecutive_errors ** 2), 10.0)
                    time.sleep(backoff)
        
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Critical error in listener: {e}")
            self._listener_running = False

    def get_client_id(self) -> str:
        """Get this transport's unique client ID."""
        return self.client_id

    def start_heartbeat(self) -> None:
        """
        Start heartbeat to keep session alive.
        Periodically sends heartbeat messages to prevent session timeout.
        """
        if self._heartbeat_running:
            if self.debug:
                print("[TRANSPORT] Heartbeat already running")
            return
        
        self._session_active = True
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self._heartbeat_thread.start()
        if self.debug:
            print("[TRANSPORT] Started heartbeat")

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat."""
        self._heartbeat_running = False
        self._session_active = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        if self.debug:
            print("[TRANSPORT] Stopped heartbeat")

    def _heartbeat_loop(self) -> None:
        """Periodically update activity time to keep session alive."""
        try:
            while self._heartbeat_running:
                self._last_activity_time = time.time()
                time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error in heartbeat loop: {e}")
            self._heartbeat_running = False

    def _is_session_active(self, client_id: str = None) -> bool:
        """
        Check if a session is still active.
        
        Args:
            client_id: Session ID to check (defaults to self.client_id)
            
        Returns:
            True if session is active (hasn't timed out)
        """
        if client_id is None:
            client_id = self.client_id
        
        if client_id != self.client_id:
            # Can't track other sessions, assume active if heartbeat running
            return self._session_active
        
        if not self._session_active:
            return False
        
        elapsed = time.time() - self._last_activity_time
        is_active = elapsed < self._session_timeout
        
        if not is_active and self.debug:
            print(f"[TRANSPORT] Session expired after {elapsed:.1f}s of inactivity")
        
        return is_active

    def start_cleanup(self) -> None:
        """
        Start background cleanup thread to remove expired messages.
        This runs independently of the listener.
        """
        if self._cleanup_running:
            if self.debug:
                print("[TRANSPORT] Cleanup already running")
            return
        
        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
        if self.debug:
            print("[TRANSPORT] Started message cleanup")

    def stop_cleanup(self) -> None:
        """Stop the cleanup thread."""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        if self.debug:
            print("[TRANSPORT] Stopped message cleanup")

    def _cleanup_loop(self) -> None:
        """Periodically clean up expired messages from all channels."""
        channels = ['server-channel', 'client-channel']
        
        try:
            while self._cleanup_running:
                for channel in channels:
                    try:
                        self._cleanup_channel(channel)
                    except Exception as e:
                        if self.debug:
                            print(f"[TRANSPORT] Error cleaning {channel}: {e}")
                
                time.sleep(self._cleanup_interval)
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error in cleanup loop: {e}")
            self._cleanup_running = False

    def _cleanup_channel(self, channel: str) -> None:
        """Remove expired messages from a channel."""
        try:
            def _do_stream():
                collection = self.fs.collection(channel)
                return list(collection.stream())
            
            docs = self._retry_operation(_do_stream, operation_name=f"cleanup stream from '{channel}'")
            
            deleted_count = 0
            for doc in docs:
                doc_id = doc['id']
                fields = doc['data']
                
                try:
                    msg = Message.from_firestore(doc_id, fields)
                    if msg.is_expired():
                        def _do_delete():
                            collection = self.fs.collection(channel)
                            doc_ref = collection.document(doc_id)
                            doc_ref.delete()
                        
                        self._retry_operation(_do_delete, operation_name=f"delete from '{channel}'")
                        deleted_count += 1
                
                except Exception as e:
                    if self.debug:
                        print(f"[TRANSPORT] Error checking expiry of {doc_id}: {e}")
            
            if deleted_count > 0 and self.debug:
                print(f"[TRANSPORT] Cleaned up {deleted_count} expired messages from '{channel}'")
        
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error cleaning up channel {channel}: {e}")

    def __repr__(self) -> str:
        """String representation."""
        return f"FirebaseTransport(project_id={self.project_id}, client_id={self.client_id[:8]})"


# === Module: Install ===
import os
import ast
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

class PythonCompiler:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.files: Dict[str, str] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self.module_map: Dict[str, str] = {}  # Maps module names to their aliases
        
    def find_python_files(self, exclude_patterns: List[str] = None) -> List[Path]:
        """Find all Python files in the project."""
        if exclude_patterns is None:
            exclude_patterns = ['__pycache__', '.venv', 'venv', '.git', 'tests']
        
        # Get the name of this compiler script to exclude it
        compiler_script = Path(__file__).name
        exclude_patterns.append(compiler_script)
        
        py_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            for file in files:
                if file.endswith('.py') and file not in exclude_patterns:
                    py_files.append(Path(root) / file)
        
        return py_files
    
    def parse_imports(self, content: str, file_path: Path) -> Set[str]:
        """Extract local imports from a Python file."""
        local_imports = set()
        
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        local_imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:  # Absolute import
                        local_imports.add(node.module.split('.')[0])
        except SyntaxError:
            print(f"Warning: Syntax error in {file_path}")
        
        return local_imports
    
    def remove_imports(self, content: str, local_modules: Set[str]) -> Tuple[str, Dict[str, str]]:
        """Remove local imports from the code and return mapping of module aliases.
        
        Returns:
            Tuple of (cleaned_content, alias_map) where alias_map maps 'alias' -> 'module'
        """
        tree = ast.parse(content)
        
        # Track which lines to keep and build alias mapping
        lines_to_remove = set()
        alias_map = {}  # Maps alias -> original module name
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name in local_modules:
                        lines_to_remove.add(node.lineno)
                        # Track the alias used for this import
                        import_alias = alias.asname if alias.asname else alias.name
                        alias_map[import_alias] = alias.name
                        
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in local_modules:
                    lines_to_remove.add(node.lineno)
                    # Track aliases for 'from x import y as z'
                    for alias in node.names:
                        import_alias = alias.asname if alias.asname else alias.name
                        full_name = f"{node.module}.{alias.name}"
                        alias_map[import_alias] = full_name
        
        # Rebuild content without local imports
        content_lines = content.split('\n')
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result), alias_map
    
    def replace_module_references(self, content: str, alias_map: Dict[str, str]) -> str:
        """Replace module.ClassName references with just ClassName.
        
        For example, if we had 'import utils' and code uses 'utils.Helper',
        this will replace it with just 'Helper' since everything is in one namespace.
        """
        if not alias_map:
            return content
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_aliases = sorted(alias_map.keys(), key=len, reverse=True)
        
        for alias in sorted_aliases:
            # Replace module.ClassName with ClassName
            # Use word boundaries to avoid replacing parts of other identifiers
            pattern = r'\b' + re.escape(alias) + r'\.([a-zA-Z_][a-zA-Z0-9_]*)'
            content = re.sub(pattern, r'\1', content)
        
        return content
    
    def remove_main_blocks(self, content: str) -> str:
        """Remove if __name__ == '__main__' blocks and main() function definitions."""
        tree = ast.parse(content)
        content_lines = content.split('\n')
        lines_to_remove = set()
        
        for node in tree.body:
            # Remove if __name__ == '__main__' blocks
            if isinstance(node, ast.If):
                # Check if it's a __name__ == '__main__' check
                if self._is_main_guard(node.test):
                    # Mark all lines in this block for removal
                    start_line = node.lineno
                    end_line = node.end_lineno
                    for line_num in range(start_line, end_line + 1):
                        lines_to_remove.add(line_num)
            
            # Remove main() function definitions
            elif isinstance(node, ast.FunctionDef) and node.name == 'main':
                start_line = node.lineno
                end_line = node.end_lineno
                for line_num in range(start_line, end_line + 1):
                    lines_to_remove.add(line_num)
        
        # Rebuild content without main blocks
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result)
    
    def _is_main_guard(self, node) -> bool:
        """Check if an AST node is a __name__ == '__main__' check."""
        if isinstance(node, ast.Compare):
            # Check for __name__ == '__main__' or '__main__' == __name__
            if isinstance(node.left, ast.Name) and node.left.id == '__name__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value == '__main__':
                            return True
            elif isinstance(node.left, ast.Constant) and node.left.value == '__main__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Name) and comp.id == '__name__':
                            return True
        return False
        """Remove if __name__ == '__main__' blocks and main() function definitions."""
        tree = ast.parse(content)
        content_lines = content.split('\n')
        lines_to_remove = set()
        
        for node in tree.body:
            # Remove if __name__ == '__main__' blocks
            if isinstance(node, ast.If):
                # Check if it's a __name__ == '__main__' check
                if self._is_main_guard(node.test):
                    # Mark all lines in this block for removal
                    start_line = node.lineno
                    end_line = node.end_lineno
                    for line_num in range(start_line, end_line + 1):
                        lines_to_remove.add(line_num)
            
            # Remove main() function definitions
            elif isinstance(node, ast.FunctionDef) and node.name == 'main':
                start_line = node.lineno
                end_line = node.end_lineno
                for line_num in range(start_line, end_line + 1):
                    lines_to_remove.add(line_num)
        
        # Rebuild content without main blocks
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result)
    
    def _is_main_guard(self, node) -> bool:
        """Check if an AST node is a __name__ == '__main__' check."""
        if isinstance(node, ast.Compare):
            # Check for __name__ == '__main__' or '__main__' == __name__
            if isinstance(node.left, ast.Name) and node.left.id == '__name__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value == '__main__':
                            return True
            elif isinstance(node.left, ast.Constant) and node.left.value == '__main__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Name) and comp.id == '__name__':
                            return True
        return False
    
    def get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        relative = file_path.relative_to(self.project_root)
        parts = list(relative.parts[:-1]) + [relative.stem]
        if parts[-1] == '__init__':
            parts = parts[:-1]
        return '.'.join(parts) if parts else '__main__'
    
    def topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        """Sort modules by dependencies."""
        visited = set()
        result = []
        
        def visit(node):
            if node in visited:
                return
            visited.add(node)
            for dep in graph.get(node, set()):
                if dep in graph:  # Only visit if it's a local module
                    visit(dep)
            result.append(node)
        
        for node in graph:
            visit(node)
        
        return result
    
    def compile_project(self, exclude_patterns: List[str] = None, entry_point: str = None) -> str:
        """Compile all Python files into a single executable string.
        
        Args:
            exclude_patterns: List of directory/file patterns to exclude
            entry_point: Path to entry point file (e.g., 'main.py' or 'src/app.py')
                        Only this file will keep its main() and if __name__ == '__main__' blocks
        """
        py_files = self.find_python_files(exclude_patterns)
        
        # Determine the entry point module name
        entry_module = None
        if entry_point:
            entry_path = self.project_root / entry_point
            if entry_path.exists():
                entry_module = self.get_module_name(entry_path)
        
        # Read all files and build dependency graph
        module_contents = {}
        local_modules = set()
        
        for file_path in py_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            module_name = self.get_module_name(file_path)
            module_contents[module_name] = content
            local_modules.add(module_name)
            
            imports = self.parse_imports(content, file_path)
            self.dependencies[module_name] = imports
        
        # Sort modules by dependencies
        sorted_modules = self.topological_sort(self.dependencies)
        
        # Build combined code
        compiled_parts = []
        compiled_parts.append("# Compiled Python Project\n")
        compiled_parts.append("# This file was automatically generated\n\n")
        
        for module_name in sorted_modules:
            if module_name in module_contents:
                content = module_contents[module_name]
                
                # Remove local imports and get alias mapping
                cleaned_content, alias_map = self.remove_imports(content, local_modules)
                
                # Replace module.Class references with just Class
                cleaned_content = self.replace_module_references(cleaned_content, alias_map)
                
                # Remove main blocks unless this is the entry point
                if module_name != entry_module:
                    cleaned_content = self.remove_main_blocks(cleaned_content)
                
                compiled_parts.append(f"\n# === Module: {module_name} ===\n")
                compiled_parts.append(cleaned_content)
                compiled_parts.append("\n")
        
        return ''.join(compiled_parts)


# Example usage

# === Module: client.client ===
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
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
        
        self.tunnel = FirebaseTransport(project_id)
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
        self.tunnel.stop_heartbeat()
        self.tunnel.stop_cleanup()

# === Module: client.main ===
import time
import client as networkclient
import wordwrapper
import pythoncom
import pywintypes
import os

os.environ["FIREBASE_PROJECT_ID"] = "my-awesome-project-3c43d"



#server_ip ="51.175.238.64"
#server_port = 7777
#domain = "ordbokene.no"

word = wordwrapper.WordWrapper(visible=True)
client = networkclient.Client(debug=True)
word_is_open = True
stop = False

def reset(args: list[str]):
    if client.new_chat():
        word.write_start("word")
    else:
        word.write_start("sentence")


def test(args: list[str]):
    word.write_end("t")
    word.replace_text("::test::", "")

def stop_program(args: list[str]):
    global stop
    stop = True

commands = {
    "stop": stop_program,
    "new": reset,
    "reset": reset,
    "test": test
}
def find_prompt_replace(word: wordwrapper.WordWrapper):
    word.make_hidden_visible()
    prompt = word.get_block("--", "--")
    prompt = prompt if isinstance(prompt, str) else prompt[0]

    if prompt is None:
        return
    r = client.send_prompt(prompt)
    word.replace_blocks(f"--", "--", "") #Delete prompt from document
    word.replace_block(",,", ",,", r)

def handle_deactivated(word: wordwrapper.WordWrapper):
    global word_is_open

    try:
        word.make_hidden_visible()
        word.replace_blocks("", ";;;", "")

        prompt = word.get_block("--", "--") is not None
        command = word.get_block("::", "::")
        
        print(prompt, command)


        if prompt:
                find_prompt_replace(word)
        if command is not None:
            command = command if isinstance(command, str) else command[0]
            commands[command]([word.get_block(",,", ",,")])
            word.replace_blocks("::", "::", "")
        print("Flashing taskbar")
        word.flash_taskbar(1)
    except pywintypes.com_error as e:
        print("Word disconnected, waiting for reconnect...")
        print(e)
        word_is_open = False

def main():
    global word_is_open
    pythoncom.CoInitialize()
    
    try:
        word.use_active_doc()
    except Exception:
        word.open_new_doc()

    #Test dns connection
    result = client.ack()
    if not result:
        raise Exception("Couldn't connect to server.")
    print("Connection successful")
    if not client.new_chat():
        print("Could not create new chat on server. Answers may be off.")
    print("Ready")

    res_text = "word\r\n" if result else "sentence\r\n"
    word.write_start(res_text)

    word.on_word_deactivated = handle_deactivated

    while not stop:
        while word_is_open:
            #Main loop
            if stop:
                break
            pythoncom.PumpWaitingMessages()

        #If execution reaches here, word got disconnected
        while True:
            if stop:
                break
            time.sleep(1)
            if word.try_reconnect():
                print("Word reconnected")
                word.write_start(res_text)
                word_is_open = True
                break
            print("Failed to reconnect")

if __name__ == "__main__":
    main()

# === Module: client.wordwrapper ===
import win32com.client as win32
import pythoncom
import win32gui
import win32process
import win32con
import win32api
import ctypes
from ctypes import wintypes, Structure
from ctypes import windll, CFUNCTYPE, c_int, c_void_p, POINTER, c_uint, c_bool


class FLASHWINFO(Structure):
    """Structure for FlashWindowEx API."""
    _fields_ = [("cbSize", c_uint),
                ("hwnd", c_void_p),
                ("dwFlags", c_uint),
                ("uCount", c_uint),
                ("dwTimeout", c_uint)]


# Flash window flags
FLASHW_STOP = 0
FLASHW_CAPTION = 1
FLASHW_TRAY = 2
FLASHW_ALL = 3
FLASHW_TIMER = 4
FLASHW_TIMERNOFG = 12


class WordWrapper:
    def __init__(self, visible=False):
        pythoncom.CoInitialize()

        try:
            self.word = win32.GetActiveObject("Word.Application")
        except:
            try:
                self.word = win32.gencache.EnsureDispatch("Word.Application")
            except:
                raise Exception("Could not start or connect to Word application. Is word installed?")

        self.word.Visible = visible
        self.doc = None

        # event callbacks
        self.on_word_activated = None
        self.on_word_deactivated = None

        self._last_active_was_word = False

        # start listening to window focus changes
        self._start_focus_hook()

    def _is_word_window(self, hwnd):
        """Check if the foreground window belongs to WINWORD.EXE."""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            return "WINWORD.EXE" in exe_path.upper()
        except:
            return False

    def _start_focus_hook(self):
        """Hooks foreground window change."""
        WinEventProcType = CFUNCTYPE(
            None, c_void_p, c_int, c_void_p, c_int, c_int, c_int, c_int
        )

        def callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            is_word = self._is_word_window(hwnd)

            # Word just became active
            if is_word and not self._last_active_was_word:
                self._last_active_was_word = True
                if self.on_word_activated:
                    self.on_word_activated(self)

            # Word just got unfocused
            if not is_word and self._last_active_was_word:
                self._last_active_was_word = False
                if self.on_word_deactivated:
                    self.on_word_deactivated(self)

        self._win_event_proc = WinEventProcType(callback)

        windll.user32.SetWinEventHook(
            win32con.EVENT_SYSTEM_FOREGROUND,
            win32con.EVENT_SYSTEM_FOREGROUND,
            0,
            self._win_event_proc,
            0,
            0,
            win32con.WINEVENT_OUTOFCONTEXT
        )

    def try_reconnect(self):
        try:
            self.word = win32.GetActiveObject("Word.Application")
            self.use_active_doc()
            return True
        except:
            return False   

    def get_text(self, start: int = None, end: int = None) -> str:
        """Get text from the document or range."""
        if not self.doc:
            raise Exception("No document loaded bro.")

        if start is None or end is None:
            rng = self.doc.Content
        else:
            rng = self.doc.Range(start, end)

        return rng.Text

    def list_open_docs(self):
        docs = []
        for i in range(1, self.word.Documents.Count + 1):
            docs.append(self.word.Documents.Item(i).FullName)
        return docs

    def use_active_doc(self):
        """Use the currently active Word document."""
        if self.word.Documents.Count == 0:
            raise Exception("No documents are open in Word, bro.")
        self.doc = self.word.ActiveDocument
        return self.doc

    def open_doc(self, path):
        """Open a document (or attach if already open)."""
        for i in range(1, self.word.Documents.Count + 1):
            doc = self.word.Documents.Item(i)
            if doc.FullName.lower() == path.lower():
                self.doc = doc
                return self.doc

        self.doc = self.word.Documents.Open(path)
        return self.doc
    
    def open_new_doc(self):
        """
        Creates a new blank Word document and sets it as the active doc.
        """
        self.doc = self.word.Documents.Add()
        return self.doc

    def write_end(self, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range()
        rng.Font.Hidden = False
        rng.InsertAfter(text)

    def write_start(self, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(0, 0)
        rng.Font.Hidden = False
        rng.InsertBefore(text)

    def insert_at(self, start, end, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(start, end)
        rng.Font.Hidden = False
        rng.Text = text

    def replace_text(self, old, new):
        """
        Replaces all occurrences of old text with new text.
        Works with long replacement text by using Range.Text instead of Find.Replacement.
        """
        if not self.doc:
            raise Exception("No document loaded bro.")
        
        rng = self.doc.Content
        full_text = rng.Text
        
        # If old text not found, return early
        if old not in full_text:
            return False
        
        # Find and replace each occurrence
        while True:
            full_text = self.doc.Content.Text
            start_idx = full_text.find(old)
            
            if start_idx == -1:
                break
            
            # Replace using Range.Text for long text support
            replace_rng = self.doc.Range(start_idx, start_idx + len(old))
            replace_rng.Font.Hidden = False
            replace_rng.Text = new
        
        return True

    def replace_blocks(self, prefix="###", suffix="###", replacement="hello world"):
        """
        Replaces all occurrences of content wrapped in prefix...suffix.
        Works with large replacement text.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        replaced_count = 0
        
        while True:
            rng = self.doc.Content
            full_text = rng.Text

            start_idx = full_text.find(prefix)
            if start_idx == -1:
                break

            end_idx = full_text.find(suffix, start_idx + len(prefix))
            if end_idx == -1:
                break

            replace_rng = self.doc.Range(start_idx, end_idx + len(suffix))
            replace_rng.Font.Hidden = False
            replace_rng.Text = replacement
            replaced_count += 1

        return replaced_count

    def get_blocks(self, prefix="###", suffix="###", ):
        """
        Returns a list of all text content inside prefix...suffix blocks.
        Returns None list if none found.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text
        
        blocks = []
        search_pos = 0
        
        while True:
            start = full_text.find(prefix, search_pos)
            if start == -1:
                break
            
            start += len(prefix)
            end = full_text.find(suffix, start)
            if end == -1:
                break
            
            blocks.append(full_text[start:end])
            search_pos = end + len(suffix)

        if len(blocks) == 0:
            return None

        return blocks

    def replace_block(self, prefix="###", suffix="###", replacement="hello world"):
        """
        Replaces the first occurrence of content wrapped in prefix...suffix.
        Works with large replacement text.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text

        start_idx = full_text.find(prefix)
        if start_idx == -1:
            return False

        end_idx = full_text.find(suffix, start_idx + len(prefix))
        if end_idx == -1:
            return False

        replace_rng = self.doc.Range(start_idx, end_idx + len(suffix))
        replace_rng.Font.Hidden = False
        replace_rng.Text = replacement

        return True

    def get_block(self, prefix="###", suffix="###"):
        """
        Returns the text inside  the first occurance of prefix...suffix.
        Returns None if not found.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text

        start = full_text.find(prefix)
        if start == -1:
            return None

        start += len(prefix)
        end = full_text.find(suffix, start)
        if end == -1:
            return None

        return full_text[start:end]

    def make_hidden_visible(self):
        """Makes all hidden text in the document visible."""
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Content
        rng.Font.Hidden = False

    def save(self):
        if self.doc:
            self.doc.Save()

    def flash_taskbar(self, count=3, timeout=500):
        """
        Flashes the Word icon in the taskbar.
        
        Args:
            count: Number of times to flash (default: 3)
            timeout: Duration in milliseconds between flashes (default: 500)
        """
        try:
            hwnd = self.word.hwnd
            fwinfo = FLASHWINFO()
            fwinfo.cbSize = ctypes.sizeof(FLASHWINFO)
            fwinfo.hwnd = hwnd
            fwinfo.dwFlags = FLASHW_ALL
            fwinfo.uCount = count
            fwinfo.dwTimeout = timeout
            
            windll.user32.FlashWindowEx(ctypes.byref(fwinfo))
            return True
        except:
            return False

    def close_doc(self):
        if self.doc:
            self.doc.Close()
            self.doc = None

    def quit(self):
        self.word.Quit()
        self.word = None
