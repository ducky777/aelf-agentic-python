# search.py

import os

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

from agent.prompts import MOCK_SEARCH_ENGINE_PROMPT
from agent.utils import parse_and_print_token


def mock_search_engine(query: str) -> str:
    """
    Mocks search engine results by calling the model with a 'mocker' prompt.
    We do not want chain-of-thought from the mocker, so we set ignore_think=True.
    """
    endpoint = os.environ["AZURE_DEEPSEEK_ENDPOINT"]
    api_key = os.environ["AZURE_DEEPSEEK_API_KEY"]
    client = ChatCompletionsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
    )

    response_gen = client.complete(
        messages=[
            SystemMessage(content=MOCK_SEARCH_ENGINE_PROMPT),
            UserMessage(content=query),
        ],
        model="Analysis-POC-DeepSeek-R1",
        stream=True,
    )

    full_response = ""
    inside_think = False

    # Print raw (ignoring chain-of-thought)
    for token in response_gen:
        if not token["choices"]:
            continue
        token_text = token["choices"][0]["delta"].get("content", "")
        processed_text, inside_think = parse_and_print_token(
            token_text, inside_think, ignore_think=True, verbose=True
        )
        full_response += processed_text

    return full_response
