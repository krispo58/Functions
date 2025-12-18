# Using the Test Suite - Practical Guide

## Quick Start (30 seconds)

```bash
cd c:\Users\kristoffer\Documents\Koding\Functions\Functions
python test_firebase_transport.py
```

**Expected:** All tests pass in ~4 seconds

---

## Common Usage Scenarios

### Scenario 1: Verify After Code Changes

**Situation:** You modified firebase_transport.py or client.py

**What to do:**
```bash
python test_firebase_transport.py
```

**If all pass:** ✅ Your changes are good!  
**If some fail:** ❌ You broke something - review the error

### Scenario 2: Debug Connection Issues

**Situation:** Client can't connect to server

**Step 1: Run tests**
```bash
python test_firebase_transport.py
```

**Step 2: Check specific areas**
- Tests 6-7: Heartbeat and retry logic
- Tests 9-10: Listener and cleanup threads
- Tests 3-4: Transport initialization

**Step 3: Enable debug mode**
```python
from firebase_transport import FirebaseTransport

transport = FirebaseTransport("your-project")
transport.debug = True  # <-- This line

transport.start_listening('channel')
# Now see detailed logging
```

### Scenario 3: Verify Installation

**Situation:** First time setting up the transport layer

**What to do:**
```bash
python test_firebase_transport.py
```

**All 43 tests pass?** ✅ Installation successful!  
**Some tests fail?** Check error messages for what's missing

### Scenario 4: Pre-Deployment Check

**Situation:** Before deploying to production

**What to do:**
```bash
python test_firebase_transport.py
```

**Result: All pass** ✅ Safe to deploy  
**Result: Some fail** ❌ Fix issues before deploying

### Scenario 5: Performance Baseline

**Situation:** Want to know baseline performance

**What to do:**
```bash
python test_firebase_transport.py
```

**Check:** Test 7 shows retry backoff timing
```
[TRANSPORT] Retry 1/3 for test failure after 0.51s
[TRANSPORT] Retry 2/3 for test failure after 1.02s
```

This shows exponential backoff is working correctly.

---

## Reading Test Output

### Successful Test Output

```
============================================================
TEST 1: Module Imports
============================================================

[PASS] firebase_transport module imported
[PASS] firestoreRest module imported
```

**What this means:** ✅ Modules are installed and importable

### Failed Test Output

```
[FAIL] firebase_transport module import
  Error: ModuleNotFoundError: No module named 'firebase_transport'
```

**What this means:** ❌ File not found or not in path  
**How to fix:** Make sure you're in the Functions directory

### Debug Output During Tests

```
[TRANSPORT] Started heartbeat
[PASS] Heartbeat start/run state works
[TRANSPORT] Stopped heartbeat
[PASS] Heartbeat stop works
```

**What this means:** ✅ Heartbeat thread lifecycle works correctly

### Retry Logic Output

```
[TRANSPORT] Retry 1/3 for test failure after 0.51s (Error: Test error)
[TRANSPORT] Retry 2/3 for test failure after 1.09s (Error: Test error)
[TRANSPORT] Failed test failure after 3 attempts: Test error
[PASS] Retry logic: retried 3 times before failing
```

**What this means:** ✅ Exponential backoff is working (0.5s → 1.0s delays)

---

## Troubleshooting with Tests

### Problem: "ModuleNotFoundError"

```
[FAIL] firebase_transport module import
  Error: ModuleNotFoundError: No module named 'firebase_transport'
```

**Causes:**
1. Not in Functions directory
2. firebase_transport.py doesn't exist
3. Filename has typo or wrong case

**Solution:**
```bash
# Make sure you're in the right directory
cd c:\Users\kristoffer\Documents\Koding\Functions\Functions

# Check files exist
dir firebase_transport.py
dir firestoreRest.py
dir test_firebase_transport.py

# Then run tests
python test_firebase_transport.py
```

### Problem: "Slow Tests"

```
Total Tests: 43
Passed: 43
Failed: 0
Pass Rate: 100.0%
```

**Timing:** Takes >10 seconds?

**Causes:**
1. Slow disk I/O
2. System under heavy load
3. Antivirus scanning files
4. Python startup overhead

**Solution:**
```bash
# Run again - second run usually faster
python test_firebase_transport.py

# Disable antivirus for test directory temporarily
# Or schedule tests during low-load times
```

### Problem: "Some Tests Fail"

```
✗ FAIL: Message model test
  Error: Deserialized ID mismatch
```

**What this means:** The Message class doesn't work as expected

**Debug steps:**
```python
# Manual test of Message class
from firebase_transport import Message
from datetime import datetime

msg = Message(
    id="test",
    sender="test",
    timestamp=datetime.now().isoformat(),
    type="test",
    data={},
)

# Try serialization
dict_form = msg.to_firestore()
print(dict_form)

# Try deserialization
reconstructed = Message.from_firestore("test", dict_form)
print(reconstructed.id == "test")  # Should be True
```

---

## Advanced Testing

### Running Specific Tests

To run just one test group:

```python
# In Python REPL or script
from test_firebase_transport import test_message_model

passed, total = test_message_model()
print(f"Message model: {passed}/{total} tests passed")
```

### Capturing Test Output

```bash
# Save to file
python test_firebase_transport.py > test_results.txt

# View results
type test_results.txt
```

### Continuous Testing (Watch Mode)

```bash
# Run tests every 2 seconds on file changes
# Requires watchdog package: pip install watchdog

while ($true) {
    cls
    python test_firebase_transport.py
    Start-Sleep -Seconds 2
}
```

### Integration with CI/CD

**GitHub Actions:**
```yaml
name: Test Firebase Transport

on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: python test_firebase_transport.py
```

**Exit code handling:**
```bash
python test_firebase_transport.py
if ($? -eq 0) {
    Write-Host "Tests passed!"
} else {
    Write-Host "Tests failed!"
    exit 1
}
```

---

## Interpreting Results

### 100% Pass Rate = All Good ✅

```
Total Tests: 43
Passed: 43
Failed: 0
Pass Rate: 100.0%

SUCCESS - ALL TESTS PASSED!
```

**What it means:**
- ✅ All core functionality works
- ✅ All methods exist and are callable
- ✅ Message model works correctly
- ✅ Thread management works
- ✅ Session management works
- ✅ Retry logic works
- ✅ Safe to use in production

### Some Tests Fail = Debug Needed ❌

```
Total Tests: 43
Passed: 40
Failed: 3
Pass Rate: 93.0%

FAILURE - SOME TESTS FAILED
```

**What it means:**
- ❌ Some functionality is broken
- ❌ Review the specific failures
- ❌ Don't use in production yet
- ❌ Fix issues before continuing

**Next steps:**
1. Find the failed test in output
2. Read the error message
3. Check the traceback
4. Fix the issue in source code
5. Run tests again

---

## Performance Expectations

### Normal Test Times

```
Test 1 (Imports) .......... <10ms
Test 2 (Message) ......... <20ms
Test 3 (Init) ............ <10ms
Test 4 (Methods) ......... <20ms
Test 5 (Callbacks) ....... <5ms
Test 6 (Session) ........ ~2000ms (heartbeat timing)
Test 7 (Retry) ......... ~1600ms (retry delays)
Test 8 (Client ID) ....... <5ms
Test 9 (Listener) ........ <20ms
Test 10 (Cleanup) ........ <20ms
Test 11 (String) ......... <5ms
                          ─────────
Total .................. ~3.7 seconds
```

### If Tests Take Too Long

**Normal:** 3-5 seconds  
**Slow:** 10-30 seconds  
**Very slow:** >30 seconds  

**Causes of slowness:**
1. Disk I/O delay
2. System resource contention
3. Antivirus scanning
4. Python first startup
5. Network timeouts (shouldn't happen in unit tests)

**Solution:**
- Run again (usually faster on second run)
- Close other applications
- Add more RAM to system
- Check disk health (free space)

---

## Best Practices

### 1. Always Run Before Deploying
```bash
python test_firebase_transport.py  # Check: All pass?
```

### 2. Run After Code Changes
```bash
# Edit firebase_transport.py
# Then test
python test_firebase_transport.py
```

### 3. Keep Debug Output
```bash
# Save output for documentation
python test_firebase_transport.py > deployment_test_log.txt
```

### 4. Run Periodically
```bash
# Add to weekly/daily checks
# Catch regressions early
python test_firebase_transport.py
```

### 5. Use in CI/CD Pipeline
```yaml
# Automate testing on every push
python test_firebase_transport.py
```

---

## When to Use Tests vs. Manual Testing

### Use Automated Tests For:
✅ Rapid validation (< 5 seconds)  
✅ Checking all functionality at once  
✅ Pre-deployment validation  
✅ Regression detection  
✅ CI/CD pipelines  
✅ Routine checks  

### Use Manual Testing For:
✅ End-to-end scenarios  
✅ Firestore integration (requires credentials)  
✅ Network communication  
✅ Performance benchmarking  
✅ Production behavior  

---

## Getting Help

### Tests Fail - Check These Files

1. **Error in imports?** → [QUICKSTART.md](QUICKSTART.md)
2. **Method doesn't exist?** → [README.md](README.md)
3. **Want architecture understanding?** → [TRANSPORT_MODEL.md](TRANSPORT_MODEL.md)
4. **Want test details?** → [TEST_README.md](TEST_README.md)
5. **Need more info?** → [INDEX.md](INDEX.md)

### Common Questions

**Q: Why do tests take 3 seconds?**  
A: Tests 6 and 7 have intentional delays (heartbeat timing, retry backoff).

**Q: Can I run just one test?**  
A: Yes - manually import the test function and call it.

**Q: What if Firestore isn't set up?**  
A: Tests still pass - they only test core logic, not Firestore.

**Q: How do I add more tests?**  
A: See [TEST_README.md - Test Maintenance](TEST_README.md#test-maintenance)

---

## Summary

The test suite provides:

✅ **Quick validation** - Run in 4 seconds  
✅ **Complete coverage** - 43 tests  
✅ **Clear feedback** - Pass/fail for each test  
✅ **Debug output** - See what's happening  
✅ **Production ready** - CI/CD compatible  

**Use it often. Use it before deploying. Use it to debug issues.**

---

**Ready to test?**
```bash
python test_firebase_transport.py
```

**Expected:** All 43 tests pass ✅
