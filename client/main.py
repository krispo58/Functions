import client as networkclient
import pythoncom
#import wordwrapper

server_ip = "127.0.0.1"
server_port = 7777
domain = "photos.google.com"


def main():
    pythoncom.CoInitialize()
    #word = wordwrapper.WordWrapper(visible=True)
    client = networkclient.Client(server_ip, server_port, domain)

    result = client.ack()

    print("Connection established") if result else "Failed to connect to server."