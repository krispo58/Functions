import server as networkserver

server = networkserver.Server(7777, debug=True)

server.start()