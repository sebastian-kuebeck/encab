import os
import pwd

from typing import Dict, Optional, Callable, Any, List, Union

from subprocess import Popen, PIPE
from signal import SIGKILL, SIGTERM

from logging import Logger, INFO, ERROR
from .log_stream import LogStream
from .exit_codes import EX_NOCHILD

from pwd import getpwnam
from grp import getgrnam


def getGroupId(name: str) -> int:
    """
    returns the GID for the group name

    For details see https://docs.python.org/3.10/library/grp.html

    :param name: the group name
    :type name: str
    :return: the GID
    :rtype: int
    :raise: KeyError if the group does not exist
    """
    return getgrnam(name).gr_gid


def getUserId(name: str) -> int:
    """
    returns the UID for the user name

    for details see https://docs.python.org/3/library/pwd.html

    :param name: the user name
    :type name: str
    :return: the UID
    :rtype: int
    :raise: KeyError if the User does not exist
    """
    return getpwnam(name).pw_uid


class Process(object):
    """
    Wrapper for POpen that is backward compatible to Python 3.7.
    In addition, it supports logging of stdout and stderr
    """

    @staticmethod
    def update_current(
        user: Optional[int] = None,
        group: Optional[int] = None,
        umask: Optional[int] = None,
    ):
        """
        sets the current process user, group and umask

        :param user: the UID, defaults to None
        :type user: Optional[int], optional
        :param group: the GID, defaults to None
        :type group: Optional[int], optional
        :param umask: the mask defining the process permssions, defaults to None
        :type umask: Optional[int], optional
        :raises ValueError: The UID cannot be found in the /etc/passwd file
        """

        if group:
            os.setgid(group)

        if user and os.getuid() != user:
            try:
                user_data = pwd.getpwuid(user)
            except KeyError as e:
                raise ValueError(f"No passwd entry for user id: {user}", e)

            os.initgroups(user_data.pw_name, user_data.pw_gid)
            os.setuid(user)

        if umask and umask != -1:
            os.umask(umask)

    def __init__(
        self,
        args: Union[str, List[str]],
        environment: Dict[str, str],
        user: Optional[int] = None,
        group: Optional[int] = None,
        umask: Optional[int] = None,
        shell: bool = False,
        start_new_session: bool = True,
        cwd: Optional[str] = None,
        reap_zombies: bool = False,
    ) -> None:
        """
        Creates the Process

        For details see: https://docs.python.org/3/library/subprocess.html#subprocess.Popen

        :param args: process arguments. The first ist the program to be started
        :type args: Union[str, List[str]]
        :param environment: the process environment
        :type environment: Dict[str, str]
        :param user: the UID for the process , defaults to None
        :type user: Optional[int], optional
        :param group: the GID of the process, defaults to None
        :type group: Optional[int], optional
        :param umask: the process permissions, defaults to None
        :type umask: Optional[int], optional
        :param shell: True: the command is run within a shell, defaults to False
        :type shell: bool, optional
        :param start_new_session: True: the process is executed in its own session, defaults to True
        :type start_new_session: bool, optional
        :param cwd: the work directory, the process is run in, defaults to None
        :type cwd: Optional[str], optional
        :param reap_zombies: if True, encab will reap zombie child processes
        :type reap_zombies: bool, defaults to False
        """
        self._args = args
        self._env = environment
        self._user = user
        self._group = group
        self._umask = umask
        self._shell = shell
        self._start_new_session = start_new_session
        self._process: Optional[Popen] = None
        self._cwd = cwd
        self._reap_zombies = reap_zombies

    def _wait_and_reap_zombies(self, logger: Logger, extra: Dict[str, str]) -> int:
        """
        Waits for the process to end and reap zombies in between

        see: https://github.com/krallin/tini/blob/master/src/tini.c

        :param logger: the logger
        :type logger: Logger
        :param extra: the logger extra
        :type extra: Dict[str, str]
        """

        assert self._process
        child_process_pid = self._process.pid

        while True:
            current_pid, status = os.waitpid(-child_process_pid, os.WUNTRACED)
            if current_pid == -1:
                logger.debug("No child to wait", extra=extra)
                return EX_NOCHILD
            elif current_pid == 0:
                pass
            else:
                if current_pid == child_process_pid:
                    if os.WIFEXITED(status):
                        rc = os.waitstatus_to_exitcode(status)
                        logger.debug(
                            "Main child exited normally (with status %d, exit code %d)",
                            os.WEXITSTATUS(status),
                            rc,
                            extra=extra,
                        )
                        return rc
                    elif os.WIFSIGNALED(status):
                        logger.debug(
                            "Main child exited with signal (with signal '%s')",
                            str(os.WTERMSIG(status)),
                            extra=extra,
                        )
                        return os.waitstatus_to_exitcode(status)
                    else:
                        logger.error(
                            "Main child exited for unknown reason", extra=extra
                        )
                        return os.waitstatus_to_exitcode(status)
                else:
                    logger.warning(
                        "Reaped child with pid: %d", current_pid, extra=extra
                    )

    def execute(
        self,
        exec: Callable[[Popen], Any],
        logger: Logger,
        extra: Dict[str, str],
        stdin: Optional[int] = None,
        stdout: Optional[int] = None,
        stderr: Optional[int] = None,
    ) -> int:
        """
        Executes the process

        For details see:

        - https://docs.python.org/3/library/subprocess.html#subprocess.Popen
        - https://docs.python.org/3.10/library/subprocess.html#replacing-shell-pipeline

        :param exec: function that is called when the process has started
        :type exec: Callable[[Popen], Any]
        :param logger: the logger
        :type logger: Logger
        :param stdin: the stdin file descriptor, defaults to None
        :type stdin: Optional[int], optional
        :param stdout: the stdout file descriptor, defaults to None
        :type stdout: Optional[int], optional
        :param stderr: the stderr file descriptor, defaults to None
        :type stderr: Optional[int], optional
        :raises ValueError: The UID cannot be found in the /etc/passwd file
        :return: the process exit code
        :rtype: int
        """
        uid = self._user
        gid = self._group
        umask = self._umask

        if uid and os.getuid() != uid:
            try:
                user_data = pwd.getpwuid(uid)
            except KeyError as e:
                raise ValueError(f"No passwd entry for user id: {uid}", e)

        def preexec_fn():
            if gid:
                os.setgid(gid)

            if uid and user_data:
                os.initgroups(user_data.pw_name, user_data.pw_gid)
                os.setuid(uid)

            if umask and umask != -1:
                os.umask(umask)

        self._process = Popen(
            self._args,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=self._env,
            preexec_fn=preexec_fn,
            shell=self._shell,
            start_new_session=self._start_new_session,
            cwd=self._cwd,
        )
        exec(self._process)

        if self._reap_zombies:
            return self._wait_and_reap_zombies(logger, extra)
        else:
            self._process.wait()
            return self._process.returncode

    def execute_and_log(
        self,
        exec: Callable[[Popen], Any],
        logger: Logger,
        extra: Any,
        log_stdout: bool = True,
    ) -> int:
        """
        Executes the process and loggs stderr (log level ERROR) and optionally stdout (log level INFO)

        :param exec: function that is called when the process has started
        :type exec: Callable[[Popen], Any]
        :param logger: the logger where stderr and optionally stdout are logget to
        :type logger: Logger
        :param extra: The extra field for log messages
        :type extra: Any
        :param log_stdout: if True, srdout is logged as well, defaults to True
        :type log_stdout: bool, optional
        :return: _description_
        :rtype: int
        """

        streams: List[LogStream] = list()

        def outer_exec(process: Popen) -> None:
            assert process.stdout
            assert process.stderr

            streams.append(LogStream(logger, ERROR, process.stderr, extra).start())

            if log_stdout:
                streams.append(LogStream(logger, INFO, process.stdout, extra).start())

            exec(process)

        try:
            return self.execute(outer_exec, logger, extra, None, PIPE, PIPE)
        finally:
            for stream in streams:
                stream.wait_close()

    def pid(self) -> Optional[int]:
        """
        :return: the operating system process id or None, if the process isn't running.
        :rtype: Optional[int]
        """
        return self._process.pid if self._process and self._process.pid else None

    def if_running(self, f: Callable[[int], Any]) -> Any:
        """
        calls a function if the process is running

        :param f: a function
        :type f: Callable[[int], Any]
        :return: _description_
        :rtype: whatever is ferurned from the function
        """
        return f(self._process.pid) if self._process and self._process.pid else None

    def signal(self, signal: int):
        """
        Sends a singal to the process if it is running

        see: https://docs.python.org/3/library/signal.html#module-signal

        :param signal: the signal to be sent
        :type signal: int
        """
        try:
            self.if_running(lambda pid: os.kill(pid, signal))
        except ProcessLookupError:
            pass

    def kill(self):
        """
        Sends SIGKILL to the process if it is running

        see: https://docs.python.org/3/library/signal.html#module-signal
        """
        self.signal(SIGKILL)

    def terminate(self):
        """
        Sends SIGTERM to the process if it is running

        see: https://docs.python.org/3/library/signal.html#module-signal
        """
        self.signal(SIGTERM)
