"""
Text written into the document by the help command (shared by the Word and
Writer clients).

It is deliberately free of the document's own markers (two or three hyphens,
two colons, two commas in a row, three semicolons): they are described in words
instead, because otherwise the clients would treat the help text itself as a
prompt, a command or a slot the next time the window loses focus.
"""

HELP_TEXT = (
    "Commands are typed with two colons on each side of the name, and they run when you switch away "
    "from the window. Stop (also quit or exit) closes the program. New (also reset) starts a fresh "
    "conversation: it forgets the chat, the judge's chat and any answers still waiting, and goes back "
    "to the OpenRouter model. Switch (also fallback) changes between OpenRouter and OpenAI and keeps "
    "the conversation. Test adds the letter t at the end of the document to show the program is alive. "
    "Backupserver switches between the main server and the backup server (starting a fresh conversation "
    "on it) and writes which one is now in use; if that server isn't running, nothing changes. "
    "Help writes this text."
)
