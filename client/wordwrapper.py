import win32com.client as win32
import pythoncom
import win32gui
import win32process
import win32con
import win32api
from ctypes import windll, CFUNCTYPE, c_int, c_void_p, POINTER


class WordWrapper:
    def __init__(self, visible=False):
        pythoncom.CoInitialize()

        try:
            self.word = win32.GetActiveObject("Word.Application")
        except:
            try:
                self.word = win32.gencache.EnsureDispatch("Word.Application")
            except:
                raise Exception("Could not start or connect to Word application. Is word installed?")

        self.word.Visible = visible
        self.doc = None

        # event callbacks
        self.on_word_activated = None
        self.on_word_deactivated = None

        self._last_active_was_word = False

        # start listening to window focus changes
        self._start_focus_hook()

    def _is_word_window(self, hwnd):
        """Check if the foreground window belongs to WINWORD.EXE."""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            return "WINWORD.EXE" in exe_path.upper()
        except:
            return False

    def _start_focus_hook(self):
        """Hooks foreground window change."""
        WinEventProcType = CFUNCTYPE(
            None, c_void_p, c_int, c_void_p, c_int, c_int, c_int, c_int
        )

        def callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            is_word = self._is_word_window(hwnd)

            # Word just became active
            if is_word and not self._last_active_was_word:
                self._last_active_was_word = True
                if self.on_word_activated:
                    self.on_word_activated()

            # Word just got unfocused
            if not is_word and self._last_active_was_word:
                self._last_active_was_word = False
                if self.on_word_deactivated:
                    self.on_word_deactivated()

        self._win_event_proc = WinEventProcType(callback)

        windll.user32.SetWinEventHook(
            win32con.EVENT_SYSTEM_FOREGROUND,
            win32con.EVENT_SYSTEM_FOREGROUND,
            0,
            self._win_event_proc,
            0,
            0,
            win32con.WINEVENT_OUTOFCONTEXT
        )

    def list_open_docs(self):
        docs = []
        for i in range(1, self.word.Documents.Count + 1):
            docs.append(self.word.Documents.Item(i).FullName)
        return docs

    def use_active_doc(self):
        """Use the currently active Word document."""
        if self.word.Documents.Count == 0:
            raise Exception("No documents are open in Word, bro.")
        self.doc = self.word.ActiveDocument
        return self.doc

    def open_doc(self, path):
        """Open a document (or attach if already open)."""
        for i in range(1, self.word.Documents.Count + 1):
            doc = self.word.Documents.Item(i)
            if doc.FullName.lower() == path.lower():
                self.doc = doc
                return self.doc

        self.doc = self.word.Documents.Open(path)
        return self.doc
    
    def open_new_doc(self):
        """
        Creates a new blank Word document and sets it as the active doc.
        """
        self.doc = self.word.Documents.Add()
        return self.doc

    def write_end(self, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range()
        rng.InsertAfter(text)

    def write_start(self, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(0, 0)
        rng.InsertBefore(text)

    def insert_at(self, start, end, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(start, end)
        rng.Text = text

    def replace_text(self, old, new):
        if not self.doc:
            raise Exception("No document loaded bro.")
        find = self.doc.Content.Find
        find.Text = old
        find.Replacement.Text = new
        find.Execute(Replace=2)  # wdReplaceAll

    def replace_block(self, prefix="###", suffix="###", replacement="hello world"):
        """
        Replaces the first occurrence of content wrapped in prefix...suffix.
        Example: ###something### → hello world
        """

        if self.doc is None:
            raise Exception("No document loaded.")

        # Word wildcard pattern:
        # prefix + * + suffix
        pattern = f"{prefix}*{suffix}"

        find = self.doc.Content.Find
        find.Text = pattern
        find.Replacement.Text = replacement

        find.MatchWildcards = True
        find.Forward = True
        find.Wrap = 1  # wdFindContinue

        # Replace just one
        find.Execute(Replace=1)

    def get_block(self, prefix="###", suffix="###"):
        """
        Returns the text inside prefix...suffix.
        Example: ###hello there### -> 'hello there'
        Returns None if not found.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        full_text = self.doc.Content.Text

        start = full_text.find(prefix)
        if start == -1:
            return None

        start += len(prefix)

        end = full_text.find(suffix, start)
        if end == -1:
            return None

        return full_text[start:end]

    def save(self):
        if self.doc:
            self.doc.Save()

    def close_doc(self):
        if self.doc:
            self.doc.Close()
            self.doc = None

    def quit(self):
        self.word.Quit()
        self.word = None