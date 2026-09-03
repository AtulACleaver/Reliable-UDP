"""
Stop-and-Wait ARQ protocol implementation.
"""

from rdt.transport import Transport

class StopAndWait(Transport):
    """
    Stop-and-Wait reliable transport protocol.
    """
    def send_file(self, file_path: str, host: str, port: int) -> None:
        """
        Send a file using Stop-and-Wait protocol.
        
        Args:
            file_path: Path of the file to send.
            host: Destination host.
            port: Destination port.
        """
        # TODO(Atul): lane 1
        raise NotImplementedError

    def receive_file(self, output_path: str, port: int) -> None:
        """
        Receive a file using Stop-and-Wait protocol.
        
        Args:
            output_path: Path to save the received file.
            port: Port to listen on.
        """
        # TODO(Atul): lane 1
        raise NotImplementedError

    def get_stats(self) -> dict:
        """
        Get Stop-and-Wait statistics.
        
        Returns:
            Dictionary containing protocol statistics.
        """
        # TODO(Atul): lane 1
        raise NotImplementedError
