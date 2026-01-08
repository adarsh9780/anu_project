import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)

model = "gemini-2.5-flash-lite"


def chat(user_query: str) -> str | None:
    response = client.models.generate_content(
        model=model,
        contents=user_query,
        config={
            "response_mime_type": "text/plain",
            # "response_schema": structured_output_format,
        },
    )

    return response.text


if __name__ == "__main__":
    response = chat("Hello, how are you?")
    print(response)
