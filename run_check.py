#Closes the program if it is already running
import msvcrt
import sys

lock_file = open("script.lock", "w")

try:
    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print("Script is already running.")
    sys.exit(0)