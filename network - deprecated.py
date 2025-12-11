#DEPRECATED


#!/usr/bin/env python3
"""
DNS Tunnel Client
Encodes data in DNS queries and decodes responses for covert communication.
"""

import socket
import base64
import struct
import random
import time
from typing import Optional

class DNSTunnelClient:
    def __init__(self, server_ip: str, domain: str, server_port: int = 9999):
        """
        Initialize DNS tunnel client.
        
        Args:
            server_ip: IP address of the tunnel server (your DNS tunnel server)
            domain: Domain name to use for encoding (e.g., "tunnel.example.com")
            server_port: DNS server port (default: 9999 for testing)
        """
        self.server_ip = server_ip
        self.domain = domain.rstrip('.')
        self.server_port = server_port
        self.session_id = random.randint(1000, 9999)
        
    def _encode_data(self, data: bytes, chunk_size: int = 32) -> list:
        """Encode data into DNS-safe subdomain labels."""
        # Base32 encoding (DNS-safe, no case sensitivity issues)
        encoded = base64.b32encode(data).decode('ascii').lower().rstrip('=')
        
        # Split into chunks that fit DNS label size limits (63 chars max)
        chunks = []
        for i in range(0, len(encoded), chunk_size):
            chunks.append(encoded[i:i+chunk_size])
        
        return chunks
    
    def _create_dns_query(self, subdomain: str, query_type: int = 1) -> bytes:
        """
        Create a DNS query packet.
        
        Args:
            subdomain: Subdomain to query
            query_type: DNS query type (1 = A record, 16 = TXT record)
        """
        # Transaction ID
        transaction_id = random.randint(0, 65535)
        
        # Flags: Standard query
        flags = 0x0100
        
        # Questions, Answers, Authority, Additional
        questions = 1
        answers = 0
        authority = 0
        additional = 0
        
        # Header
        header = struct.pack('!HHHHHH', transaction_id, flags, questions, 
                           answers, authority, additional)
        
        # Question section
        full_domain = f"{subdomain}.{self.domain}"
        question = b''
        
        # Encode domain name
        for label in full_domain.split('.'):
            question += struct.pack('B', len(label)) + label.encode('ascii')
        question += b'\x00'  # Null terminator
        
        # Query type and class (IN = Internet)
        question += struct.pack('!HH', query_type, 1)
        
        return header + question
    
    def _parse_dns_response(self, response: bytes) -> Optional[str]:
        """Parse DNS response and extract data."""
        try:
            # Skip header (12 bytes)
            offset = 12
            
            # Skip question section
            while response[offset] != 0:
                offset += response[offset] + 1
            offset += 5  # Null byte + type + class
            
            # Parse answer section
            if len(response) <= offset:
                return None
            
            # Skip name (usually compressed pointer)
            if response[offset] & 0xC0:
                offset += 2
            else:
                while response[offset] != 0:
                    offset += response[offset] + 1
                offset += 1
            
            # Type, Class, TTL, Data length
            offset += 8  # Skip type, class, and TTL
            data_len = struct.unpack('!H', response[offset:offset+2])[0]
            offset += 2
            
            # Extract data
            data = response[offset:offset+data_len]
            
            # If it's a TXT record, extract text
            if len(data) > 0 and data[0] < len(data):
                return data[1:data[0]+1].decode('ascii', errors='ignore')
            
            return None
            
        except Exception as e:
            print(f"Error parsing response: {e}")
            return None
    
    def send_data(self, data: bytes, chunk_delay: float = 0.1) -> bool:
        """
        Send data through DNS tunnel.
        
        Args:
            data: Bytes to send
            chunk_delay: Delay between chunks in seconds
        
        Returns:
            True if successful, False otherwise
        """
        chunks = self._encode_data(data)
        total_chunks = len(chunks)
        
        print(f"Sending {len(data)} bytes in {total_chunks} chunks to {self.server_ip}:{self.server_port}...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        try:
            for i, chunk in enumerate(chunks):
                # Create subdomain with metadata: sessionid-chunknum-totalchunks-data
                subdomain = f"{self.session_id}-{i}-{total_chunks}-{chunk}"
                
                # Create and send DNS query
                query = self._create_dns_query(subdomain)
                sock.sendto(query, (self.server_ip, self.server_port))
                
                print(f"Sent chunk {i+1}/{total_chunks}")
                
                # Wait for response
                try:
                    response, _ = sock.recvfrom(512)
                    print(f"  Received ACK for chunk {i+1}")
                except socket.timeout:
                    print(f"  Timeout on chunk {i+1}, continuing...")
                
                time.sleep(chunk_delay)
            
            print("All chunks sent successfully!")
            return True
            
        except Exception as e:
            print(f"Error sending data: {e}")
            return False
        finally:
            sock.close()
    
    def receive_data(self, timeout: int = 10) -> Optional[bytes]:
        """
        Request and receive data through DNS tunnel.
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            Received data as bytes, or None if failed
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        try:
            # Request data with special subdomain
            subdomain = f"recv-{self.session_id}"
            query = self._create_dns_query(subdomain, query_type=16)  # TXT record
            
            sock.sendto(query, (self.server_ip, self.server_port))
            
            response, _ = sock.recvfrom(512)
            data = self._parse_dns_response(response)
            
            if data:
                # Decode base32
                # Add padding if needed
                padding = (8 - len(data) % 8) % 8
                data += '=' * padding
                return base64.b32decode(data.upper())
            
            return None
            
        except socket.timeout:
            print("Timeout waiting for response")
            return None
        except Exception as e:
            print(f"Error receiving data: {e}")
            return None
        finally:
            sock.close()


# Example usage
if __name__ == "__main__":
    import sys
    
    # Get server IP from command line or use localhost
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    domain = sys.argv[3] if len(sys.argv) > 3 else "tunnel.example.com"
    
    print(f"DNS Tunnel Client")
    print(f"=================")
    print(f"Connecting to DNS tunnel server at {server_ip}:{server_port}")
    print(f"Using domain: {domain}\n")
    
    # Initialize client
    client = DNSTunnelClient(
        server_ip=server_ip,
        domain=domain,
        server_port=server_port
    )
    
    # Send some data
    message = b"Hello from DNS tunnel!"
    print(f"Sending message: {message.decode()}")
    success = client.send_data(message)
    
    if success:
        # Wait a moment for server to process
        time.sleep(0.5)
        
        # Receive data (server echo response)
        print("\nTrying to receive data...")
        received = client.receive_data()
        if received:
            print(f"Received: {received.decode()}")
        else:
            print("No data received (server may not have queued a response)")