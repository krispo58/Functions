from openai import OpenAI

def main():
    client = OpenAI(api_key="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")

    response = client.responses.create(
        model="gpt-5-mini",  # fast + cheap, good for testing
        input="Explain how APIs work in one paragraph."
    )

    print(response.output[0].content[0].text)

if __name__ == "__main__":
    main()