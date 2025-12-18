import time
from firebase_transport import FirebaseTransport

PROJECT_ID = "my-awesome-project-3c43d"
CHANNEL = "test-channel"

def main():
    t1 = FirebaseTransport(PROJECT_ID)
    t2 = FirebaseTransport(PROJECT_ID)

    print("[*] Sending message...")
    ok = t1.send(CHANNEL, {"ping": "pong"})
    assert ok, "Send failed"

    print("[*] Waiting for receive...")
    msg = t2.receive(CHANNEL, timeout=10)
    assert msg is not None, "No message received"

    print("[+] Tunnel works")
    print("    Data:", msg["data"])
    print("    Sender:", msg["sender"])

if __name__ == "__main__":
    main()
