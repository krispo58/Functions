# Communication System Model - Visual Guide

## System Architecture

### High-Level View
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  APPLICATION LAYER                                              │
│  ┌──────────────────────┐           ┌──────────────────────┐   │
│  │   Client App         │           │   Server App         │   │
│  │ - send_prompt()      │           │ - process_commands() │   │
│  │ - ack()              │           │ - handle_requests()  │   │
│  └──────────────────────┘           └──────────────────────┘   │
│           ▲                                 ▲                   │
│           │                                 │                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ TRANSPORT LAYER (FirebaseTransport)                     │   │
│  │ - Socket-like API                                       │   │
│  │ - Retry logic (exponential backoff)                     │   │
│  │ - Session management (heartbeat)                        │   │
│  │ - Message cleanup (TTL enforcement)                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│           ▲                                 ▲                   │
│           │                                 │                   │
│  FIRESTORE REST API (requests/responses)                        │
│           ▲                                 ▲                   │
└─────────────────────────────────────────────────────────────────┘
           │                                 │
    ┌──────┴────────────────────────────────┴──────┐
    │                                               │
    ▼                                               ▼
┌─────────────────────────────────────────────────────────────┐
│             FIRESTORE DATABASE                              │
│                                                             │
│  ┌────────────────────┐       ┌────────────────────┐       │
│  │ server-channel     │       │ client-channel     │       │
│  │                    │       │                    │       │
│  │ Documents:         │       │ Documents:         │       │
│  │ - Requests from    │       │ - Responses from   │       │
│  │   client to server │       │   server to client │       │
│  │ - Auto-cleanup     │       │ - Auto-cleanup     │       │
│  │   every 5 min      │       │   every 5 min      │       │
│  └────────────────────┘       └────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Message Flow Diagram

```
TIME →

CLIENT                          FIRESTORE                       SERVER
  │                               │                               │
  │                               │                               │
  ├─ send('server-channel')      │                               │
  │  ┌─────────────────────────→ │                               │
  │  │ {                          │                               │
  │  │   "id": "msg-123",         │                               │
  │  │   "command": "PROMPT",     │                               │
  │  │   "args": [...],           │                               │
  │  │   "timestamp": "...",      │ ← listener polls             │
  │  │   "ttl_seconds": 300       │  ┌─ retrieves message       │
  │  │ }                          │  │                          │
  │  └────────────────────────────→ │ ┌────────────────────────→
  │                               │  │  Message parsed
  │                               │  │  Command executed
  │                               │  │
  │                               │  │  LLM processing...
  │                               │  │  (may take 10-60 seconds)
  │                               │  │
  ├─ heartbeat every 30s ────────→│  │ ┌─ send to 'client-channel'
  │  (keeps session alive)        │  │ │ {
  │                               │  │ │   "status": "success",
  │                               │  │ │   "data": "Response...",
  │                               │  │ │   "command": "PROMPT"
  │                               │  │ │ }
  │                               │  │ └─→
  │  ← listener polls ────────────→  │
  │  ┌─ response received            │
  │  │  - Callback triggered         │
  │  │  - Response processed         │
  └──→ (returns to caller)          │
       Response: "Response..."       │
                                     │ ← TTL countdown
                                     │   (300 seconds)
                                     │
                                     │
                                     │ ← Auto-cleanup removes
                                     │   expired documents
                                     │
```

## Two-Channel Communication Pattern

### Request Channel (server-channel)

```
CLIENT                          FIRESTORE              SERVER
  │                               │                      │
  ├─ Write Request ──────────→ document-1               │
  ├─ Write Request ──────────→ document-2        ┌──────┴─→ Read/Process
  ├─ Write Request ──────────→ document-3        │         │
  ├─ Write Request ──────────→ document-4        │         │
  │                               │              │         │
  │                               │              └─ Listen │
  │                               │                (poll)  │
  │                        ┌──────┴────┐                    │
  │                        │ Listener   │                    │
  │                        │ (0.5s)     │                    │
  │                        └────────────┘                    │
```

### Response Channel (client-channel)

```
CLIENT                    FIRESTORE              SERVER
  │                         │                       │
  │                         │                       │
  ├─ Listen ────────────────→ (poll every 0.5s)    │
  │                         │                       │
  │                         │ ← Write Response ── ┤
  │                         │    document-1        │
  │                         │                       │
  │ ← Response received     │                       │
  │   Callback triggered    │                       │
  │   Event signaled        │                       │
```

## Message Lifecycle

### Complete Timeline

```
TIME:    0s        1s        2s        3s     ...  290s      300s     302s
         │         │         │         │           │          │         │
Message  CREATED   STORED    RECEIVED  PROCESSED   ...       EXPIRED   CLEANED
Status:  ┌────────→ ├──────→ ├────────→ ├─────────→ ├────────→ ├───────→ ├──── 
         │         │         │         │           │         │         │
         └─ ID     └─        └─        └─ Callback │         └─ TTL    └─
           generated  Firestore   Client   handler  ... 290    expired   Delete
                      STORED      receives   runs      seconds  (default) from
                      with TTL    message             later     300s      DB

         TRANSPORT LAYER HANDLES ALL THIS AUTOMATICALLY
```

### Message States

```
                    ┌─────────────────┐
                    │    CREATED      │
                    │ (in memory)     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    SENT         │
                    │ (Firestore      │ ←─ Retry on failure
                    │  write)         │    (exp. backoff)
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    STORED       │
                    │ (in Firestore   │ ← TTL countdown
                    │  collection)    │   starts here
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
            ┌────────────────┐  ┌──────────────┐
            │   RECEIVED     │  │   EXPIRED    │
            │ (by listener)  │  │ (TTL limit   │
            │                │  │  reached)    │
            └────────┬───────┘  └──────┬───────┘
                     │                 │
                     ▼                 ▼
            ┌────────────────┐  ┌──────────────┐
            │ DELIVERED      │  │   DELETED    │
            │ (callback      │  │ (by cleanup  │
            │  called)       │  │  thread)     │
            └────────────────┘  └──────────────┘
```

## Session Management

### Heartbeat System

```
CLIENT ALIVE FOR 60 SECONDS WITH HEARTBEAT:

Activity Timeline:
┌─────────────────────────────────────────────────────────────────────┐
│ 0s: send_prompt()                                                   │
│     ↓                                                               │
│     last_activity = 0                                               │
│     Session: ACTIVE                                                 │
│                                                                     │
│ 5s: [long LLM processing...no new messages]                         │
│     Session: ACTIVE (elapsed: 5s < 60s timeout)                    │
│                                                                     │
│ 30s: heartbeat_loop() updates last_activity = 30                   │
│      ↓                                                              │
│      Session: ACTIVE (elapsed: 0s, reset)                          │
│                                                                     │
│ 35s: [still processing...]                                          │
│      Session: ACTIVE (elapsed: 5s < 60s timeout)                   │
│                                                                     │
│ 60s: heartbeat_loop() updates last_activity = 60                   │
│      ↓                                                              │
│      Session: ACTIVE (elapsed: 0s, reset)                          │
│                                                                     │
│ 65s: response finally arrives                                       │
│      Session: ACTIVE (elapsed: 5s < 60s timeout)                   │
│                                                                     │
│ Result: Session stayed alive the entire time!                      │
└─────────────────────────────────────────────────────────────────────┘

CLIENT WITHOUT HEARTBEAT (DIES):

┌─────────────────────────────────────────────────────────────────────┐
│ 0s: send_prompt()                                                   │
│     ↓                                                               │
│     last_activity = 0                                               │
│     Session: ACTIVE                                                 │
│                                                                     │
│ 30s: [still processing...]                                          │
│      Session: ACTIVE (elapsed: 30s < 60s timeout)                  │
│                                                                     │
│ 60s: [still processing...]                                          │
│      Session: ACTIVE (elapsed: 60s = 60s timeout) ← BOUNDARY!      │
│                                                                     │
│ 61s: [still processing...]                                          │
│      Session: EXPIRED (elapsed: 61s > 60s timeout)                 │
│      _is_session_active() returns False                             │
│      Server rejects further messages from this session!             │
│                                                                     │
│ Result: Session dies if response takes > 60s without heartbeat!    │
└─────────────────────────────────────────────────────────────────────┘
```

## Retry Logic with Exponential Backoff

```
OPERATION ATTEMPTS WITH EXPONENTIAL BACKOFF:

Attempt Sequence:
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│ Attempt 1: SEND                                                        │
│  │                                                                     │
│  ├─→ Success? Return immediately ✓                                    │
│  │                                                                     │
│  └─→ Fail? Compute delay...                                           │
│      base_delay = 0.5s                                                │
│      delay = 0.5 * (2^0) + jitter = ~0.5s                             │
│                                                                        │
│      ┌────────────────────────────────────┐                           │
│      │ WAIT 0.5 SECONDS                   │                           │
│      └────────────────────────────────────┘                           │
│                     ▼                                                  │
│ Attempt 2: RETRY                                                      │
│  │                                                                     │
│  ├─→ Success? Return immediately ✓                                    │
│  │                                                                     │
│  └─→ Fail? Compute delay...                                           │
│      delay = 0.5 * (2^1) + jitter = ~1.0s                             │
│                                                                        │
│      ┌────────────────────────────────────┐                           │
│      │ WAIT 1.0 SECOND                    │                           │
│      └────────────────────────────────────┘                           │
│                     ▼                                                  │
│ Attempt 3: RETRY                                                      │
│  │                                                                     │
│  ├─→ Success? Return immediately ✓                                    │
│  │                                                                     │
│  └─→ Fail? All retries exhausted                                      │
│      RAISE EXCEPTION                                                  │
│                                                                        │
│      Total time spent: 0.5 + 1.0 = 1.5 seconds                        │
│      Last attempt error is raised to caller                           │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

## Message Cleanup Process

```
AUTOMATIC CLEANUP EVERY 30 SECONDS:

Timeline:
T+0s:  Cleanup thread starts
       │
T+30s: ┌─→ Poll server-channel
       │   ├─ doc-1: Created at T+0s, TTL=300s, age=30s → KEEP
       │   ├─ doc-2: Created at T-330s, TTL=300s, age=330s → DELETE
       │   ├─ doc-3: Created at T+5s, TTL=300s, age=25s → KEEP
       │   └─ (Deleted 1 document)
       │
       └─→ Poll client-channel
           ├─ doc-A: Created at T-250s, TTL=300s, age=250s → KEEP
           ├─ doc-B: Created at T-310s, TTL=300s, age=310s → DELETE
           ├─ doc-C: Created at T+10s, TTL=300s, age=20s → KEEP
           └─ (Deleted 1 document)
       
       Total deleted: 2 documents
       Next cleanup: T+60s

T+60s: (repeat process)

Result: Database size stays bounded!
```

## Thread Synchronization

```
CONCURRENT THREADS IN TRANSPORT:

┌─────────────────────────────────────────────────────┐
│ MAIN THREAD                                         │
│ ├─ Initialize transport                             │
│ ├─ Call send() → creates message, writes to DB      │
│ └─ Call start_listening()                           │
│    ├─ Spawns LISTENER THREAD                        │
│    ├─ Returns immediately (non-blocking)            │
│    └─ MAIN continues...                             │
│                                                     │
│ ... MAIN can continue doing work ...                │
│     call send() more, close resources, etc.         │
│                                                     │
└─────────────────────────────────────────────────────┘
                    ▲
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
┌─────────────────┐    ┌──────────────────┐
│ LISTENER THREAD │    │ HEARTBEAT THREAD │
│                 │    │                  │
│ Loop forever:   │    │ Loop forever:    │
│ - Poll channel  │    │ - Update active  │
│ - Process msgs  │    │   time every 30s │
│ - Call callback │    │                  │
│ - Sleep 0.5s    │    │                  │
│ (daemon)        │    │ (daemon)         │
└─────────────────┘    └──────────────────┘
                       ▲
                       │
                   ┌───┘
                   │
           ┌───────┴────────┐
           │                │
           ▼                ▼
    ┌──────────────┐ ┌─────────────────┐
    │ CLEANUP      │ │ FIRESTORE REST  │
    │ THREAD       │ │ (synchronous,   │
    │              │ │  called from    │
    │ Loop every   │ │  threads)       │
    │ 30s:         │ │                 │
    │ - Query each │ │ Thread-safe?    │
    │   collection │ │ Using requests  │
    │ - Delete exp │ │ library which   │
    │   messages   │ │ handles this    │
    │              │ │                 │
    └──────────────┘ └─────────────────┘

KEY: Messages and callbacks are passed between threads
     safely via thread events and queues.
```

## Data Model

### Message Document in Firestore

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "sender": "client-id-xyz",
  "timestamp": "2025-12-18T10:30:45.123456",
  "type": "request",
  "data": {
    "command": "PROMPT",
    "args": ["What is machine learning?"]
  },
  "ttl_seconds": 300
}
```

### Collection Structure

```
Firestore Database
└── server-channel (collection)
    ├── msg-001 (document)
    ├── msg-002 (document)
    └── msg-003 (document)
└── client-channel (collection)
    ├── msg-101 (document)
    ├── msg-102 (document)
    └── msg-103 (document)
```

---

**This visual model shows:**
1. How client-server communication flows through Firestore
2. Why two separate channels are used
3. How the transport handles retries, sessions, and cleanup
4. Thread management and synchronization
5. Complete message lifecycle
6. Performance considerations

**Key Takeaway:** The transport layer abstracts away all complexity, making Firestore communication feel like regular socket-based networking.
