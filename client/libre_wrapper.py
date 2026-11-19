"""
LibreOffice Writer counterpart of wordwrapper.py (Windows).

LibreWriter exposes the same methods as WordWrapper (use_active_doc,
open_new_doc, write_start, write_end, replace_text, replace_blocks,
get_block, replace_block, make_hidden_visible, try_reconnect, ...) and the
same on_word_activated / on_word_deactivated callbacks, so libre_main.py can
be a straight copy of main.py. It edits the live document through UNO, so
nothing has to be saved.

LibreOffice ships its own Python with UNO. bootstrap_or_continue() re-runs the
calling script under that Python when the current one has no UNO.
"""
import ctypes
import glob
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

HOST = "localhost"
PORT = 2002
CHUNK = 30000  # goRight() takes a signed 16-bit count


# --------------------------------------------------------------------------
# Locating LibreOffice / bootstrapping into its bundled Python
# --------------------------------------------------------------------------
def find_program_dir():
    """Return LibreOffice's 'program' directory, or None."""
    candidates = []
    if os.environ.get("LIBREOFFICE_PATH"):
        candidates.append(os.environ["LIBREOFFICE_PATH"])
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            candidates += glob.glob(os.path.join(base, "LibreOffice*", "program"))
    soffice = shutil.which("soffice")
    if soffice:
        candidates.append(os.path.dirname(os.path.realpath(soffice)))

    for path in candidates:
        if os.path.exists(os.path.join(path, "soffice.exe")):
            return path
    return None


def have_uno() -> bool:
    try:
        import uno  # noqa: F401
        return True
    except ImportError:
        return False


def bootstrap_or_continue():
    """Make sure we run under a Python that has UNO; re-exec if needed."""
    if have_uno():
        return

    program_dir = find_program_dir()
    if not program_dir:
        sys.exit("LibreOffice not found. Install it, or set LIBREOFFICE_PATH to its "
                 "'program' folder (e.g. C:\\Program Files\\LibreOffice\\program).")
    py = os.path.join(program_dir, "python.exe")
    if not os.path.exists(py):
        sys.exit(f"No bundled Python in {program_dir}. Reinstall LibreOffice with the "
                 "default components.")

    if "--setup" in sys.argv:
        print(f"Installing dependencies into {py} ...")
        # LibreOffice's Python usually already ships pip; only bootstrap if missing.
        pip_ok = subprocess.call([py, "-m", "pip", "--version"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        if not pip_ok:
            subprocess.call([py, "-m", "ensurepip", "--upgrade"])
        sys.exit(subprocess.call([py, "-m", "pip", "install", "--no-warn-script-location",
                                  "requests", "psutil"]))

    # Re-run the calling script under LibreOffice's Python.
    script = os.path.abspath(sys.argv[0])
    kwargs = {}
    if os.path.basename(sys.executable).lower() == "pythonw.exe":
        # Started windowless (pythonw): stay windowless. Use LibreOffice's own pythonw.exe
        # if it ships one; many installs only have python.exe, so also suppress its console
        # window and give it null stdio (pythonw has no console handles to inherit).
        pyw = os.path.join(program_dir, "pythonw.exe")
        if os.path.exists(pyw):
            py = pyw
        kwargs = dict(creationflags=subprocess.CREATE_NO_WINDOW,
                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.exit(subprocess.call([py, script] + sys.argv[1:], **kwargs))


# --------------------------------------------------------------------------
# UNO connection
# --------------------------------------------------------------------------
def _try_connect(port: int):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local)
    ctx = resolver.resolve(
        f"uno:socket,host={HOST},port={port};urp;StarOffice.ComponentContext")
    return ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)


def connect(port: int = PORT, launch: bool = True, timeout: float = 40.0):
    """Connect to Writer, launching it if needed. Returns the Desktop object."""
    try:
        return _try_connect(port)
    except Exception:
        if not launch:
            raise

    program_dir = find_program_dir()
    if not program_dir:
        raise RuntimeError("LibreOffice not found (set LIBREOFFICE_PATH).")

    print("Starting LibreOffice Writer...")
    subprocess.Popen([
        os.path.join(program_dir, "soffice.exe"), "--writer", "--norestore",
        f"--accept=socket,host={HOST},port={port};urp;",
    ])

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        try:
            return _try_connect(port)
        except Exception:
            continue
    raise RuntimeError(
        "Could not connect to LibreOffice. If it was already open, close all its "
        "windows and try again.")


# Exceptions that mean "Writer went away" (the equivalent of pywintypes.com_error).
_DISCONNECT_NAMES = ("DisposedException", "NoConnectException", "ConnectException",
                     "RuntimeException", "IllegalArgumentException")


def is_disconnect(error: BaseException) -> bool:
    return (type(error).__name__ in _DISCONNECT_NAMES
            or isinstance(error, (ConnectionError, OSError)))


# --------------------------------------------------------------------------
# Foreground-window detection (is the focused window LibreOffice?)
# --------------------------------------------------------------------------
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _foreground_is_writer() -> bool:
    """True if the foreground window belongs to LibreOffice (soffice)."""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return False
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return False
            return os.path.basename(buf.value).lower() in ("soffice.exe", "soffice.bin")
        finally:
            _kernel32.CloseHandle(handle)
    except Exception:
        return False


def _normalize(text: str) -> str:
    """Writer uses \\n for paragraph breaks."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


# --------------------------------------------------------------------------
# The wrapper
# --------------------------------------------------------------------------
class LibreWriter:
    def __init__(self, visible=True, port: int = PORT):
        self.port = port
        self.desktop = connect(port)  # always visible; `visible` kept for API parity
        self.doc = None

        # event callbacks
        self.on_word_activated = None
        self.on_word_deactivated = None

        self._last_active_was_word = False

    # --- focus events (call poll() regularly; replaces the Win32 event hook) ---
    def poll(self):
        """Fire on_word_activated / on_word_deactivated on focus changes."""
        is_word = _foreground_is_writer()

        # Writer just became active
        if is_word and not self._last_active_was_word:
            self._last_active_was_word = True
            if self.on_word_activated:
                self.on_word_activated(self)

        # Writer just got unfocused
        if not is_word and self._last_active_was_word:
            self._last_active_was_word = False
            if self.on_word_deactivated:
                self.on_word_deactivated(self)

    def try_reconnect(self):
        try:
            self.desktop = connect(self.port, launch=False)
            self.use_active_doc()
            return True
        except Exception:
            return False

    # --- documents ---
    @staticmethod
    def _is_writer_doc(doc) -> bool:
        return doc is not None and doc.supportsService("com.sun.star.text.TextDocument")

    def list_open_docs(self):
        docs = []
        components = self.desktop.getComponents().createEnumeration()
        while components.hasMoreElements():
            doc = components.nextElement()
            if self._is_writer_doc(doc):
                docs.append(doc.getURL() or doc.getTitle())
        return docs

    def use_active_doc(self):
        """Use the currently active Writer document."""
        doc = self.desktop.getCurrentComponent()
        if not self._is_writer_doc(doc):
            doc = None
            components = self.desktop.getComponents().createEnumeration()
            while components.hasMoreElements():
                candidate = components.nextElement()
                if self._is_writer_doc(candidate):
                    doc = candidate
                    break
        if doc is None:
            raise Exception("No Writer documents are open.")
        self.doc = doc
        return self.doc

    def open_doc(self, path):
        """Open a document (or attach if already open)."""
        import uno
        url = uno.systemPathToFileUrl(os.path.abspath(path))
        components = self.desktop.getComponents().createEnumeration()
        while components.hasMoreElements():
            doc = components.nextElement()
            if self._is_writer_doc(doc) and doc.getURL() == url:
                self.doc = doc
                return self.doc
        self.doc = self.desktop.loadComponentFromURL(url, "_blank", 0, ())
        return self.doc

    def open_new_doc(self):
        """Creates a new blank Writer document and sets it as the active doc."""
        self.doc = self.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        return self.doc

    def save(self):
        if self.doc:
            self.doc.store()

    def close_doc(self):
        if self.doc:
            self.doc.close(True)
            self.doc = None

    def quit(self):
        self.desktop.terminate()
        self.desktop = None

    # --- low-level editing helpers ---
    def _require_doc(self):
        if self.doc is None:
            raise Exception("No document loaded.")

    def _cursor_at(self, pos: int):
        cursor = self.doc.getText().createTextCursor()
        cursor.gotoStart(False)
        while pos > 0:
            step = min(pos, CHUNK)
            cursor.goRight(step, False)
            pos -= step
        return cursor

    def _replace_range(self, start: int, end: int, new: str):
        """Replace characters [start, end) with `new`, making the result visible."""
        cursor = self._cursor_at(start)
        remaining = end - start
        while remaining > 0:
            step = min(remaining, CHUNK)
            cursor.goRight(step, True)
            remaining -= step
        cursor.CharHidden = False
        cursor.setString(_normalize(new))
        cursor.CharHidden = False  # setString leaves the new text selected

    # --- reading ---
    def get_text(self, start: int = None, end: int = None) -> str:
        """Get text from the document or range."""
        self._require_doc()
        # getString() renders a real paragraph break (Enter, pasted paragraphs) as
        # "\r\n" - two characters - but the text cursor counts it as ONE position.
        # Every offset computed from the string would then drift by one per
        # paragraph, so edits (e.g. deleting the prompt) hit the wrong characters.
        # Normalising to "\n" keeps string indexes identical to cursor positions.
        text = self.doc.getText().getString().replace("\r\n", "\n")
        if start is None or end is None:
            return text
        return text[start:end]

    def get_blocks(self, prefix="###", suffix="###"):
        """
        Returns a list of all text content inside prefix...suffix blocks.
        Returns None if none found.
        """
        self._require_doc()
        full_text = self.get_text()

        blocks = []
        search_pos = 0
        while True:
            start = full_text.find(prefix, search_pos)
            if start == -1:
                break
            start += len(prefix)
            end = full_text.find(suffix, start)
            if end == -1:
                break
            blocks.append(full_text[start:end])
            search_pos = end + len(suffix)

        return blocks or None

    def get_block(self, prefix="###", suffix="###"):
        """
        Returns the text inside the first occurrence of prefix...suffix.
        Returns None if not found.
        """
        self._require_doc()
        full_text = self.get_text()

        start = full_text.find(prefix)
        if start == -1:
            return None
        start += len(prefix)
        end = full_text.find(suffix, start)
        if end == -1:
            return None
        return full_text[start:end]

    # --- writing ---
    def write_end(self, text):
        self._require_doc()
        cursor = self.doc.getText().createTextCursor()
        cursor.gotoEnd(False)
        cursor.CharHidden = False
        self.doc.getText().insertString(cursor, _normalize(text), True)
        cursor.CharHidden = False

    def write_start(self, text):
        self._require_doc()
        cursor = self.doc.getText().createTextCursor()
        cursor.gotoStart(False)
        cursor.CharHidden = False
        self.doc.getText().insertString(cursor, _normalize(text), True)
        cursor.CharHidden = False

    def insert_at(self, start, end, text):
        self._require_doc()
        self._replace_range(start, end, text)

    def replace_text(self, old, new):
        """Replaces all occurrences of old text with new text."""
        self._require_doc()
        if old not in self.get_text():
            return False

        search_from = 0
        while True:
            start_idx = self.get_text().find(old, search_from)
            if start_idx == -1:
                break
            self._replace_range(start_idx, start_idx + len(old), new)
            # Continue after the replacement so a `new` containing `old` can't loop forever.
            search_from = start_idx + len(_normalize(new))
        return True

    def replace_blocks(self, prefix="###", suffix="###", replacement="hello world"):
        """Replaces all occurrences of content wrapped in prefix...suffix."""
        self._require_doc()
        replaced_count = 0

        while True:
            full_text = self.get_text()

            start_idx = full_text.find(prefix)
            if start_idx == -1:
                break
            end_idx = full_text.find(suffix, start_idx + len(prefix))
            if end_idx == -1:
                break

            self._replace_range(start_idx, end_idx + len(suffix), replacement)
            replaced_count += 1

        return replaced_count

    def replace_block(self, prefix="###", suffix="###", replacement="hello world"):
        """Replaces the first occurrence of content wrapped in prefix...suffix."""
        self._require_doc()
        full_text = self.get_text()

        start_idx = full_text.find(prefix)
        if start_idx == -1:
            return False
        end_idx = full_text.find(suffix, start_idx + len(prefix))
        if end_idx == -1:
            return False

        self._replace_range(start_idx, end_idx + len(suffix), replacement)
        return True

    def make_hidden_visible(self):
        """Makes all hidden text in the document visible."""
        self._require_doc()
        cursor = self.doc.getText().createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        cursor.CharHidden = False
