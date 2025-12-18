import threading
import time
import server.server as server
import client.client as client

def start_server():
    server = server.Server(debug=True)
    server.start()

def test_client_server():
    # Start client
    client = client.Client(debug=True)

    print("\n[Test] Sending ACK...")
    ack_result = client.ack()
    print(f"[Result] ACK: {ack_result}\n")

    print("[Test] Starting new chat...")
    new_chat_result = client.new_chat()
    print(f"[Result] New Chat: {new_chat_result}\n")

    print("[Test] Sending PROMPT...")
    prompt = "Hello LLM, what is 2+2?"
    response = client.send_prompt(prompt)
    print(f"[Result] PROMPT Response: {response}\n")

    # Clean up
    client.close()
    print("[Test] Client closed.")

if __name__ == "__main__":
    # Start server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Give server some time to initialize
    time.sleep(2)

    # Run the client test
    test_client_server()

    # Keep main thread alive briefly to ensure server outputs appear
    time.sleep(5)
    print("[Test] Done.")
