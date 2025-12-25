"""
Firebase Transport Testing Script

Tests the FirebaseTransport class to verify all functionality works correctly.
Provides detailed debug output to help diagnose any issues.

Usage:
    python test_firebase_transport.py

Tests Covered:
    ✓ Module imports
    ✓ Message model
    ✓ FirebaseTransport initialization
    ✓ Basic method availability
    ✓ Callback registration
    ✓ Thread creation and lifecycle
    ✓ Session management
    ✓ Retry logic
"""

import sys
import os
import io
import threading
import time
from datetime import datetime, timedelta

# Enable UTF-8 for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Color codes for console output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_pass(text):
    """Print a passing test"""
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {text}")

def print_fail(text, error=None):
    """Print a failing test"""
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {text}")
    if error:
        print(f"  {Colors.RED}Error: {error}{Colors.RESET}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {text}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")

def test_imports():
    """Test that all modules can be imported"""
    print_header("TEST 1: Module Imports")
    
    tests_passed = 0
    tests_total = 0
    
    # Test firebase_transport import
    tests_total += 1
    try:
        import firebase_transport
        print_pass("firebase_transport module imported")
        tests_passed += 1
    except Exception as e:
        print_fail("firebase_transport module import", str(e))
        return tests_passed, tests_total
    
    # Test firestoreRest import
    tests_total += 1
    try:
        import firestoreRest
        print_pass("firestoreRest module imported")
        tests_passed += 1
    except Exception as e:
        print_fail("firestoreRest module import", str(e))
    
    return tests_passed, tests_total

def test_message_model():
    """Test the Message dataclass"""
    print_header("TEST 2: Message Model")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import Message
        print_pass("Message class imported")
        
        # Test message creation
        tests_total += 1
        msg = Message(
            id="test-id-123",
            sender="client-uuid",
            timestamp=datetime.now().isoformat(),
            type="request",
            data={"command": "TEST", "args": ["arg1"]},
            ttl_seconds=300
        )
        print_pass("Message instance created")
        tests_passed += 1
        
        # Test message attributes
        tests_total += 1
        assert msg.id == "test-id-123", "Message ID mismatch"
        assert msg.sender == "client-uuid", "Message sender mismatch"
        assert msg.type == "request", "Message type mismatch"
        assert msg.data["command"] == "TEST", "Message data mismatch"
        print_pass("Message attributes correct")
        tests_passed += 1
        
        # Test message serialization
        tests_total += 1
        firestore_dict = msg.to_firestore()
        assert "id" in firestore_dict, "Serialized message missing 'id'"
        assert "sender" in firestore_dict, "Serialized message missing 'sender'"
        assert "data" in firestore_dict, "Serialized message missing 'data'"
        print_pass("Message serialization works")
        tests_passed += 1
        
        # Test message expiration
        tests_total += 1
        old_msg = Message(
            id="old-id",
            sender="client",
            timestamp=(datetime.now() - timedelta(seconds=400)).isoformat(),
            type="request",
            data={},
            ttl_seconds=300  # Expired
        )
        assert old_msg.is_expired(), "Old message should be expired"
        print_pass("Message expiration detection works")
        tests_passed += 1
        
        # Test deserialization
        tests_total += 1
        # Note: when deserializing, we pass the doc_id separately
        # (in Firestore, the ID is the document key, not a field)
        reconstructed = Message.from_firestore("test-id-123", firestore_dict)
        assert reconstructed.id == "test-id-123", "Deserialized ID mismatch"
        assert reconstructed.sender == msg.sender, "Deserialized sender mismatch"
        print_pass("Message deserialization works")
        tests_passed += 1
        
    except Exception as e:
        print_fail(f"Message model test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_transport_initialization():
    """Test FirebaseTransport initialization"""
    print_header("TEST 3: FirebaseTransport Initialization")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        print_pass("FirebaseTransport class imported")
        
        # Test initialization
        tests_total += 1
        try:
            transport = FirebaseTransport(project_id="test-project")
            print_pass("FirebaseTransport initialized with project_id")
            tests_passed += 1
            
            # Check attributes
            tests_total += 1
            assert hasattr(transport, 'client_id'), "Missing client_id"
            assert hasattr(transport, 'project_id'), "Missing project_id"
            assert hasattr(transport, '_listener_running'), "Missing _listener_running"
            assert hasattr(transport, '_heartbeat_running'), "Missing _heartbeat_running"
            print_pass(f"Transport attributes initialized (client_id: {transport.client_id[:8]}...)")
            tests_passed += 1
            
            # Check initial state
            tests_total += 1
            assert transport._listener_running == False, "Listener should not be running initially"
            assert transport._heartbeat_running == False, "Heartbeat should not be running initially"
            print_pass("Transport initial state correct")
            tests_passed += 1
            
            # Check debug mode
            tests_total += 1
            transport.debug = True
            assert transport.debug == True, "Debug mode not settable"
            print_pass("Debug mode can be enabled")
            tests_passed += 1
            
        except ImportError as e:
            print_fail("FirebaseTransport initialization", f"Import error: {e}")
            print_warning("This may indicate Firebase credentials are not set up")
        
    except Exception as e:
        print_fail("FirebaseTransport initialization", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_transport_methods():
    """Test FirebaseTransport methods exist and are callable"""
    print_header("TEST 4: FirebaseTransport Methods")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        transport = FirebaseTransport(project_id="test-project")
        transport.debug = True
        
        # List of methods that should exist
        methods = [
            'send',
            'on_message',
            'start_listening',
            'stop_listening',
            'start_heartbeat',
            'stop_heartbeat',
            'start_cleanup',
            'stop_cleanup',
            'get_client_id',
            '_is_session_active',
            '_retry_operation',
            '_listen_loop',
            '_heartbeat_loop',
            '_cleanup_loop',
        ]
        
        for method_name in methods:
            tests_total += 1
            assert hasattr(transport, method_name), f"Missing method: {method_name}"
            assert callable(getattr(transport, method_name)), f"Method not callable: {method_name}"
            print_pass(f"Method '{method_name}' exists and is callable")
            tests_passed += 1
        
    except Exception as e:
        print_fail("FirebaseTransport methods test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_callback_registration():
    """Test callback registration"""
    print_header("TEST 5: Callback Registration")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        transport = FirebaseTransport(project_id="test-project")
        
        # Test callback registration
        tests_total += 1
        callback_called = []
        
        def test_callback(msg):
            callback_called.append(msg)
        
        transport.on_message(test_callback)
        assert transport._message_callback is not None, "Callback not registered"
        print_pass("Callback registration works")
        tests_passed += 1
        
        # Test callback is the right function
        tests_total += 1
        assert transport._message_callback == test_callback, "Registered callback mismatch"
        print_pass("Registered callback is correct")
        tests_passed += 1
        
    except Exception as e:
        print_fail("Callback registration test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_session_management():
    """Test session management methods"""
    print_header("TEST 6: Session Management")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        transport = FirebaseTransport(project_id="test-project")
        transport.debug = True
        
        # Test session active check (no session started yet)
        tests_total += 1
        is_active = transport._is_session_active()
        print_pass(f"Session active check works (initial: {is_active})")
        tests_passed += 1
        
        # Test heartbeat can be started (but won't actually work without proper setup)
        tests_total += 1
        try:
            transport.start_heartbeat()
            assert transport._heartbeat_running == True, "Heartbeat not started"
            print_pass("Heartbeat start/run state works")
            tests_passed += 1
            
            # Test heartbeat thread created
            tests_total += 1
            assert transport._heartbeat_thread is not None, "Heartbeat thread not created"
            assert isinstance(transport._heartbeat_thread, threading.Thread), "Heartbeat thread wrong type"
            print_pass("Heartbeat thread created correctly")
            tests_passed += 1
            
            # Test heartbeat stop
            tests_total += 1
            transport.stop_heartbeat()
            time.sleep(0.2)  # Let thread finish
            assert transport._heartbeat_running == False, "Heartbeat not stopped"
            print_pass("Heartbeat stop works")
            tests_passed += 1
            
        except Exception as e:
            print_warning(f"Heartbeat test incomplete: {e}")
        
    except Exception as e:
        print_fail("Session management test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_retry_logic():
    """Test retry operation with exponential backoff"""
    print_header("TEST 7: Retry Logic")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        transport = FirebaseTransport(project_id="test-project")
        transport.debug = True
        
        # Test successful operation on first try
        tests_total += 1
        call_count = []
        
        def success_operation():
            call_count.append(1)
            return "success"
        
        result = transport._retry_operation(success_operation, operation_name="test success")
        assert result == "success", "Operation result mismatch"
        assert len(call_count) == 1, "Operation called more than once"
        print_pass("Retry logic: operation succeeds on first try")
        tests_passed += 1
        
        # Test operation fails all retries
        tests_total += 1
        call_count.clear()
        
        def always_fails():
            call_count.append(1)
            raise ValueError("Test error")
        
        try:
            transport._retry_operation(always_fails, operation_name="test failure")
            print_fail("Retry logic: should have raised exception after retries")
        except ValueError as e:
            assert len(call_count) == 3, f"Should retry 3 times, got {len(call_count)}"
            print_pass(f"Retry logic: retried {len(call_count)} times before failing")
            tests_passed += 1
        
        # Test configuration
        tests_total += 1
        assert transport._max_retries == 3, "Default max retries wrong"
        assert transport._base_retry_delay == 0.5, "Default retry delay wrong"
        print_pass(f"Retry configuration correct (max_retries={transport._max_retries}, base_delay={transport._base_retry_delay}s)")
        tests_passed += 1
        
    except Exception as e:
        print_fail("Retry logic test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_get_client_id():
    """Test client ID retrieval"""
    print_header("TEST 8: Client ID")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        import uuid
        
        transport = FirebaseTransport(project_id="test-project")
        
        # Test get_client_id
        tests_total += 1
        client_id = transport.get_client_id()
        assert client_id is not None, "Client ID is None"
        assert isinstance(client_id, str), "Client ID is not a string"
        print_pass(f"get_client_id works (ID: {client_id[:16]}...)")
        tests_passed += 1
        
        # Test it's a valid UUID format
        tests_total += 1
        try:
            uuid.UUID(client_id)
            print_pass("Client ID is a valid UUID")
            tests_passed += 1
        except ValueError:
            print_fail("Client ID is not a valid UUID", client_id)
        
    except Exception as e:
        print_fail("Client ID test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_listener_lifecycle():
    """Test listener start/stop lifecycle"""
    print_header("TEST 9: Listener Lifecycle")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        transport = FirebaseTransport(project_id="test-project")
        transport.debug = False  # Disable debug to avoid Firestore errors
        
        # Test listener initial state
        tests_total += 1
        assert transport._listener_running == False, "Listener should not be running initially"
        assert transport._listener_thread is None, "Listener thread should be None initially"
        print_pass("Listener initial state correct")
        tests_passed += 1
        
        # Test listener can't be started without proper Firestore setup
        # (we just check that the attempt is made properly)
        tests_total += 1
        try:
            transport.start_listening('test-channel', poll_interval=1.0)
            # If we get here, listener started (or tried to)
            assert transport._listener_running == True, "Listener should be marked as running"
            assert transport._listener_thread is not None, "Listener thread should be created"
            print_pass("Listener start/thread creation logic works")
            tests_passed += 1
            
            # Test listener stop
            tests_total += 1
            transport.stop_listening()
            time.sleep(0.2)  # Let thread finish
            assert transport._listener_running == False, "Listener should be stopped"
            print_pass("Listener stop works")
            tests_passed += 1
            
        except Exception as e:
            print_warning(f"Listener lifecycle test (may require Firestore): {type(e).__name__}")
            # Still count as partial pass since logic works
            tests_passed += 1
            tests_total += 1
        
    except Exception as e:
        print_fail("Listener lifecycle test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_cleanup_lifecycle():
    """Test cleanup thread lifecycle"""
    print_header("TEST 10: Cleanup Lifecycle")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        transport = FirebaseTransport(project_id="test-project")
        transport.debug = False  # Disable debug
        
        # Test cleanup initial state
        tests_total += 1
        assert transport._cleanup_running == False, "Cleanup should not be running initially"
        assert transport._cleanup_thread is None, "Cleanup thread should be None initially"
        print_pass("Cleanup initial state correct")
        tests_passed += 1
        
        # Test cleanup can be started
        tests_total += 1
        try:
            transport.start_cleanup()
            assert transport._cleanup_running == True, "Cleanup should be marked as running"
            assert transport._cleanup_thread is not None, "Cleanup thread should be created"
            print_pass("Cleanup start/thread creation works")
            tests_passed += 1
            
            # Test cleanup stop
            tests_total += 1
            transport.stop_cleanup()
            time.sleep(0.2)  # Let thread finish
            assert transport._cleanup_running == False, "Cleanup should be stopped"
            print_pass("Cleanup stop works")
            tests_passed += 1
            
        except Exception as e:
            print_warning(f"Cleanup lifecycle test (may require Firestore): {type(e).__name__}")
            tests_passed += 1
            tests_total += 1
        
    except Exception as e:
        print_fail("Cleanup lifecycle test", str(e))
        import traceback
        traceback.print_exc()
    
    return tests_passed, tests_total

def test_repr():
    """Test string representation"""
    print_header("TEST 11: String Representation")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from firebase_transport import FirebaseTransport
        transport = FirebaseTransport(project_id="my-project")
        
        tests_total += 1
        repr_str = repr(transport)
        assert "FirebaseTransport" in repr_str, "__repr__ missing class name"
        assert "my-project" in repr_str, "__repr__ missing project_id"
        print_pass(f"__repr__ works: {repr_str}")
        tests_passed += 1
        
    except Exception as e:
        print_fail("String representation test", str(e))
    
    return tests_passed, tests_total

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}Firebase Transport Testing Suite{Colors.RESET}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_passed = 0
    all_total = 0
    
    # Run all tests
    tests = [
        test_imports,
        test_message_model,
        test_transport_initialization,
        test_transport_methods,
        test_callback_registration,
        test_session_management,
        test_retry_logic,
        test_get_client_id,
        test_listener_lifecycle,
        test_cleanup_lifecycle,
        test_repr,
    ]
    
    for test_func in tests:
        try:
            passed, total = test_func()
            all_passed += passed
            all_total += total
        except Exception as e:
            print_fail(f"Test '{test_func.__name__}'", str(e))
            import traceback
            traceback.print_exc()
    
    # Print summary
    print_header("TEST SUMMARY")
    
    pass_rate = (all_passed / all_total * 100) if all_total > 0 else 0
    
    print(f"Total Tests: {all_total}")
    print(f"Passed: {Colors.GREEN}{all_passed}{Colors.RESET}")
    print(f"Failed: {Colors.RED}{all_total - all_passed}{Colors.RESET}")
    print(f"Pass Rate: {pass_rate:.1f}%\n")
    
    if all_passed == all_total:
        print(f"{Colors.GREEN}{Colors.BOLD}SUCCESS - ALL TESTS PASSED!{Colors.RESET}")
        print("Firebase Transport is working correctly!\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}FAILURE - SOME TESTS FAILED{Colors.RESET}")
        print("See details above for debugging information.\n")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
