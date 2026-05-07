import llmapi

llm = llmapi.LLM()


response = llm._prompt_openai("What is the capital of France?")
print("OpenAI Response:", response)
