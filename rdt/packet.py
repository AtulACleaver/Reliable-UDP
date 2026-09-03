"""
Packet representation, encoding, decoding, checksum and sequence space helpers.
"""

def encode_packet() -> bytes:
    """
    Encode a packet into bytes to be sent over UDP.
    
    Returns:
        Encoded packet bytes.
    """
    # TODO(Atul): lane 1
    raise NotImplementedError

def decode_packet(data: bytes):
    """
    Decode received bytes into a packet.
    
    Args:
        data: The bytes received over UDP.
        
    Returns:
        The decoded packet object.
    """
    # TODO(Atul): lane 1
    raise NotImplementedError

def calculate_checksum(data: bytes) -> int:
    """
    Calculate a 16-bit internet checksum for the given data.
    
    Args:
        data: Data to checksum.
        
    Returns:
        The 16-bit checksum.
    """
    # TODO(Atul): lane 1
    raise NotImplementedError
