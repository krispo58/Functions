import win32com.client as win32
import pythoncom
import win32gui
import win32process
import win32con
import win32api
import ctypes
from ctypes import wintypes
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
                    self.on_word_activated(self)

            # Word just got unfocused
            if not is_word and self._last_active_was_word:
                self._last_active_was_word = False
                if self.on_word_deactivated:
                    self.on_word_deactivated(self)

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

    def try_reconnect(self):
        try:
            self.word = win32.GetActiveObject("Word.Application")
            self.use_active_doc()
            return True
        except:
            return False

    def flash_taskbar(self, count: int = 3):
        """
        Triggers a taskbar attention flash on the Word icon.
        Works even if Word is minimized and COM doesn't expose Hwnd.
        """

        # Find Word's main window (class name is always 'OpusApp')
        hwnd = win32gui.FindWindow("OpusApp", None)
        if not hwnd:
            return False

        FLASHW_ALL = 3
        FLASHW_TIMERNOFG = 12

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        info = FLASHWINFO(
            cbSize=ctypes.sizeof(FLASHWINFO),
            hwnd=hwnd,
            dwFlags=FLASHW_ALL | FLASHW_TIMERNOFG,
            uCount=count,
            dwTimeout=0,
        )

        return ctypes.windll.user32.FlashWindowEx(ctypes.byref(info)) != 0

    def get_text(self, start: int = None, end: int = None) -> str:
        """Get text from the document or range."""
        if not self.doc:
            raise Exception("No document loaded bro.")

        if start is None or end is None:
            rng = self.doc.Content
        else:
            rng = self.doc.Range(start, end)

        return rng.Text

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
        rng.Font.Hidden = False
        rng.InsertAfter(text)

    def write_start(self, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(0, 0)
        rng.Font.Hidden = False
        rng.InsertBefore(text)

    def insert_at(self, start, end, text):
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Range(start, end)
        rng.Font.Hidden = False
        rng.Text = text

    def replace_text(self, old, new):
        """
        Replaces all occurrences of old text with new text.
        Works with long replacement text by using Range.Text instead of Find.Replacement.
        """
        if not self.doc:
            raise Exception("No document loaded bro.")
        
        rng = self.doc.Content
        full_text = rng.Text
        
        # If old text not found, return early
        if old not in full_text:
            return False
        
        # Find and replace each occurrence
        while True:
            full_text = self.doc.Content.Text
            start_idx = full_text.find(old)
            
            if start_idx == -1:
                break
            
            # Replace using Range.Text for long text support
            replace_rng = self.doc.Range(start_idx, start_idx + len(old))
            replace_rng.Font.Hidden = False
            replace_rng.Text = new
        
        return True

    def replace_blocks(self, prefix="###", suffix="###", replacement="hello world"):
        """
        Replaces all occurrences of content wrapped in prefix...suffix.
        Works with large replacement text.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        replaced_count = 0
        
        while True:
            rng = self.doc.Content
            full_text = rng.Text

            start_idx = full_text.find(prefix)
            if start_idx == -1:
                break

            end_idx = full_text.find(suffix, start_idx + len(prefix))
            if end_idx == -1:
                break

            replace_rng = self.doc.Range(start_idx, end_idx + len(suffix))
            replace_rng.Font.Hidden = False
            replace_rng.Text = replacement
            replaced_count += 1

        return replaced_count

    def get_blocks(self, prefix="###", suffix="###", ):
        """
        Returns a list of all text content inside prefix...suffix blocks.
        Returns None list if none found.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text
        
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

        if len(blocks) == 0:
            return None

        return blocks

    def replace_block(self, prefix="###", suffix="###", replacement="hello world"):
        """
        Replaces the first occurrence of content wrapped in prefix...suffix.
        Works with large replacement text.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text

        start_idx = full_text.find(prefix)
        if start_idx == -1:
            return False

        end_idx = full_text.find(suffix, start_idx + len(prefix))
        if end_idx == -1:
            return False

        replace_rng = self.doc.Range(start_idx, end_idx + len(suffix))
        replace_rng.Font.Hidden = False
        replace_rng.Text = replacement

        return True

    def get_block(self, prefix="###", suffix="###"):
        """
        Returns the text inside  the first occurance of prefix...suffix.
        Returns None if not found.
        """
        if self.doc is None:
            raise Exception("No document loaded.")

        rng = self.doc.Content
        full_text = rng.Text

        start = full_text.find(prefix)
        if start == -1:
            return None

        start += len(prefix)
        end = full_text.find(suffix, start)
        if end == -1:
            return None

        return full_text[start:end]

    def make_hidden_visible(self):
        """Makes all hidden text in the document visible."""
        if not self.doc:
            raise Exception("No document loaded bro.")
        rng = self.doc.Content
        rng.Font.Hidden = False

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