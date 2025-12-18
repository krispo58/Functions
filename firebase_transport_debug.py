import requests
import json
from firebase_transport import FirebaseTransport

PROJECT_ID = "my-awesome-project-3c43d"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/messages"

def raw_get():
    print("\n[*] RAW GET test")
    r = requests.get(BASE_URL, timeout=10)
    print("Status:", r.status_code)
    print("Body:", r.text[:500])

def raw_post():
    print("\n[*] RAW POST test")
    doc = {
        "fields": {
            "key": {"stringValue": "GigaPassword"},
            "channel": {"stringValue": "debug"},
            "id": {"stringValue": "debug-id"},
            "sender": {"stringValue": "debugger"},
            "timestamp": {"timestampValue": "2025-01-01T00:00:00Z"},
            "data": {"stringValue": "hello"}
        }
    }
    r = requests.post(
        BASE_URL + "?documentId=debug_doc",
        json=doc,
        timeout=10
    )
    print("Status:", r.status_code)
    print("Body:", r.text[:500])

def transport_test():
    print("\n[*] Transport layer test")
    t = FirebaseTransport(PROJECT_ID)

    print("Sending...")
    if not t.send("debug", {"msg": "test"}):
        print("Send failed")
        return

    print("Receiving...")
    msg = t.receive("debug", timeout=5)
    print("Received:", msg)

def main():
    print("=== FIRESTORE TUNNEL DEBUG ===")

    raw_get()
    raw_post()
    transport_test()

    print("\n[*] Debug complete")

if __name__ == "__main__":
    main()
