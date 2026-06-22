"""Background task runner utility for non-blocking operations."""
import threading
from typing import Callable, Any, Tuple, Dict, Optional


class BackgroundTask:
    """A helper class to execute long-running tasks in a background thread."""

    def __init__(self, target: Callable, args: Tuple = (), kwargs: Optional[Dict[str, Any]] = None):
        """Initialize background task.

        Args:
            target: Function to execute.
            args: Positional arguments for target.
            kwargs: Keyword arguments for target.
        """
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.thread: Optional[threading.Thread] = None
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.is_running: bool = False
        self.is_done: bool = False

    def start(self) -> None:
        """Start execution in a daemon thread."""
        self.is_running = True
        self.is_done = False
        self.result = None
        self.error = None
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self) -> None:
        """Execute target function and capture result or error."""
        try:
            self.result = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self.error = e
        finally:
            self.is_running = False
            self.is_done = True
