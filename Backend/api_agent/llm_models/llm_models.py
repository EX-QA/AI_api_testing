import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

load_dotenv()

json_format_model = OpenAIChatCompletionClient(
    model='kimi-k2.5',
    base_url="https://api.moonshot.cn/v1",
    api_key=os.getenv("MOONSHOT_API_KEY"),
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
kimi_model = OpenAIChatCompletionClient(
    model='kimi-k2.5',
    base_url="https://api.moonshot.cn/v1",
    api_key=os.getenv("MOONSHOT_API_KEY"),
    max_tokens=8291,
    model_info={
        "structured_output": True,
        "json_output": True,
        "function_calling": True,
        "vision": False,
        "family": "unknown",
        "multiple_system_messages": True
    }

)
deepseek_llm_model = OpenAIChatCompletionClient(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url='https://api.deepseek.com/v1/',
    model_info={
        "structured_output": True,
        "json_output": True,
        "function_calling": True,
        "vision": False,
        "family": "unknown",
        "multiple_system_messages": True
    }
)
minimax_model = OpenAIChatCompletionClient(
    model="MiniMax-M2.1",
    api_key=os.getenv("MINIMAX_API_KEY"),
    base_url='https://api.minimaxi.com/v1',
    model_info={
        "structured_output": True,
        "json_output": True,
        "function_calling": True,
        "vision": False,
        "family": "unknown",
        "multiple_system_messages": True
    }
)
