from abc import ABC, abstractmethod

class PicoConnection(ABC):
    """
    Abstract base class defining the standard interface for communicating
    with the Zx50 Pico firmware, regardless of the physical medium.
    """

    @abstractmethod
    def connect(self) -> None:
        """
        Establishes the physical/network connection, flushes any
        leftover boot buffers, and syncs up with the initial 'Zx50>' prompt.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Sends the 'BYE' command (if applicable) and cleanly
        closes the port or socket.
        """
        pass

    @abstractmethod
    def send_cmd(self, cmd: str) -> str:
        """
        Sends a string command, reads the stream until the 'Zx50>' prompt
        returns, and extracts the 'OK' or 'ERR' response line.
        """
        pass