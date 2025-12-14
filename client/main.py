import time
import client as networkclient
import wordwrapper
import pythoncom
import pywintypes


server_ip = "51.175.238.64"
server_port = 7777
domain = "ordbokene.no"

word = wordwrapper.WordWrapper(visible=True)
client = networkclient.Client(server_ip, server_port, domain)
word_is_open = True


def reset(args: list[str]):
    client.new_chat()

def test(args: list[str]):
    word.write_end("t")
    word.replace_text("::test::", "")

commands = {
    "reset": reset,
    "test": test
}
def find_prompt_replace(word: wordwrapper.WordWrapper):
    word.make_hidden_visible()
    prompt = word.get_block("-", "-")
    if prompt is None:
        return
    r = client.send_prompt(prompt)
    word.replace_block(",,", ",,", r)
    word.replace_text(f"-{prompt}-", "") #Delete prompt from document

def handle_deactivated(word: wordwrapper.WordWrapper):
    global word_is_open

    prompt = word.get_block("--", "--") is not None
    command = word.get_block("::", "::")

    try:
        if prompt:
                find_prompt_replace(word)
                print("Flashing taskbar")
                word.flash_taskbar(1)
        if command is not None:
            commands[command]([word.get_block(",,", ",,")])
    except pywintypes.com_error as e:
        print("Word disconnected, waiting for reconnect...")
        word_is_open = False

def main():
    global word_is_open
    pythoncom.CoInitialize()
    
    try:
        word.use_active_doc()
    except Exception:
        word.open_new_doc()

    #Test dns connection
    result = client.ack()
    if not result:
        raise Exception("Couldn't connect to server.")
    print("Connection successful")
    if not client.new_chat():
        print("Could not create new chat on server. Answers may be off.")
    print("Ready")

    res_text = "word\r\n" if result else "sentence\r\n"
    word.write_start(res_text)

    word.on_word_deactivated = handle_deactivated

    while True:
        while word_is_open:
            pythoncom.PumpWaitingMessages()

        #If execution reaches here, word got disconnected
        while True:
            time.sleep(1)
            if word.try_reconnect():
                print("Word reconnected")
                word.write_start(res_text)
                word_is_open = True
                break
            print("Failed to reconnect")

if __name__ == "__main__":
    main()