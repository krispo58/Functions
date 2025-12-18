# Firebase Firestore Transport Communication Model

## Overview

This document describes the **FirebaseTransport** communication layer—a socket-like abstraction that enables client-server communication through Firestore collections. The transport handles all Firebase/Firestore complexity, allowing applications to use familiar messaging patterns.

## Architecture

### Two-Channel Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Firestore Database                        │
├──────────────────────┬──────────────────────┬────────────────┤
│  server-channel      │  client-channel      │  (future use)  │
│  (requests)          │  (responses)         │                │
└──────────────────────┴──────────────────────┴────────────────┘
         ▲                      ▲
         │                      │
    ┌────┴────────────┐  ┌──────┴──────────┐
    │                 │  │                 │
    │    CLIENT       │  │     SERVER      │
    │  (Sender)       │  │   (Receiver)    │
    │                 │  │                 │
    └────┬────────────┘  └──────┬──────────┘
         │                      │
         └──────────────────────┘
         Client writes requests → Server-channel
         Server reads requests ← Server-channel
         Server writes responses → Client-channel
         Client reads responses ← Client-channel
```

### Message Flow

1. **Client sends request** to `server-channel`
   - Message contains: command, args, unique ID, sender ID, timestamp
   - TTL set (5 minutes by default) for automatic cleanup

2. **Server polls** `server-channel`
   - Listener thread continuously polls at configurable interval (0.5s default)
   - Processes new messages via callback function

3. **Server sends response** to `client-channel`
   - Response contains: status, data or error, command reference

4. **Client polls** `client-channel`
   - Receives response and triggers callback
   - Matches response to original request

## Message Model

### Message Structure

```python
@dataclass
class Message:
    id: str                          # Unique message ID (UUID)
    sender: str                      # Sender's client ID (UUID)
    timestamp: str                   # ISO 8601 creation time
    type: str                        # 'request', 'response', 'heartbeat'
    data: dict                       # Message payload
    ttl_seconds: Optional[int]       # Cleanup timeout (default: 300s)
```

### Message Lifecycle

```
Created (ttl_seconds set)
         ↓
    Active (TTL countdown)
         ↓
    Expired → Cleanup Thread Removes
         ↓
    Deleted from Firestore
```

## Communication Protocol

### Request Format

```python
# Client sends to server-channel
request = {
    "command": "PROMPT",
    "args": ["What is AI?"]
}
```

### Response Format

```python
# Server sends to client-channel
response = {
    "status": "success",  # or "error"
    "data": "AI is...",   # result if success
    "error": None,        # error message if failed
    "command": "PROMPT"   # echoed from request
}
```

## Core Components

### FirebaseTransport Class

**Initialization:**
```python
transport = FirebaseTransport(
    project_id="your-firebase-project-id",
    database="(default)"  # Firestore database name
)
```

**Public API:**

| Method | Purpose |
|--------|---------|
| `send(channel, data, msg_type)` | Send message to channel, returns message ID |
| `on_message(callback)` | Register handler for incoming messages |
| `start_listening(channel, poll_interval)` | Begin polling a channel |
| `stop_listening()` | Stop listener thread |
| `start_heartbeat()` | Begin session keepalive |
| `stop_heartbeat()` | Stop heartbeat |
| `start_cleanup()` | Begin expired message cleanup |
| `stop_cleanup()` | Stop cleanup thread |
| `get_client_id()` | Get this transport's unique ID |

**Session Management:**
```python
# Keep session alive (prevents timeout)
transport._is_session_active(client_id)
```

**Error Handling:**
- Exponential backoff retry with jitter (configurable: `_max_retries`, `_base_retry_delay`)
- Graceful degradation on Firestore API failures
- Consecutive error tracking with adaptive backoff

## Usage Patterns

### Server Setup

```python
from server.server import Server

# Initialize server
server = Server(project_id="your-project", debug=True)

# Start listening
server.start()  # Blocking call, handles requests until Ctrl+C
```

The server automatically:
- Listens on `server-channel` for requests
- Registers handlers for commands (PROMPT, ACK, NEW)
- Sends responses to `client-channel`
- Maintains heartbeat to keep session alive
- Cleans up expired messages

### Client Setup

```python
from client.client import Client

# Initialize client
client = Client(project_id="your-project")

# Send request and wait for response
response = client.send_prompt("Write a poem about networking")

# Test connection
if client.ack():
    print("Server is responding")

# Cleanup
client.close()
```

The client automatically:
- Listens on `client-channel` for responses
- Waits with timeout for each response
- Handles request/response matching via events
- Maintains heartbeat
- Cleans up resources on close()

## Session Management

**Heartbeat System:**
- Runs independently, updates `_last_activity_time` every 30 seconds
- Prevents session timeout (default: 60 seconds of inactivity)
- Server and client both run heartbeat to stay alive

**Session Timeout:**
- Default: 60 seconds of inactivity
- Configurable via `_session_timeout` attribute
- Used by server to ignore stale client requests

**Example: Long-Running Operation**
```python
# Server needs 45+ seconds?
# Client heartbeat keeps session alive:
client.start_heartbeat()  # Resets activity timer every 30s
response = client.send_prompt("Process huge dataset")  # Can wait 45s
```

## Cleanup System

**Automatic Message Expiration:**
- Default TTL: 5 minutes (300 seconds)
- Configurable per message via `ttl_seconds` parameter
- Checked during listener polling

**Background Cleanup Thread:**
```python
transport.start_cleanup()  # Runs every 30 seconds
# Removes expired messages from both channels
transport.stop_cleanup()
```

**Prevents Database Bloat:**
- Without cleanup: messages accumulate indefinitely
- With cleanup: documents auto-removed when TTL expires
- Configurable cleanup interval: `_cleanup_interval`

## Error Handling & Resilience

### Retry Logic

```python
# Exponential backoff with jitter:
# Attempt 1: ~0.5s delay
# Attempt 2: ~1.0s delay
# Attempt 3: ~2.0s delay
# Raises exception after 3 failed attempts

transport.send('server-channel', {'cmd': 'test'})
# Automatically retries on Firestore API failures
```

### Debug Mode

```python
transport.debug = True  # Enable detailed logging
# Output:
# [TRANSPORT] Started listening on 'server-channel'
# [TRANSPORT] Sent message abc12345 to 'server-channel'
# [TRANSPORT] Received message def67890 from 'client-channel'
# [TRANSPORT] Cleaned up 3 expired messages from 'server-channel'
```

### Common Patterns

**Handling Timeouts:**
```python
response = client.send_prompt("Long task", timeout=60)
if response is None:
    print("Server did not respond in 60 seconds")
```

**Handling Errors:**
```python
try:
    transport.send('server-channel', data)
except Exception as e:
    print(f"Failed to send: {e}")
    # Retry or fallback
```

## Configuration Reference

### Transport-Level Settings

```python
transport = FirebaseTransport(project_id, database)

# Retry configuration
transport._max_retries = 3          # Number of retry attempts
transport._base_retry_delay = 0.5   # Base delay in seconds

# Session configuration
transport._session_timeout = 60     # Inactivity timeout in seconds

# Cleanup configuration
transport._cleanup_interval = 30    # Cleanup check interval in seconds

# Listener configuration
transport.start_listening(channel, poll_interval=0.5)  # Poll frequency
```

### Message Configuration

```python
# Set TTL when sending
transport.send('channel', data, ttl_seconds=600)  # 10 minute expiration
# Default: 300 seconds (5 minutes)
# None: no expiration (not recommended for production)
```

## Best Practices

1. **Always call cleanup:**
   ```python
   transport.start_cleanup()  # In server and client
   transport.stop_cleanup()   # On shutdown
   ```

2. **Keep heartbeat running:**
   ```python
   transport.start_heartbeat()  # Prevents session timeout
   transport.stop_heartbeat()   # On shutdown
   ```

3. **Set appropriate timeouts:**
   ```python
   # Fast commands: 5-10 seconds
   response = client._send_and_wait("ACK", timeout=5)
   
   # LLM prompts: 30-60+ seconds
   response = client._send_and_wait("PROMPT", timeout=60)
   ```

4. **Enable debug mode during development:**
   ```python
   transport.debug = True
   ```

5. **Handle exceptions gracefully:**
   ```python
   try:
       result = client.send_prompt(prompt)
   except Exception as e:
       print(f"Communication error: {e}")
   ```

## Performance Considerations

| Factor | Impact | Tuning |
|--------|--------|--------|
| `poll_interval` | Response latency vs API cost | Lower = faster, more reads |
| `ttl_seconds` | Database size | Lower = smaller DB, more cleanup ops |
| `_cleanup_interval` | Cleanup frequency | Lower = smaller DB, more overhead |
| `_max_retries` | Resilience | Higher = more resilient, slower failure |
| `_session_timeout` | Stale request rejection | Lower = stricter, may drop valid requests |

**Recommended for Production:**
- `poll_interval`: 0.5 - 1.0 seconds
- `ttl_seconds`: 300 - 600 seconds
- `_cleanup_interval`: 30 - 60 seconds
- `_max_retries`: 3
- `_session_timeout`: 60 - 120 seconds

## Troubleshooting

### No responses received from server

```python
# Check 1: Listener running?
transport._listener_running  # Should be True

# Check 2: Enable debug logging
transport.debug = True

# Check 3: Heartbeat active?
transport._heartbeat_running  # Should be True

# Check 4: Check Firestore for messages manually
```

### Frequent "operation failed" errors

```python
# Increase retry attempts
transport._max_retries = 5

# Increase base retry delay
transport._base_retry_delay = 1.0

# Check Firebase authentication and permissions
```

### Database growing too large

```python
# Ensure cleanup is running
transport.start_cleanup()

# Reduce TTL for messages
transport.send('channel', data, ttl_seconds=120)  # 2 minutes

# Increase cleanup frequency
transport._cleanup_interval = 10  # Every 10 seconds
```

## Example: Complete Application Flow

```python
#!/usr/bin/env python3
import os
from client.client import Client
from server.server import Server
import threading

# Start server in background thread
def run_server():
    server = Server(debug=True)
    server.start()

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Give server time to initialize
import time
time.sleep(1)

# Connect client
client = Client()

# Test connection
if client.ack():
    print("✓ Server responsive")

# Start new chat
if client.new_chat():
    print("✓ Chat session started")

# Send prompt
response = client.send_prompt("What is machine learning?")
print(f"LLM: {response}")

# Cleanup
client.close()
```

This ensures both client and server communicate reliably through Firestore without either knowing about Firebase internals.
