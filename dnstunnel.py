#!/usr/bin/env python3
"""
DNS Tunnel Library - Pure Transport Layer with Chunking Support
Provides DNSTunnelClient and DNSTunnelServer as network communication primitives.
Automatically handles large data by chunking responses.
"""

import socket
import base64
import struct
import random
import time
import threading
from typing import Optional, Callable
from collections import defaultdict

# ============================================================================
# DNS TUNNEL CLIENT - Pure Transport Layer with Chunking
# ============================================================================

class DNSTunnelClient:
    """
    DNS Tunnel Client - Handles only network communication.
    
    Use this to send/receive raw bytes through DNS queries.
    Automatically handles chunking for large responses.
    """
    
    def __init__(self, server_ip: str, server_port: int, domain: str):
        """
        Initialize DNS tunnel client.
        
        Args:
            server_ip: IP address of tunnel server
            server_port: Port number of tunnel server
            domain: Domain to use for queries (e.g., "tunnel.example.com")
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.domain = domain.rstrip('.').lower()
        self.session_id = random.randint(1000, 9999)
        self.timeout = 5
        self.max_response_chunk = 180  # Max bytes per response chunk
    
    def send(self, data: bytes, chunk_delay: float = 0.05) -> bool:
        """
        Send raw bytes through DNS tunnel.
        
        Args:
            data: Bytes to send
            chunk_delay: Delay between chunks in seconds
            
        Returns:
            True if successful, False otherwise
        """
        chunks = self._encode_data(data)
        total_chunks = len(chunks)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        
        try:
            for i, chunk in enumerate(chunks):
                subdomain = f"{self.session_id}-{i}-{total_chunks}-{chunk}"
                query = self._create_dns_query(subdomain)
                sock.sendto(query, (self.server_ip, self.server_port))
                
                try:
                    response, _ = sock.recvfrom(512)
                except socket.timeout:
                    pass
                
                time.sleep(chunk_delay)
            
            return True
        except Exception as e:
            print(f"[DNSTunnelClient] Send error: {e}")
            return False
        finally:
            sock.close()
    
    def receive(self, timeout: Optional[int] = None, max_chunks: int = 100) -> Optional[bytes]:
        """
        Receive raw bytes through DNS tunnel with automatic chunk reassembly.
        
        Args:
            timeout: Timeout in seconds per chunk (uses default if None)
            max_chunks: Maximum number of chunks to receive
            
        Returns:
            Received bytes or None if no data/timeout
        """
        all_data = []
        chunk_num = 0
        total_chunks = None
        
        while chunk_num < max_chunks:
            chunk_data = self._receive_chunk(chunk_num, timeout)
            
            if chunk_data is None:
                # No more chunks or timeout
                break
            
            # Parse chunk metadata
            if chunk_data.startswith(b"CHUNK:"):
                try:
                    header, data = chunk_data.split(b":", 3)[1:]  # Skip "CHUNK"
                    parts = header.split(b"/")
                    current = int(parts[0])
                    total = int(parts[1])
                    
                    if total_chunks is None:
                        total_chunks = total
                    
                    all_data.append(data)
                    chunk_num += 1
                    
                    if current + 1 >= total:
                        # All chunks received
                        break
                except:
                    # Not a chunked response, return as-is
                    return chunk_data
            else:
                # Single response without chunking
                return chunk_data
        
        if all_data:
            return b''.join(all_data)
        return None
    
    def _receive_chunk(self, chunk_num: int, timeout: Optional[int] = None) -> Optional[bytes]:
        """Receive a single chunk from server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout or self.timeout)
        
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        except:
            pass
        
        try:
            subdomain = f"recv-{self.session_id}-{chunk_num}"
            query = self._create_dns_query(subdomain, query_type=16)
            sock.sendto(query, (self.server_ip, self.server_port))
            
            response, _ = sock.recvfrom(2048)
            data = self._parse_dns_response(response)
            
            if data:
                padding = (8 - len(data) % 8) % 8
                data += '=' * padding
                return base64.b32decode(data.upper())
            return None
        except socket.timeout:
            return None
        except OSError as e:
            if hasattr(e, 'winerror') and e.winerror == 10040:
                print(f"[DNSTunnelClient] Error: Response too large even after chunking")
            return None
        except Exception as e:
            return None
        finally:
            sock.close()
    
    def send_and_receive(self, data: bytes, wait_time: float = 0.5, 
                         timeout: Optional[int] = None) -> Optional[bytes]:
        """
        Convenience method: send data and wait for response.
        
        Args:
            data: Data to send
            wait_time: Time to wait between send and receive
            timeout: Receive timeout per chunk
            
        Returns:
            Response bytes or None
        """
        if self.send(data):
            time.sleep(wait_time)
            return self.receive(timeout)
        return None
    
    # Internal methods
    def _encode_data(self, data: bytes, chunk_size: int = 32) -> list:
        """Encode data into DNS-safe chunks."""
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        return [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
    
    def _create_dns_query(self, subdomain: str, query_type: int = 1) -> bytes:
        """Create DNS query packet."""
        transaction_id = random.randint(0, 65535)
        flags = 0x0100
        header = struct.pack('!HHHHHH', transaction_id, flags, 1, 0, 0, 0)
        
        full_domain = f"{subdomain}.{self.domain}"
        question = b''
        for label in full_domain.split('.'):
            question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'
        question += struct.pack('!HH', query_type, 1)
        
        return header + question
    
    def _parse_dns_response(self, response: bytes) -> Optional[str]:
        """Parse DNS response and extract data."""
        try:
            offset = 12
            while response[offset] != 0:
                offset += response[offset] + 1
            offset += 5
            if len(response) <= offset:
                return None
            if response[offset] & 0xC0:
                offset += 2
            else:
                while response[offset] != 0:
                    offset += response[offset] + 1
                offset += 1
            offset += 8
            data_len = struct.unpack('!H', response[offset:offset+2])[0]
            offset += 2
            data = response[offset:offset+data_len]
            
            # TXT records can have multiple strings
            result = []
            i = 0
            while i < len(data):
                str_len = data[i]
                i += 1
                if i + str_len > len(data):
                    break
                result.append(data[i:i+str_len].decode('ascii', errors='ignore'))
                i += str_len
            
            return ''.join(result) if result else None
        except:
            return None


# ============================================================================
# DNS TUNNEL SERVER - Pure Transport Layer with Chunking
# ============================================================================

class DNSTunnelServer:
    """
    DNS Tunnel Server - Handles only network communication.
    
    Set a callback to receive data from clients.
    Use queue_response() to send data back to clients.
    Automatically chunks large responses.
    """
    
    def __init__(self, listen_ip: str, listen_port: int, domain: str):
        """
        Initialize DNS tunnel server.
        
        Args:
            listen_ip: IP to bind to (e.g., "127.0.0.1" or "0.0.0.0")
            listen_port: Port to listen on
            domain: Domain to accept queries for
        """
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.domain = domain.rstrip('.').lower()
        
        # Internal state
        self.sessions = defaultdict(dict)
        self.session_metadata = {}
        self.response_queue = {}  # session_id -> list of chunks
        self.running = False
        self.sock = None
        
        # Chunking configuration
        self.max_chunk_size = 180  # Max bytes per chunk after base32 encoding
        
        # Callback for when complete data is received
        self.on_data_received: Optional[Callable[[int, bytes, tuple], None]] = None
    
    def queue_response(self, session_id: int, data: bytes):
        """
        Queue data to send back to a client. Automatically chunks if needed.
        
        Args:
            session_id: Session ID of the client
            data: Raw bytes to send (can be any size, will be chunked automatically)
        """
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        
        # Calculate how many chunks we need
        # Account for chunk header overhead: "CHUNK:N/T:"
        header_overhead = 20  # Conservative estimate for "CHUNK:99/99:"
        effective_chunk_size = self.max_chunk_size - header_overhead
        
        if len(encoded) <= effective_chunk_size:
            # Small enough to send in one chunk, no header needed
            self.response_queue[session_id] = [encoded]
        else:
            # Need to chunk the response
            chunks = []
            total_chunks = (len(encoded) + effective_chunk_size - 1) // effective_chunk_size
            
            for i in range(total_chunks):
                start = i * effective_chunk_size
                end = start + effective_chunk_size
                chunk_data = encoded[start:end]
                
                # Add chunk header
                chunk_with_header = f"CHUNK:{i}/{total_chunks}:{chunk_data}"
                chunks.append(chunk_with_header)
            
            self.response_queue[session_id] = chunks
            print(f"[DNSTunnelServer] Response for session {session_id} split into {total_chunks} chunks ({len(data)} bytes)")
    
    def start(self, blocking: bool = True):
        """
        Start the DNS tunnel server.
        
        Args:
            blocking: If True, blocks until stopped. If False, runs in background thread.
        """
        if blocking:
            self._run()
        else:
            thread = threading.Thread(target=self._run, daemon=True)
            thread.start()
    
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.sock:
            self.sock.close()
    
    # Internal methods
    def _run(self):
        """Main server loop."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.sock.bind((self.listen_ip, self.listen_port))
            self.running = True
            self.sock.settimeout(0.1)
            
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(512)
                    threading.Thread(target=self._handle_query, args=(data, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    break
        except Exception as e:
            print(f"[DNSTunnelServer] Error: {e}")
        finally:
            self.stop()
    
    def _handle_query(self, data: bytes, addr: tuple):
        """Handle incoming DNS query."""
        parsed = self._parse_dns_query(data)
        if not parsed:
            return
        
        transaction_id, query_name, query_type = parsed
        decoded = self._decode_subdomain(query_name)
        
        if not decoded:
            response = self._create_dns_response(transaction_id, query_name, query_type)
            self.sock.sendto(response, addr)
            return
        
        session_id, chunk_num, total_chunks, chunk_data = decoded
        
        # Handle receive request (possibly for a specific chunk)
        if chunk_data == "RECV":
            if session_id in self.response_queue:
                chunks = self.response_queue[session_id]
                
                if chunk_num < len(chunks):
                    # Send specific chunk
                    response_data = chunks[chunk_num]
                    response = self._create_dns_response(transaction_id, query_name, 
                                                        query_type, response_data)
                    self.sock.sendto(response, addr)
                    
                    # If this was the last chunk, clean up
                    if chunk_num >= len(chunks) - 1:
                        del self.response_queue[session_id]
                else:
                    # No more chunks
                    response = self._create_dns_response(transaction_id, query_name, query_type)
                    self.sock.sendto(response, addr)
            else:
                # No response queued
                response = self._create_dns_response(transaction_id, query_name, query_type)
                self.sock.sendto(response, addr)
            return
        
        # Store chunk
        self.sessions[session_id][chunk_num] = chunk_data
        self.session_metadata[session_id] = (total_chunks, time.time())
        
        # Try to assemble complete message
        complete_data = self._assemble_session_data(session_id)
        if complete_data:
            # Call user's callback
            if self.on_data_received:
                self.on_data_received(session_id, complete_data, addr)
            
            # Clean up session
            del self.sessions[session_id]
            del self.session_metadata[session_id]
        
        # Send response
        response = self._create_dns_response(transaction_id, query_name, query_type)
        self.sock.sendto(response, addr)
    
    def _decode_subdomain(self, query_name: str):
        """Decode data from subdomain."""
        try:
            if not query_name.endswith(self.domain):
                return None
            subdomain = query_name[:-len(self.domain)-1]
            
            # Check for chunk receive request: recv-SESSION-CHUNKNUM
            if subdomain.startswith('recv-'):
                parts = subdomain.split('-')
                session_id = int(parts[1])
                chunk_num = int(parts[2]) if len(parts) > 2 else 0
                return (session_id, chunk_num, -1, "RECV")
            
            # Regular data: sessionid-chunknum-totalchunks-data
            parts = subdomain.split('-', 3)
            if len(parts) != 4:
                return None
            return int(parts[0]), int(parts[1]), int(parts[2]), parts[3]
        except:
            return None
    
    def _assemble_session_data(self, session_id: int) -> Optional[bytes]:
        """Assemble complete message from chunks."""
        if session_id not in self.session_metadata:
            return None
        total_chunks, _ = self.session_metadata[session_id]
        session_data = self.sessions[session_id]
        if len(session_data) != total_chunks:
            return None
        encoded_data = ''.join(session_data[i] for i in range(total_chunks))
        try:
            padding = (8 - len(encoded_data) % 8) % 8
            encoded_data += '=' * padding
            return base64.b32decode(encoded_data.upper())
        except:
            return None
    
    def _parse_dns_query(self, data: bytes):
        """Parse DNS query packet."""
        try:
            if len(data) < 12:
                return None
            transaction_id = struct.unpack('!H', data[0:2])[0]
            offset = 12
            labels = []
            while offset < len(data) and data[offset] != 0:
                length = data[offset]
                offset += 1
                labels.append(data[offset:offset+length].decode('ascii', errors='ignore'))
                offset += length
            query_name = '.'.join(labels).lower()
            offset += 1
            query_type = struct.unpack('!H', data[offset:offset+2])[0]
            return transaction_id, query_name, query_type
        except:
            return None
    
    def _create_dns_response(self, transaction_id: int, query_name: str, 
                            query_type: int, response_data: Optional[str] = None) -> bytes:
        """Create DNS response packet."""
        flags = 0x8180
        header = struct.pack('!HHHHHH', transaction_id, flags, 1, 1, 0, 0)
        
        question = b''
        for label in query_name.split('.'):
            if label:
                question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'
        question += struct.pack('!HH', query_type, 1)
        
        answer = b'\xc0\x0c'
        answer += struct.pack('!HHI', query_type, 1, 300)
        
        if query_type == 1:
            ip_bytes = socket.inet_aton("127.0.0.1")
            answer += struct.pack('!H', 4) + ip_bytes
        elif query_type == 16:
            if response_data:
                txt_data = response_data.encode('ascii')
                
                # Split into 255-byte chunks for TXT record
                chunks = []
                max_chunk = 255
                for i in range(0, len(txt_data), max_chunk):
                    chunk = txt_data[i:i+max_chunk]
                    chunks.append(struct.pack('B', len(chunk)) + chunk)
                
                txt_record = b''.join(chunks)
                answer += struct.pack('!H', len(txt_record)) + txt_record
            else:
                answer += struct.pack('!H', 1) + b'\x00'
        
        return header + question + answer