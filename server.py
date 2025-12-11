#!/usr/bin/env python3
"""
DNS Tunnel Server
Receives data encoded in DNS queries and can send responses.
"""

import socket
import struct
import base64
import threading
from collections import defaultdict
from typing import Dict, Tuple, Optional
import time

class DNSTunnelServer:
    def __init__(self, listen_ip: str = "127.0.0.1", listen_port: int = 9999, domain: str = "tunnel.example.com"):
        """
        Initialize DNS tunnel server.
        
        Args:
            listen_ip: IP address to bind to (default: 127.0.0.1 for localhost, use 0.0.0.0 for all interfaces)
            listen_port: Port to listen on (default: 9999 for testing, avoid 5353 on Windows)
            domain: Domain to accept queries for
        """
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.domain = domain.rstrip('.').lower()
        
        # Storage for received data chunks
        self.sessions: Dict[int, Dict[int, str]] = defaultdict(dict)
        self.session_metadata: Dict[int, Tuple[int, float]] = {}  # session_id: (total_chunks, last_activity)
        
        # Storage for data to send back to clients
        self.response_queue: Dict[int, bytes] = {}
        
        self.running = False
        self.sock = None
        
        # Cleanup thread
        self.cleanup_thread = None
        
    def _parse_dns_query(self, data: bytes) -> Optional[Tuple[int, str, int]]:
        """
        Parse DNS query packet.
        
        Returns:
            Tuple of (transaction_id, query_name, query_type) or None
        """
        try:
            if len(data) < 12:
                print(f"  Error: Packet too short ({len(data)} bytes)")
                return None
                
            # Parse header
            transaction_id = struct.unpack('!H', data[0:2])[0]
            
            # Skip to question section (offset 12)
            offset = 12
            
            # Parse domain name
            labels = []
            while offset < len(data) and data[offset] != 0:
                length = data[offset]
                if length > 63:  # Invalid label length
                    print(f"  Error: Invalid label length {length}")
                    return None
                offset += 1
                if offset + length > len(data):
                    print(f"  Error: Label extends beyond packet")
                    return None
                labels.append(data[offset:offset+length].decode('ascii', errors='ignore'))
                offset += length
            
            if offset >= len(data):
                print(f"  Error: Unexpected end of packet")
                return None
                
            query_name = '.'.join(labels).lower()
            offset += 1  # Skip null terminator
            
            # Parse query type and class
            if offset + 4 > len(data):
                print(f"  Error: Missing query type/class")
                return None
                
            query_type = struct.unpack('!H', data[offset:offset+2])[0]
            
            return transaction_id, query_name, query_type
            
        except Exception as e:
            print(f"  Error parsing query: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_dns_response(self, transaction_id: int, query_name: str, 
                            query_type: int, response_data: Optional[str] = None) -> bytes:
        """
        Create DNS response packet.
        
        Args:
            transaction_id: Transaction ID from query
            query_name: Domain name queried
            query_type: Type of query (1=A, 16=TXT)
            response_data: Data to include in response (for TXT records)
        """
        # Flags: Standard query response, no error
        flags = 0x8180
        
        # Counts
        questions = 1
        answers = 1
        authority = 0
        additional = 0
        
        # Header
        header = struct.pack('!HHHHHH', transaction_id, flags, questions, 
                           answers, authority, additional)
        
        # Question section (echo the question)
        question = b''
        for label in query_name.split('.'):
            if label:  # Skip empty labels
                question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'
        question += struct.pack('!HH', query_type, 1)  # Type and class
        
        # Answer section
        answer = b''
        
        # Name (use compression pointer to question)
        answer += b'\xc0\x0c'  # Pointer to offset 12 (start of question)
        
        # Type, Class, TTL
        answer += struct.pack('!HHI', query_type, 1, 300)  # 5 min TTL
        
        # Response data
        if query_type == 1:  # A record
            # Return a dummy IP (or could return actual data)
            ip_bytes = socket.inet_aton("127.0.0.1")
            answer += struct.pack('!H', 4) + ip_bytes
            
        elif query_type == 16:  # TXT record
            if response_data:
                # TXT record format: length byte + text
                txt_data = response_data.encode('ascii')
                answer += struct.pack('!H', len(txt_data) + 1)
                answer += struct.pack('B', len(txt_data)) + txt_data
            else:
                # Empty TXT record
                answer += struct.pack('!H', 1) + b'\x00'
        
        return header + question + answer
    
    def _decode_subdomain(self, query_name: str) -> Optional[Tuple[int, int, int, str]]:
        """
        Decode data from subdomain.
        
        Returns:
            Tuple of (session_id, chunk_num, total_chunks, data) or None
        """
        try:
            # Remove our domain from the end
            if not query_name.endswith(self.domain):
                print(f"  Query domain '{query_name}' doesn't match expected domain '{self.domain}'")
                return None
            
            subdomain = query_name[:-len(self.domain)-1]
            
            # Check if this is a receive request
            if subdomain.startswith('recv-'):
                session_id = int(subdomain.split('-')[1])
                return (session_id, -1, -1, "RECV")
            
            # Parse: sessionid-chunknum-totalchunks-data
            parts = subdomain.split('-', 3)
            if len(parts) != 4:
                print(f"  Invalid subdomain format: {subdomain}")
                return None
            
            session_id = int(parts[0])
            chunk_num = int(parts[1])
            total_chunks = int(parts[2])
            data = parts[3]
            
            return session_id, chunk_num, total_chunks, data
            
        except Exception as e:
            print(f"  Error decoding subdomain '{query_name}': {e}")
            return None
    
    def _assemble_session_data(self, session_id: int) -> Optional[bytes]:
        """Assemble complete message from chunks."""
        if session_id not in self.session_metadata:
            return None
        
        total_chunks, _ = self.session_metadata[session_id]
        session_data = self.sessions[session_id]
        
        # Check if we have all chunks
        if len(session_data) != total_chunks:
            return None
        
        # Assemble in order
        encoded_data = ''
        for i in range(total_chunks):
            if i not in session_data:
                return None
            encoded_data += session_data[i]
        
        # Decode base32
        try:
            # Add padding if needed
            padding = (8 - len(encoded_data) % 8) % 8
            encoded_data += '=' * padding
            return base64.b32decode(encoded_data.upper())
        except Exception as e:
            print(f"Error decoding data: {e}")
            return None
    
    def _cleanup_old_sessions(self):
        """Cleanup sessions older than 5 minutes."""
        while self.running:
            time.sleep(60)  # Check every minute
            
            current_time = time.time()
            expired_sessions = []
            
            for session_id, (_, last_activity) in list(self.session_metadata.items()):
                if current_time - last_activity > 300:  # 5 minutes
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                print(f"Cleaning up expired session: {session_id}")
                if session_id in self.sessions:
                    del self.sessions[session_id]
                if session_id in self.session_metadata:
                    del self.session_metadata[session_id]
                if session_id in self.response_queue:
                    del self.response_queue[session_id]
    
    def queue_response(self, session_id: int, data: bytes):
        """Queue data to send back to a client."""
        # Encode data for DNS response
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        self.response_queue[session_id] = encoded
        print(f"Queued response for session {session_id}: {len(data)} bytes")
    
    def handle_query(self, data: bytes, addr: Tuple[str, int]):
        """Handle incoming DNS query."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Received {len(data)} bytes from {addr[0]}:{addr[1]}")
        
        parsed = self._parse_dns_query(data)
        if not parsed:
            print("  Failed to parse DNS query")
            return
        
        transaction_id, query_name, query_type = parsed
        print(f"  Transaction ID: {transaction_id}")
        print(f"  Query: {query_name}")
        print(f"  Type: {query_type} ({'A' if query_type == 1 else 'TXT' if query_type == 16 else 'OTHER'})")
        
        # Decode subdomain
        decoded = self._decode_subdomain(query_name)
        if not decoded:
            # Not a tunnel query, send empty response anyway
            print("  Not a valid tunnel query, sending generic response")
            response = self._create_dns_response(transaction_id, query_name, query_type)
            self.sock.sendto(response, addr)
            return
        
        session_id, chunk_num, total_chunks, chunk_data = decoded
        
        # Handle receive request
        if chunk_data == "RECV":
            print(f"  Receive request for session {session_id}")
            response_data = self.response_queue.get(session_id)
            response = self._create_dns_response(transaction_id, query_name, 
                                                query_type, response_data)
            self.sock.sendto(response, addr)
            
            if response_data:
                print(f"  Sent response to session {session_id}")
                del self.response_queue[session_id]
            else:
                print(f"  No response queued for session {session_id}")
            return
        
        # Store chunk
        self.sessions[session_id][chunk_num] = chunk_data
        self.session_metadata[session_id] = (total_chunks, time.time())
        
        print(f"  Session: {session_id}, Chunk: {chunk_num+1}/{total_chunks}, Data: {chunk_data[:20]}...")
        
        # Try to assemble complete message
        complete_data = self._assemble_session_data(session_id)
        if complete_data:
            print(f"\n{'='*60}")
            print(f"COMPLETE MESSAGE RECEIVED - Session {session_id}")
            print(f"{'='*60}")
            print(f"Data ({len(complete_data)} bytes): {complete_data[:200]}")
            if len(complete_data) > 200:
                print(f"... (truncated)")
            print(f"{'='*60}\n")
            
            # Process the received data here
            self.on_data_received(session_id, complete_data, addr)
            
            # Clean up session
            del self.sessions[session_id]
            del self.session_metadata[session_id]
        
        # Send response
        response = self._create_dns_response(transaction_id, query_name, query_type)
        print(f"  Sending response ({len(response)} bytes)")
        self.sock.sendto(response, addr)
    
    def on_data_received(self, session_id: int, data: bytes, addr: Tuple[str, int]):
        """
        Callback when complete data is received.
        Override this method to process received data.
        """
        try:
            message = data.decode('utf-8')
            print(f"Decoded message: {message}")
            
            # Example: Echo back the message
            response = f"Server received: {message}".encode('utf-8')
            self.queue_response(session_id, response)
            
        except Exception as e:
            print(f"Error processing received data: {e}")
    
    def start(self):
        """Start the DNS tunnel server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Test if we can bind to the port
        try:
            print(f"Attempting to bind to {self.listen_ip}:{self.listen_port}...")
            self.sock.bind((self.listen_ip, self.listen_port))
            print(f"Successfully bound to {self.listen_ip}:{self.listen_port}")
        except OSError as e:
            print(f"ERROR: Could not bind to {self.listen_ip}:{self.listen_port}")
            print(f"Error details: {e}")
            if self.listen_port < 1024:
                print("Ports below 1024 require administrator privileges.")
            elif self.listen_port == 5353:
                print("Port 5353 (mDNS) may be blocked by Windows. Try port 9999 instead.")
            print("\nTry running:")
            print(f"  python {__file__} 9999 tunnel.example.com")
            return
        
        try:
            print(f"\n{'='*60}")
            print(f"DNS TUNNEL SERVER STARTED")
            print(f"{'='*60}")
            print(f"Listening on: {self.listen_ip}:{self.listen_port}")
            print(f"Domain: {self.domain}")
            
            # Test the socket is actually ready to receive
            self.sock.settimeout(0.1)
            print(f"Socket ready to receive data...")
            
            print(f"\nReady to receive queries...")
            print(f"Press Ctrl+C to stop")
            print(f"{'='*60}\n")
            
            self.running = True
            
            # Start cleanup thread
            self.cleanup_thread = threading.Thread(target=self._cleanup_old_sessions, daemon=True)
            self.cleanup_thread.start()
            
            # Main loop
            packet_count = 0
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(512)
                    packet_count += 1
                    print(f"\n*** PACKET #{packet_count} RECEIVED ***")
                    # Handle in separate thread to avoid blocking
                    threading.Thread(target=self.handle_query, args=(data, addr), daemon=True).start()
                except socket.timeout:
                    # This is normal, just loop again
                    continue
                except KeyboardInterrupt:
                    print("\n\nShutting down...")
                    break
                except Exception as e:
                    print(f"Error in main loop: {e}")
                    import traceback
                    traceback.print_exc()
            
        except Exception as e:
            print(f"Error starting server: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()
    
    def stop(self):
        """Stop the DNS tunnel server."""
        self.running = False
        if self.sock:
            self.sock.close()
        print("\nServer stopped")


# Example usage
if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    port = 9999  # Use non-privileged, non-special port by default
    domain = "tunnel.example.com"
    listen_ip = "127.0.0.1"  # Default to localhost for testing
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    if len(sys.argv) > 2:
        domain = sys.argv[2]
    if len(sys.argv) > 3:
        listen_ip = sys.argv[3]
    
    print(f"Starting DNS Tunnel Server on {listen_ip}:{port}")
    print(f"Domain: {domain}\n")
    
    server = DNSTunnelServer(listen_ip=listen_ip, listen_port=port, domain=domain)
    server.start()