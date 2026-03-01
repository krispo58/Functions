import time
import client as networkclient
import wordwrapper
import pythoncom
import pywintypes
import os
import notifier
import threading
import pyautogui


os.environ["FIREBASE_PROJECT_ID"] = "my-awesome-project-3c43d"

#server_ip ="51.175.238.64"
#server_port = 7777
#domain = "ordbokene.no"

word = wordwrapper.WordWrapper(visible=True)
client = networkclient.Client()
word_is_open = True
stop = False

def reset(args: list[str]):
    if _with_mouse_activity(client.new_chat):
        word.write_start("word")
    else:
        word.write_start("sentence")


def test(args: list[str]):
    word.write_end("t")
    word.replace_text("::test::", "")

def stop_program(args: list[str]):
    global stop
    stop = True

commands = {
    "stop": stop_program,
    "new": reset,
    "reset": reset,
    "test": test
}

def _keep_mouse_active(stop_event: threading.Event):
    """Move mouse slightly to keep system active during pending operations."""
    try:
        offset = 0
        while not stop_event.is_set():
            # Move mouse slightly (3 pixels) in alternating directions
            current_x, current_y = pyautogui.position()
            new_x = current_x + (3 if offset % 2 == 0 else -3)
            pyautogui.moveTo(new_x, current_y, duration=0.1)
            offset += 1
            
            # Check every 2 seconds if operation is complete
            if stop_event.wait(timeout=2):
                break
    except Exception as e:
        print(f"Mouse movement error: {e}")

def _with_mouse_activity(func, *args, **kwargs):
    """Wrapper to execute a function while keeping mouse active."""
    stop_event = threading.Event()
    mouse_thread = threading.Thread(target=_keep_mouse_active, args=(stop_event,), daemon=True)
    mouse_thread.start()
    
    try:
        result = func(*args, **kwargs)
    finally:
        stop_event.set()
        mouse_thread.join(timeout=1)
    
    return result

def find_prompt_replace(word: wordwrapper.WordWrapper):
    word.make_hidden_visible()
    prompt = word.get_block("--", "--")
    prompt = prompt if isinstance(prompt, str) else prompt[0]

    if prompt is None:
        return
    r = _with_mouse_activity(client.send_prompt, prompt)
    word.replace_blocks(f"--", "--", "") #Delete prompt from document
    word.replace_block(",,", ",,", r)

def handle_deactivated(word: wordwrapper.WordWrapper):
    global word_is_open

    try:
        word.make_hidden_visible()
        word.replace_blocks("", ";;;", "")

        prompt = word.get_block("--", "--") is not None
        command = word.get_block("::", "::").lower()
        
        print(prompt, command)


        if prompt:
                find_prompt_replace(word)
        if command is not None:
            command = command if isinstance(command, str) else command[0]
            commands[command]([word.get_block(",,", ",,")])
            word.replace_blocks("::", "::", "")
        print("Flashing taskbar")
        notifier.notify()
    except pywintypes.com_error as e:
        print("Word disconnected, waiting for reconnect...")
        print(e)
        word_is_open = False

def main():
    global word_is_open
    pythoncom.CoInitialize()
    
    try:
        word.use_active_doc()
    except Exception:
        word.open_new_doc()

    #Test dns connection
    result = _with_mouse_activity(client.ack)
    if not result:
        raise Exception("Couldn't connect to server.")
    print("Connection successful")
    if not _with_mouse_activity(client.new_chat):
        print("Could not create new chat on server. Answers may be off.")
    print("Ready")

    res_text = "word\r\n" if result else "sentence\r\n"
    word.write_start(res_text)

    word.on_word_deactivated = handle_deactivated

    while not stop:
        while word_is_open:
            #Main loop
            if stop:
                break
            pythoncom.PumpWaitingMessages()

        #If execution reaches here, word got disconnected
        while True:
            if stop:
                break
            time.sleep(1)
            if word.try_reconnect():
                print("Word reconnected")
                word.write_start(res_text)
                word_is_open = True
                break
            print("Failed to reconnect")

if __name__ == "__main__":
    main()