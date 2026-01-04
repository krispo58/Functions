import server as networkserver
import os

def run():
    os.environ["FIREBASE_PROJECT_ID"] = "my-awesome-project-3c43d"
    os.environ["FIREBASE_PASSWORD"] = "GigaPassword"


    server = networkserver.Server(debug=True)

    server.start()

if __name__ == "__main__":
    run()