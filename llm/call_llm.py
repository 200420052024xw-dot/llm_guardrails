import os

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.responses import EasyInputMessageParam

load_dotenv()

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "deepseek-v4-flash-260425"

client = OpenAI(
    base_url=os.getenv("BASE_URL", DEFAULT_BASE_URL),
    api_key=os.getenv("API_KEY"),
)


def call_llm(query: str, model: str | None = None) -> str:

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
        model=model or os.getenv("MODEL", DEFAULT_MODEL),
        input=input_messages,
    )

    return response.output_text
