import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

load_dotenv()

json_format_model = OpenAIChatCompletionClient(
    model='moonshot-v1-32k',
    base_url="https://api.moonshot.cn/v1",
    api_key=os.getenv("moonshot_api_key"),
    response_format={"type": "json_object"},
    max_tokens=8291,
    model_info={
        "structured_output": True,
        "json_output": True,
        "function_calling": True,
        "vision": False,
        "family": "unknown"
    }
)
