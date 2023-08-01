import os
import pwd

from typing import Dict, Optional, Callable, Any, List, Union

from subprocess import Popen, PIPE
from signal import SIGKILL, SIGTERM

from logging import Logger, INFO, ERROR
from .log_stream import LogStream

from pwd import getpwnam
from grp import getgrnam

def getGroupId(name: str) -> int:
    """
    returns the GID for the group name

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

    :param name: the user name
    :type name: str
    :return: the UID
    :rtype: int 
    :raise: KeyError if the User does not exist
    """
    return getpwnam(name).pw_uid


class Process(object):
    """
    Wrapper for POpen that supports logging of stdout and stdin
    """
    
    @staticmethod
    def update_current(user: Optional[int] = None, 
                       group: Optional[int] = None, 
                       umask: Optional[int] = None):
        """
        sets the current process user, group and umask

        :param user: the UID, defaults to None
        :type user: Optional[int], optional
        :param group: the GID, defaults to None
        :type group: Optional[int], optional
        :param umask: the mask, defaults to None
        :type umask: Optional[int], optional
        :raises ValueError: _description_
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

    
    def __init__(self, 
                 args:Union[str, List[str]], 
                 environment: Dict[str, str], 
                 user: Optional[int] = None, 
                 group: Optional[int] = None, 
                 umask: Optional[int] = None, 
                 shell: bool=False,
                 start_new_session: bool=True,
                 cwd: Optional[str] = None) -> None:
        self._args = args
        self._env = environment
        self._user = user
        self._group = group
        self._umask = umask
        self._shell = shell
        self._start_new_session = start_new_session
        self._process: Optional[Popen] = None
        self._cwd = cwd
        
    def execute(self, 
                exec: Callable[[Popen], Any], 
                stdin: Optional[int] = None, 
                stdout: Optional[int] = None, 
                stderr: Optional[int] = None) -> int:
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
                cwd=self._cwd
            )
        exec(self._process)
        self._process.wait()
        return self._process.returncode

    def execute_and_log(self, 
                exec: Callable[[Popen], Any], 
                logger: Logger,
                extra: Any, 
                log_stdout:bool=True) -> int:

        streams: List[LogStream] = list()

        def outer_exec(process: Popen) -> None:
            assert process.stdout
            assert process.stderr
            
            streams.append(LogStream(logger, ERROR, process.stderr, extra).start())
            
            if log_stdout:
                streams.append(LogStream(logger, INFO, process.stdout, extra).start())

            exec(process)

        try:
            return self.execute(outer_exec, None, PIPE, PIPE)
        finally:
            for stream in streams:
                stream.close()
    
    
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process and self._process.pid else None
    
    def if_running(self, f: Callable[[int], Any]) -> Any:
        return f(self._process.pid) if self._process and self._process.pid else None
                    
    def signal(self, signal: int):
        try:
            self.if_running(lambda pid: os.kill(pid, signal))
        except ProcessLookupError:
            pass
    
    def kill(self):
        self.signal(SIGKILL)
        
    def terminate(self):
        self.signal(SIGTERM)

    
    