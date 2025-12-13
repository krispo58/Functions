import client as networkclient
import wordwrapper
import pythoncom


server_ip = "51.175.238.64"
server_port = 7777
domain = "ordbokene.no"

word = wordwrapper.WordWrapper(visible=True)
client = networkclient.Client(server_ip, server_port, domain)

def find_prompt_replace(word: wordwrapper.WordWrapper):
    prompt = word.get_block("-", "-")
    word.replace_block(",,", ",,", client.send_prompt(prompt))

def handle_deactivated(word: wordwrapper.WordWrapper):
    find_prompt_replace(word)

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
    res_text = "word\r\n" if result else "sentence\r\n"
    word.write_start(res_text)
    print("Connection successful")

    word.on_word_deactivated = handle_deactivated

    while True:
        pythoncom.PumpWaitingMessages()

if __name__ == "__main__":
    main()