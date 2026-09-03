"""
Selective Repeat ARQ protocol implementation.
"""

from rdt.transport import Transport

class SelectiveRepeat(Transport):
    """
    Selective Repeat reliable transport protocol.
    """
    def send_file(self, file_path: str, host: str, port: int) -> None:
        """
        Send a file using Selective Repeat protocol.
        
        Args:
            file_path: Path of the file to send.
            host: Destination host.
            port: Destination port.
        """
        # TODO(Aqifa): lane 3
        raise NotImplementedError

    def receive_file(self, output_path: str, port: int) -> None:
        """
        Receive a file using Selective Repeat protocol.
        
        Args:
            output_path: Path to save the received file.
            port: Port to listen on.
        """
        # TODO(Aqifa): lane 3
        raise NotImplementedError

    def get_stats(self) -> dict:
        """
        Get Selective Repeat statistics.
        
        Returns:
            Dictionary containing protocol statistics.
        """
        # TODO(Aqifa): lane 3
        raise NotImplementedError
