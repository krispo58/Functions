import server as networkserver

server = networkserver.Server("https://my-awesome-project-3c43d-default-rtdb.europe-west1.firebasedatabase.app/", debug=True)

server.start()