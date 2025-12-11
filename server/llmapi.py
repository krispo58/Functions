import os
from groq import Groq

class LLM:
    def __init__(self):
        os.environ["GROQ_API_KEY"] = "REDACTED_FOR_SAFETY"  # Replace with your actual API key
        self.client = Groq(
            api_key=os.environ.get("GROQ_API_KEY"),  # This is the default and can be omitted
        )

    def prompt(self, content: str):
        completion = self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
            {
                "role": "user",
                "content": content
            }
            ],
            temperature=1,
            top_p=1,
            reasoning_effort="high",
            stream=True,
            stop=None
        )
        
        result = ""
        for chunk in completion:
            result += chunk.choices[0].delta.content or ""
        return result