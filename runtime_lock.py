"""Small cross-process file lock used by Desktop runtime jobs."""
from __future__ import annotations

import os
from pathlib import Path


class RuntimeLock:
    def __init__(self, path):
        self.path=Path(path)
        self.stream=None

    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        stream=open(self.path,'a+b')
        stream.seek(0)
        if not stream.read(1):
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise RuntimeError('Một tiến trình NetworkAutomation khác đang dùng cùng tài nguyên này.') from None
        self.stream=stream
        return self

    def __exit__(self,*args):
        if not self.stream:
            return
        if os.name=='nt':
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
        self.stream.close()
        self.stream=None
