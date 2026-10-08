"""packet.py: the packet format every protocol uses. Owner: Atul.

Header, 13 bytes, network byte order (big-endian):

    seq       4 bytes   number of this chunk (DATA packets)
    ack       4 bytes   number of the chunk being acknowledged (ACK packets)
    flags     1 byte    DATA = 1, ACK = 2, FIN = 4 (FIN marks the last chunk)
    length    2 bytes   payload length in bytes
    checksum  2 bytes   RFC 1071 checksum of the whole packet, computed with this field set to 0
"""

