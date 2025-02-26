# deepseek_client.py

import os

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

from agent.utils import parse_and_print_token


class DeepseekClient:
    """
    Handles streaming responses from the model.
    If ignore_think=True, we do not add <think> content to the final text
    (but still color-print it if verbose=True).
    """

    def __init__(self):
        endpoint = os.environ["AZURE_DEEPSEEK_ENDPOINT"]
        api_key = os.environ["AZURE_DEEPSEEK_API_KEY"]
        self.client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
        )

    def complete(
        self,
        messages: list,
        model: str = "Analysis-POC-DeepSeek-R1",
        verbose: bool = False,
        ignore_think: bool = False,
        temperature: float = 0.5,
    ):
        # Stream the response
        response_gen = self.client.complete(
            messages=messages,
            model=model,
            stream=True,
            temperature=temperature,
            stop=["</query>", "</report>"],
        )

        full_response = ""
        inside_think = False

        for token in response_gen:
            if not token["choices"]:
                continue

            token_text = token["choices"][0]["delta"].get("content", "")
            if not token_text:
                continue

            processed_text, inside_think = parse_and_print_token(
                token_text, inside_think, ignore_think, verbose
            )
            full_response += processed_text

        return full_response
