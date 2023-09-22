"""
Linux /usr/include/sysexits.h
"""

EX_OK = 0  # successful termination
EX_DATAERR = 65  # data format error
EX_NOINPUT = 66  # cannot open input
EX_UNAVAILABLE = 69  # service unavailable
EX_SOFTWARE = 70  # internal software error
EX_OSERR = 71  # system error (e.g., can't fork) */
EX_IOERR = 74  # input/output error */
EX_NOPERM = 77  # permission denied
EX_CONFIG = 78  # configuration error

EX_NOCHILD = EX_OSERR  # Child process could not be launched
EX_UNKNOWN_RC = EX_OSERR  # Return code of main program could not be determined
EX_IOERROR = EX_IOERR  # I/O Error, e.g. reading config
EX_CONFIG_ERROR = EX_CONFIG  # Configuration error
EX_INSUFFICIENT_PERMISSIONS = EX_NOPERM  # Insufficient permissions to set UID or GID
EX_INTERRUPTED = EX_OK  # Encab was interrupted
EX_TERMINATED = EX_OK  # Encab was terminated
