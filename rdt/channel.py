"""
Seeded channel emulator (loss, duplication, reordering, corruption, delay with jitter).
"""

class ChannelEmulator:
    """
    Emulates network conditions for the RDT project.
    """
    def __init__(self, seed: int):
        """
        Initialize the emulator with a given seed.
        
        Args:
            seed: Seed for random number generation.
        """
        # TODO(Archit): lane 4
        raise NotImplementedError

    def process_packet(self, packet: bytes) -> bytes | None:
        """
        Process a packet, applying loss, corruption, delay, or duplication.
        
        Args:
            packet: The raw packet bytes to process.
            
        Returns:
            Processed packet bytes, or None if the packet is lost.
        """
        # TODO(Archit): lane 4
        raise NotImplementedError
