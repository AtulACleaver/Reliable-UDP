"""
Jacobson/Karels estimator and Karn's algorithm for adaptive RTO.
"""

class RTOEstimator:
    """
    Estimator for Retransmission TimeOut using Jacobson/Karels and Karn's algorithm.
    """
    def update(self, rtt: float) -> None:
        """
        Update the RTO estimate given a new RTT sample.
        
        Args:
            rtt: The measured Round Trip Time for an un-retransmitted packet.
        """
        # TODO(Archit): lane 4
        raise NotImplementedError

    def get_rto(self) -> float:
        """
        Get the current RTO value.
        
        Returns:
            The estimated Retransmission TimeOut.
        """
        # TODO(Archit): lane 4
        raise NotImplementedError
        
    def backoff(self) -> None:
        """
        Backoff the RTO (e.g. upon a timeout).
        """
        # TODO(Archit): lane 4
        raise NotImplementedError
