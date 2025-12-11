import dnstunnel
import pythoncom
import wordwrapper

server_ip = "127.0.0.1"
server_port = 7777
domain = "example.com"

word = wordwrapper.WordWrapper(visible=True)
word.use_active_doc()
word.on_word_deactivated = lambda: word.replace_block()


while True:
    pythoncom.PumpWaitingMessages()