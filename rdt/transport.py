"""
Abstract Transport interface and shared monotonic timer-heap event loop skeleton.
"""

class Transport:
    """
    Abstract base class for all RDT protocols.
    """
    def send_file(self, file_path: str, host: str, port: int) -> None:
        """
        Send a file reliably over UDP.
        
        Args:
            file_path: Path of the file to send.
            host: Destination host.
            port: Destination port.
        """
        # TODO(Atul): lane 1
        raise NotImplementedError

    def receive_file(self, output_path: str, port: int) -> None:
        """
        Receive a file reliably over UDP.
        
        Args:
            output_path: Path to save the received file.
            port: Port to listen on.
        """
        # TODO(Atul): lane 1
        raise NotImplementedError

    def get_stats(self) -> dict:
        """
        Retrieve transport statistics.
        
        Returns:
            Dictionary containing protocol statistics.
        """
        # TODO(Atul): lane 1
        raise NotImplementedError

def run_event_loop() -> None:
    """
    Run the shared monotonic timer-heap event loop.
    """
    # TODO(Atul): lane 1
    raise NotImplementedError
