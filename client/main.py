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

def start_mouse_movement():
    def move_mouse():
        while True:
            pyautogui.move(0, 1)
            time.sleep(0.1)
            pyautogui.move(0, -1)
            time.sleep(0.1)
    thread = threading.Thread(target=move_mouse, daemon=True)
    thread.start()
    return thread

def stop_mouse_movement(thread: threading.Thread):
    if thread.is_alive():
        thread.join(timeout=0)

def find_prompt_replace(word: wordwrapper.WordWrapper):
    word.make_hidden_visible()
    prompt = word.get_block("--", "--")

    if prompt is None:
        return
    prompt = prompt if isinstance(prompt, str) else prompt[0]
    r = client.send_prompt(prompt)
    if r is None:
        return
    word.replace_blocks(f"--", "--", "") #Delete prompt from document
    word.replace_block(",,", ",,", r)

def find_agent_prompt_replace(word: wordwrapper.WordWrapper):
    word.make_hidden_visible()
    prompt = word.get_block("---", "---")

    if prompt is None:
        return
    prompt = prompt if isinstance(prompt, str) else prompt[0]
    r = client.send_agent_prompt(prompt)
    if r is None:
        return
    word.replace_blocks("---", "---", "") #Delete prompt from document
    word.replace_block(",,", ",,", r)

def handle_deactivated(word: wordwrapper.WordWrapper):
    global word_is_open

    try:
        word.make_hidden_visible()
        word.replace_blocks("", ";;;", "")

        agent_prompt = word.get_block("---", "---") is not None
        prompt = word.get_block("--", "--") is not None
        command = word.get_block("::", "::")
        command = command.lower() if isinstance(command, str) else command
        
        print(prompt, agent_prompt, command)


        if agent_prompt:
            find_agent_prompt_replace(word)
        elif prompt:
            find_prompt_replace(word)
        if command is not None:
            command = command if isinstance(command, str) else command[0]
            mt = start_mouse_movement()
            commands[command]([word.get_block(",,", ",,")])
            word.replace_blocks("::", "::", "")
            stop_mouse_movement(mt)
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
