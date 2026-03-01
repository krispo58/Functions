import server as networkserver
import os
import api_key

def run():
    os.environ["FIREBASE_PROJECT_ID"] = "myproject-3d105"
    os.environ["FIREBASE_PASSWORD"] = "GigaPassword"


    server = networkserver.Server(debug=True)

    server.start()

if __name__ == "__main__":
    run()