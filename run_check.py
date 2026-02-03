#Closes the program if it is already running
import msvcrt
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
import run_check

lock_file = open(f"%TEMP%/script.lock", "w")

try:
    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print("Script is already running.")
    sys.exit(0)