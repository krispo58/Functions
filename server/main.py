import server as networkserver
import os

def run():
    os.environ["FIREBASE_PROJECT_ID"] = "moneymoneygreengreen-e3e24"
    os.environ["FIREBASE_PASSWORD"] = "GigaPassword"


    server = networkserver.Server(debug=True)

    server.start()

if __name__ == "__main__":
    run()