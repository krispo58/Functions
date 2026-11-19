import llmapi

llm = llmapi.LLM()

print("OpenRouter Response:", llm.prompt("What is the capital of France?"))

llm.reset_chat_history()
llm.toggle_llm()  # switch to OpenAI
print("OpenAI Response:", llm.prompt("What is the capital of France?"))
