# Quick Start Guide - Firebase Firestore Transport

## 5-Minute Setup

### 1. Set Environment Variable
```bash
# Windows PowerShell
$env:FIREBASE_PROJECT_ID = "your-firebase-project-id"

# Or add to .env file / system environment
```

### 2. Start Server
```python
from server.server import Server

server = Server(debug=True)
server.start()  # Blocks until Ctrl+C
```

**Output:**
```
Starting Firebase Tunnel Server...
Server initialized with Firebase project: your-project
Server ID: abc12345...
Firebase Tunnel Server started.
Listening on 'server-channel'
Press Ctrl+C to stop
```

### 3. Start Client (in another terminal)
```python
from client.client import Client

client = Client()
print("Connected!")

# Test it
if client.ack():
    print("Server is alive ✓")

# Send request
response = client.send_prompt("Hello, server!")
print(response)

# Cleanup
client.close()
```

## File Reference

| File | Purpose |
|------|---------|
| `firebase_transport.py` | Core transport layer (socket-like abstraction) |
| `firestoreRest.py` | Low-level Firestore REST API wrapper |
| `client/client.py` | Client wrapper with request/response handling |
| `server/server.py` | Server wrapper with command dispatch |
| `TRANSPORT_MODEL.md` | Comprehensive documentation |

## Key Classes

### FirebaseTransport (Core)
- **What it does:** Handles all Firestore communication
- **When to use:** Direct access to transport layer
- **Key methods:** `send()`, `on_message()`, `start_listening()`, `start_heartbeat()`, `start_cleanup()`

### Client
- **What it does:** Wraps transport for client-side convenience
- **When to use:** Sending requests and waiting for responses
- **Key methods:** `send_prompt()`, `ack()`, `new_chat()`, `close()`

### Server
- **What it does:** Wraps transport for server-side convenience
- **When to use:** Receiving commands and sending responses
- **Key methods:** `start()` (blocks), custom command handlers

## Common Operations

### Send a message and wait for response
```python
client = Client()
response = client._send_and_wait("COMMAND", ["arg1", "arg2"], timeout=30)
print(response['data'])
```

### Add a new command handler (server-side)
```python
server = Server()

# Add to commands dict
server.commands['MYCMD'] = server._my_handler

# Define handler
def _my_handler(args):
    return f"Got: {args}"

server._my_handler = _my_handler
server.start()
```

### Enable debug logging
```python
transport.debug = True
# or
server.tunnel.debug = True
client.tunnel.debug = True
```

### Change polling frequency
```python
# Faster (more reads, lower latency)
transport.start_listening('channel', poll_interval=0.25)

# Slower (fewer reads, higher latency)
transport.start_listening('channel', poll_interval=1.0)
```

### Change message TTL
```python
# Long-lived messages (1 hour)
transport.send('channel', data, ttl_seconds=3600)

# Short-lived messages (1 minute)
transport.send('channel', data, ttl_seconds=60)
```

## Debugging

### Check if listener is running
```python
print(transport._listener_running)  # True/False
print(transport._heartbeat_running)  # True/False
print(transport._cleanup_running)    # True/False
```

### View pending activity
```python
print(f"Client ID: {transport.client_id}")
print(f"Last activity: {transport._last_activity_time}")
print(f"Session active: {transport._is_session_active()}")
```

### Monitor message processing
```python
transport.debug = True
# Now watch the console for detailed logging
```

## Troubleshooting Checklist

- [ ] `FIREBASE_PROJECT_ID` environment variable set?
- [ ] Server running and listening?
- [ ] Client can create Transport without errors?
- [ ] `debug=True` to see what's happening?
- [ ] Heartbeat running? (`start_heartbeat()`)
- [ ] Listener running? (`start_listening()`)
- [ ] Cleanup running? (`start_cleanup()`)
- [ ] Firestore console shows collections? (`server-channel`, `client-channel`)

## Architecture in One Diagram

```
Client                    Firestore                 Server
  │                           │                       │
  ├─ send('server-channel')──→ server-channel        │
  │   {command, args}          messages              │
  │                             │                    │
  │                             ├─ listener polls ───→
  │                             │   message parsed
  │                             │   command executed
  │                             │
  │   ← listener polls ──────── client-channel ←── send('client-channel')
  │   receives response         responses      {status, data}
  │
  └─ callback triggered
     response processed
```

## Expected Latency

- **ACK command:** 0.5 - 1.5 seconds
- **LLM prompt:** 10 - 60+ seconds (depends on LLM)
- **Network overhead:** ~0.2 - 0.5 seconds per direction

(All estimates assume polling interval of 0.5s and normal Firestore latency)

## Security Notes

⚠️ **Current Implementation:**
- No authentication/authorization in transport layer
- Relies on Firestore security rules to protect data
- Client ID is just a UUID (not cryptographically bound)

✓ **Recommendation:**
- Configure Firestore rules to require authentication
- Use Firebase Authentication for identity verification
- Validate sender IDs server-side

## Performance Tips

1. **Batch messages** - don't send 100 one-at-a-time, group them
2. **Tune poll_interval** - 0.5s is good default, adjust for your latency tolerance
3. **Monitor TTL** - shorter TTL = smaller DB, more cleanup overhead
4. **Enable cleanup** - prevents database bloat
5. **Use heartbeat** - keeps sessions alive during long operations

## Next Steps

1. Read [TRANSPORT_MODEL.md](TRANSPORT_MODEL.md) for comprehensive documentation
2. Look at [client/main.py](client/main.py) for client usage example
3. Look at [server/main.py](server/main.py) for server usage example
4. Check Firestore console for collections and documents
5. Add custom command handlers for your use case
