import client as networkclient
import wordwrapper
import pythoncom


server_ip = "51.175.238.64"
server_port = 7777
domain = "ordbokene.no"

word = wordwrapper.WordWrapper(visible=True)
client = networkclient.Client(server_ip, server_port, domain)

def find_prompt_replace(word: wordwrapper.WordWrapper):
    word.make_hidden_visible()
    prompt = word.get_block("-", "-")
    if prompt is None:
        return
    r = client.send_prompt(prompt)
    print(r)
    word.replace_block(",,", ",,",r)
    word.replace_block("-", "-", "") #Delete prompt from document

def handle_deactivated(word: wordwrapper.WordWrapper):
    find_prompt_replace(word)
    print("Flashing taskbar")
    word.flash_taskbar(1)

def main():
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
        pythoncom.PumpWaitingMessages()

if __name__ == "__main__":
    main()