import argparse
import importlib.util
import os
import sys

# server.py, llmapi.py and api_key.py live in this folder and import each other
# by plain name, so this folder must be on sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Load server.py by path. A plain `import server` is ambiguous: when started via
# run_server.py it resolves to this *package folder* (which has no Server class).
_spec = importlib.util.spec_from_file_location("server_impl", os.path.join(_HERE, "server.py"))
networkserver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(networkserver)


def harden_console():
    """
    Make the console unable to freeze or crash the server.
      - QuickEdit: on Windows, clicking in the console window pauses every
        print() (and so the whole server) until a key is pressed. Turn it off.
      - Encoding: printing text the console encoding can't represent (emoji,
        Norwegian quotes, ...) raises UnicodeEncodeError, which used to turn a
        successful LLM answer into an error. Replace instead of raising.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            STD_INPUT_HANDLE = -10
            ENABLE_QUICK_EDIT_MODE = 0x0040
            ENABLE_EXTENDED_FLAGS = 0x0080
            handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
                kernel32.SetConsoleMode(handle, new_mode)
        except Exception:
            pass


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", action="store_true",
                        help="run as a backup server: same as normal, but on the backup "
                             "channel; clients switch to it with ::backupserver::")
    args, _ = parser.parse_known_args()

    harden_console()
    os.environ["FIREBASE_PROJECT_ID"] = "my-awesome-project-3c43d"


    server = networkserver.Server(debug=True, backup=args.backup)

    server.start()

if __name__ == "__main__":
    run()
