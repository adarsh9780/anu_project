import os
from typing import Literal
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel
from pathlib import Path

load_dotenv()


class NewsAnalysis(BaseModel):
    theme: str
    sentiment: Literal["positive", "negative", "neutral"]


api_key = os.environ["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)

model = "gemini-2.5-flash-lite"


def chat(user_query: str, response_schema):
    response = client.models.generate_content(
        model=model,
        contents=user_query,
        config={
            "response_mime_type": "application/json",
            # "response_schema": response_schema, # using pydnatic directly
            "response_json_schema": response_schema.model_json_schema(),
        },
    )

    return response


if __name__ == "__main__":
    news = Path("text_data/01_news.txt").read_text()
    prompt = f"""
    Analyze the following news and provide a summary, theme, and sentiment.
    News: {news}
    """
    response = chat(prompt, NewsAnalysis)
    response = NewsAnalysis.model_validate_json(response.text)
    print(response)
