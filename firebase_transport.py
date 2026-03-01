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
- Adaptive polling reduces frequency when CPU usage is high
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

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import firestoreRest


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
        
        # CPU-aware adaptive polling
        self._adaptive_polling_enabled = True
        self._cpu_threshold_low = 50.0  # Below this: use base interval
        self._cpu_threshold_medium = 70.0  # Above this: slow down polling
        self._cpu_threshold_high = 85.0  # Above this: slow down significantly
        self._cpu_check_interval = 5.0  # Check CPU every 5 seconds
        self._last_cpu_check = 0.0
        self._current_cpu_usage = 0.0
        self._max_polling_slowdown = 10.0  # Maximum multiplier for poll interval

    def configure_adaptive_polling(
        self,
        enabled: bool = True,
        cpu_threshold_low: float = 50.0,
        cpu_threshold_medium: float = 70.0,
        cpu_threshold_high: float = 85.0,
        max_slowdown: float = 10.0
    ) -> None:
        """
        Configure CPU-aware adaptive polling behavior.
        
        Args:
            enabled: Enable/disable adaptive polling
            cpu_threshold_low: CPU % below which base interval is used
            cpu_threshold_medium: CPU % above which to start slowing down
            cpu_threshold_high: CPU % above which to slow down significantly
            max_slowdown: Maximum multiplier for poll interval (default 10x)
        """
        self._adaptive_polling_enabled = enabled
        self._cpu_threshold_low = cpu_threshold_low
        self._cpu_threshold_medium = cpu_threshold_medium
        self._cpu_threshold_high = cpu_threshold_high
        self._max_polling_slowdown = max_slowdown
        
        if self.debug:
            print(f"[TRANSPORT] Adaptive polling configured: enabled={enabled}, "
                  f"thresholds=[{cpu_threshold_low}, {cpu_threshold_medium}, {cpu_threshold_high}], "
                  f"max_slowdown={max_slowdown}x")

    def _get_cpu_usage(self) -> float:
        """
        Get current CPU usage percentage.
        
        Returns:
            CPU usage as percentage (0-100), or 0 if psutil not available
        """
        if not HAS_PSUTIL:
            return 0.0
        
        current_time = time.time()
        
        # Only check CPU at intervals to reduce overhead
        if current_time - self._last_cpu_check < self._cpu_check_interval:
            return self._current_cpu_usage
        
        try:
            # Get CPU usage with a short interval
            cpu_usage = psutil.cpu_percent(interval=0.1)
            self._current_cpu_usage = cpu_usage
            self._last_cpu_check = current_time
            return cpu_usage
        except Exception as e:
            if self.debug:
                print(f"[TRANSPORT] Error getting CPU usage: {e}")
            return 0.0

    def _calculate_adaptive_interval(self, base_interval: float) -> float:
        """
        Calculate adaptive polling interval based on CPU usage.
        
        Args:
            base_interval: Base polling interval in seconds
            
        Returns:
            Adjusted polling interval based on CPU load
        """
        if not self._adaptive_polling_enabled or not HAS_PSUTIL:
            return base_interval
        
        cpu_usage = self._get_cpu_usage()
        
        # No adjustment needed if CPU is low
        if cpu_usage < self._cpu_threshold_low:
            return base_interval
        
        # Calculate slowdown factor based on CPU usage
        if cpu_usage < self._cpu_threshold_medium:
            # Linear interpolation between 1x and 2x
            factor = 1.0 + (cpu_usage - self._cpu_threshold_low) / \
                     (self._cpu_threshold_medium - self._cpu_threshold_low)
        elif cpu_usage < self._cpu_threshold_high:
            # Linear interpolation between 2x and 5x
            factor = 2.0 + 3.0 * (cpu_usage - self._cpu_threshold_medium) / \
                     (self._cpu_threshold_high - self._cpu_threshold_medium)
        else:
            # High CPU: use exponential slowdown up to max
            excess = cpu_usage - self._cpu_threshold_high
            factor = min(5.0 + (excess / 5.0), self._max_polling_slowdown)
        
        adjusted_interval = base_interval * factor
        
        if self.debug and abs(adjusted_interval - base_interval) > 0.01:
            print(f"[TRANSPORT] CPU at {cpu_usage:.1f}% - adjusted interval: "
                  f"{base_interval:.2f}s → {adjusted_interval:.2f}s ({factor:.1f}x)")
        
        return adjusted_interval

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
            poll_interval: Base time in seconds between polls (adjusted by CPU usage)
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
            print(f"[TRANSPORT] Started listening on '{channel}' (base interval: {poll_interval}s)")

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
        Uses adaptive polling based on CPU usage.
        
        Args:
            channel: Channel to listen on
            poll_interval: Base polling interval in seconds (adjusted by CPU)
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
                                
                                # Automatically cleanup message after it's been received
                                try:
                                    def _do_delete():
                                        collection = self.fs.collection(channel)
                                        doc_ref = collection.document(doc_id)
                                        doc_ref.delete()
                                    
                                    self._retry_operation(_do_delete, operation_name=f"auto-delete from '{channel}'")
                                    if self.debug:
                                        print(f"[TRANSPORT] Auto-cleaned message {msg.id[:8]} from '{channel}'")
                                except Exception as delete_error:
                                    if self.debug:
                                        print(f"[TRANSPORT] Error auto-cleaning message {doc_id}: {delete_error}")
                        
                        except Exception as e:
                            if self.debug:
                                print(f"[TRANSPORT] Error parsing message {doc_id}: {e}")
                    
                    # Calculate adaptive sleep interval based on CPU usage
                    adaptive_interval = self._calculate_adaptive_interval(poll_interval)
                    time.sleep(adaptive_interval)
                
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

    def get_cpu_usage(self) -> float:
        """
        Get the current CPU usage percentage.
        
        Returns:
            CPU usage percentage (0-100), or 0 if psutil not available
        """
        return self._get_cpu_usage()

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
        status = "adaptive" if self._adaptive_polling_enabled and HAS_PSUTIL else "fixed"
        return f"FirebaseTransport(project_id={self.project_id}, client_id={self.client_id[:8]}, polling={status})"