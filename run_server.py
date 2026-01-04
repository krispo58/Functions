import os
import server.main

if __name__ == "__main__":
    os.chdir("./server/")
    server.main.run()