"""
Go-Back-N ARQ protocol implementation.
"""

from rdt.transport import Transport

class GoBackN(Transport):
    """
    Go-Back-N reliable transport protocol.
    """
    def send_file(self, file_path: str, host: str, port: int) -> None:
        """
        Send a file using Go-Back-N protocol.
        
        Args:
            file_path: Path of the file to send.
            host: Destination host.
            port: Destination port.
        """
        # TODO(Shashank): lane 2
        raise NotImplementedError

    def receive_file(self, output_path: str, port: int) -> None:
        """
        Receive a file using Go-Back-N protocol.
        
        Args:
            output_path: Path to save the received file.
            port: Port to listen on.
        """
        # TODO(Shashank): lane 2
        raise NotImplementedError

    def get_stats(self) -> dict:
        """
        Get Go-Back-N statistics.
        
        Returns:
            Dictionary containing protocol statistics.
        """
        # TODO(Shashank): lane 2
        raise NotImplementedError
