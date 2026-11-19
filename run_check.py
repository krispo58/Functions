"""
Single-instance guard.

Ensures only one copy of the calling script is running at a time by taking
an exclusive lock on a file in the OS temp directory. Import this module
(before doing anything else) from an entry-point script that must not run
twice concurrently.
"""
import msvcrt
import os
import sys
import tempfile

_lock_file = None


def acquire_lock(name: str = "script.lock") -> bool:
    """
    Try to acquire the single-instance lock.

    Returns True if the lock was acquired (no other instance is running),
    False if another instance already holds it. Keeps the file handle open
    for the lifetime of the process; the OS releases the lock automatically
    on exit.
    """
    global _lock_file

    lock_path = os.path.join(tempfile.gettempdir(), name)

    try:
        _lock_file = open(lock_path, "w")
        msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        if _lock_file:
            _lock_file.close()
            _lock_file = None
        return False


# Importing this module at the top of a script enforces single-instance
# behavior immediately, exiting the process if another instance is running.
if not acquire_lock():
    print("Script is already running.")
    sys.exit(0)
