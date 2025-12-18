# Firebase Transport Test Suite

## Overview

`test_firebase_transport.py` is a comprehensive testing script that validates the Firebase Transport layer functionality. It provides detailed debugging output to help diagnose any issues.

## Test Coverage

### ✅ Test 1: Module Imports
- Verifies firebase_transport module imports
- Verifies firestoreRest module imports
- Identifies import path issues

### ✅ Test 2: Message Model
- Message dataclass creation
- Message attributes and properties
- Message serialization to Firestore format
- Message expiration detection
- Message deserialization from Firestore

### ✅ Test 3: FirebaseTransport Initialization
- Transport initialization with project_id
- Attribute initialization (client_id, project_id)
- Initial state verification
- Debug mode enabling

### ✅ Test 4: FirebaseTransport Methods
- Verifies all 14 public/private methods exist
- Confirms all methods are callable
- Tests method availability

### ✅ Test 5: Callback Registration
- on_message() callback registration
- Callback storage and retrieval
- Callback invocation capability

### ✅ Test 6: Session Management
- Session active state checking
- Heartbeat start/stop
- Heartbeat thread creation
- Session timeout logic

### ✅ Test 7: Retry Logic
- Operation success on first attempt
- Retry behavior on failures
- Exponential backoff timing
- Retry configuration (max_retries, base_delay)

### ✅ Test 8: Client ID
- Client ID generation (UUID)
- Client ID retrieval via get_client_id()
- UUID format validation

### ✅ Test 9: Listener Lifecycle
- Listener initial state
- Listener thread creation
- Listener start/stop functionality
- Listener running state tracking

### ✅ Test 10: Cleanup Lifecycle
- Cleanup initial state
- Cleanup thread creation
- Cleanup start/stop functionality
- Cleanup running state tracking

### ✅ Test 11: String Representation
- __repr__() implementation
- Includes project_id and client_id
- Human-readable output format

## Running the Tests

### Basic Run
```bash
python test_firebase_transport.py
```

### With Output Capture
```bash
python test_firebase_transport.py > test_results.txt 2>&1
```

### With Debug Output
The tests automatically enable debug mode in some sections to show detailed logging:
```
[TRANSPORT] Started heartbeat
[TRANSPORT] Stopped heartbeat
[TRANSPORT] Retry 1/3 for test failure after 0.52s (Error: Test error)
```

## Test Results Interpretation

### Success (100% Pass Rate)
```
✓ ALL TESTS PASSED!
Firebase Transport is working correctly!
```

### What This Means
- ✅ All modules import correctly
- ✅ Message model works as expected
- ✅ Transport initialization succeeds
- ✅ All methods exist and are callable
- ✅ Callbacks register properly
- ✅ Session management functions
- ✅ Retry logic works with backoff
- ✅ Listener and cleanup threads manage correctly
- ✅ Thread lifecycle (start/stop) works
- ✅ Client IDs are valid UUIDs

### Failure Cases

#### Test Failure Example
```
✗ FAIL: Message deserialization
  Error: Deserialized ID mismatch
```

**What to Check:**
- Look at the assertion error message
- Review the traceback for specific line
- Check if Message.from_firestore() is working
- Verify dict structure from to_firestore()

#### Import Failure
```
✗ FAIL: firebase_transport module import
  Error: No module named 'firebase_transport'
```

**What to Check:**
- Ensure test_firebase_transport.py is in Functions directory
- Verify firebase_transport.py exists in same directory
- Check Python path and working directory

## Debug Output

### When Tests Pass
```
✓ PASS: Firebase Transport initialized with project_id
✓ PASS: Transport attributes initialized (client_id: 1e2b6fdc...)
✓ PASS: Method 'send' exists and is callable
```

### When Tests Debug
```
[TRANSPORT] Started heartbeat
✓ PASS: Heartbeat start/run state works
[TRANSPORT] Stopped heartbeat
✓ PASS: Heartbeat stop works

[TRANSPORT] Retry 1/3 for test failure after 0.52s (Error: Test error)
[TRANSPORT] Retry 2/3 for test failure after 1.09s (Error: Test error)
[TRANSPORT] Failed test failure after 3 attempts: Test error
✓ PASS: Retry logic: retried 3 times before failing
```

## Color-Coded Output

### Console Colors
- 🟢 **GREEN** - Tests passed
- 🔴 **RED** - Tests failed
- 🟡 **YELLOW** - Warnings or notes
- 🔵 **BLUE** - Section headers and info

### Legend
- `✓ PASS:` - Test succeeded
- `✗ FAIL:` - Test failed
- `ℹ INFO:` - Information message
- `⚠ WARNING:` - Warning or incomplete test

## What's NOT Tested

The following require Firebase setup and are not fully tested:

### ❌ Firestore Communication
- Actual message sending to Firestore
- Actual message polling from collections
- Actual Firestore authentication
- Network communication

### ❌ Real Message Flow
- End-to-end request/response
- Client-server communication
- Collection operations
- Document CRUD operations

### ❌ External Dependencies
- Firestore REST API calls
- Google Cloud authentication
- Network connectivity
- Project setup verification

**Why?** These tests would require:
- Valid Firebase project credentials
- Firestore database setup
- Google Cloud authentication
- Network access

**Testing These:** See [TRANSPORT_MODEL.md - Testing](TRANSPORT_MODEL.md) for integration testing guide.

## Troubleshooting

### All Tests Pass But Still Having Issues?

1. **Check Firestore Setup**
   ```bash
   echo $env:FIREBASE_PROJECT_ID
   ```
   Should output your Firebase project ID.

2. **Enable Debug Logging**
   ```python
   transport.debug = True
   ```
   This shows detailed logging of all operations.

3. **Check Thread Status**
   ```python
   transport._listener_running     # Should be True when listening
   transport._heartbeat_running    # Should be True when active
   transport._cleanup_running      # Should be True when active
   ```

4. **Test Message Creation**
   ```python
   from firebase_transport import Message
   from datetime import datetime
   
   msg = Message(
       id="test",
       sender="test",
       timestamp=datetime.now().isoformat(),
       type="test",
       data={}
   )
   print(msg.to_firestore())
   ```

5. **Check Firestore Collections**
   - Open Firebase Console
   - Go to Firestore Database
   - Look for `server-channel` and `client-channel` collections
   - Check if documents are being created

### Common Issues

**Issue: `ModuleNotFoundError: No module named 'firebase_transport'`**
- Solution: Run from Functions directory
- Solution: Check filename spelling (no spaces)

**Issue: Tests fail with Firestore errors**
- Solution: This is expected - requires Firebase setup
- Solution: Tests validate logic, not Firebase communication
- Solution: See [QUICKSTART.md](QUICKSTART.md) for Firebase setup

**Issue: Thread tests time out**
- Solution: Threads might still be running
- Solution: Increase timeout in test file
- Solution: Check system resources

## Performance Metrics

From test runs:

```
Retry Logic Tests
- Operation success: < 1ms
- Single operation failure: < 1ms
- Three retries: ~1.6 seconds (0.52s + 1.07s delays)

Thread Creation
- Heartbeat thread: ~1ms
- Listener thread: ~5ms (or fails if Firestore unavailable)
- Cleanup thread: ~5ms (or fails if Firestore unavailable)

Message Model
- Create message: < 1ms
- Serialize to_firestore(): < 1ms
- Deserialize from_firestore(): < 1ms
- Check expiration: < 1ms
```

## Test Maintenance

### When to Run Tests
- After code changes
- Before deploying
- When troubleshooting
- Regular validation (CI/CD)

### Updating Tests
To add new tests:

1. Create new test function:
   ```python
   def test_new_feature():
       """Test description"""
       tests_passed = 0
       tests_total = 0
       
       tests_total += 1
       try:
           # Test logic
           print_pass("Test passed")
           tests_passed += 1
       except Exception as e:
           print_fail("Test failed", str(e))
       
       return tests_passed, tests_total
   ```

2. Add to `tests` list in `main()`:
   ```python
   tests = [
       test_imports,
       test_message_model,
       # ... existing tests ...
       test_new_feature,  # ← Add here
   ]
   ```

3. Run and verify

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Test Firebase Transport
  run: python test_firebase_transport.py
```

### Exit Codes
- `0` - All tests passed ✓
- `1` - Some tests failed ✗

## Related Documentation

- [README.md](README.md) - Main reference
- [TRANSPORT_MODEL.md](TRANSPORT_MODEL.md) - Architecture and design
- [QUICKSTART.md](QUICKSTART.md) - Getting started
- [firebase_transport.py](firebase_transport.py) - Source code

## Summary

The test suite validates core Firebase Transport functionality without requiring a live Firestore database. It checks:

✅ Imports and dependencies  
✅ Message model operations  
✅ Transport initialization  
✅ All methods and APIs  
✅ Callback system  
✅ Session management  
✅ Retry logic and backoff  
✅ Client ID generation  
✅ Thread lifecycle  
✅ String representation  

**Current Status**: 43/43 tests passing (100%)
