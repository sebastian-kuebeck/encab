import sys

from typing import Dict, Optional, IO

from threading import Thread, Event

from logging import Logger


class LogStream(object):
    """
    Reads from a stream in a background thread and logs the result line by line
    """

    def __init__(
        self, logger: Logger, log_level: int, stream: IO[bytes], extra: Dict[str, str]
    ) -> None:
        """
        :param Logger logger: the logger to which the stream content is written
        :param int log_level: the log level (see Python logging)
        :param IOBase stream: the stream that is logged
        :param Dict[str, str] extra: extra information that is logged each line (see Python logging)
        """
        self.logger = logger
        self.log_level = log_level
        self.stream = stream
        self.extra = extra
        self.thread: Optional[Thread] = None
        self._closed = Event()

    def _run(self):
        try:
            for line in self.stream:
                strline = line.decode(sys.getdefaultencoding()).rstrip("\r\n\t ")
                self.logger.log(self.log_level, strline, extra=self.extra)
        except ValueError:
            pass  # stream was closed
        except OSError:
            self.logger.exception(
                "I/O Error while logging: %s", self.name, extra=self.extra  # type: ignore
            )
        except:
            self.logger.exception(
                "Something went wrong while logging", extra=self.extra
            )
            raise
        finally:
            self.stream.close()
            self._closed.set()

    def start(self):
        """starts reading and logging"""
        program = self.extra.get("program", "")
        name = f"{program}:{self.log_level}"
        thread = Thread(target=lambda: self._run(), name=name)
        thread.daemon = True
        self.thread = thread
        thread.start()
        return self

    def wait_close(self, wait_time: float = 1.0):
        """
        waits untill the stream closes or a timeout occurs

        :param wait_time: timeout in seconds, defaults to 1.0
        :type wait_time: float, optional
        """
        try:
            if self.thread:
                self._closed.wait(wait_time)
        except IOError:
            pass
