import os

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.responses import EasyInputMessageParam

load_dotenv()

client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv("API_KEY"),
)


def call_llm(query: str, model: str = "deepseek-v4-flash-260425") -> str:

    input_messages: list[EasyInputMessageParam] = [
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": query,
        },
    ]

    response = client.responses.create(
        model=model,
        input=input_messages,
    )

    return response.output_text
