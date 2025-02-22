import os
import re

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import AssistantMessage, SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

SYSTEM_PROMPT = """You are a helpful assistant that has access to a search engine. Think about the user's request and decide if you need to search the web. If you have a query, wrap it around
```query
```

For example, if the user asks "What is flights are available from US?", you should search the web for
```query
flights from US
```

You will ONLY HAVE 1 QUERY AT A TIME. After you respond, user will reply with the query results. You will then continue digging and searching the web until you have enough information to give a comprehensive answer to the user's question. When responding, ONLY respond with the query. If you are done with your research, respond with <!END_RESEARCH>.
"""

MOCK_SEARCH_ENGINE_PROMPT = """You are a search engine results mocker. Given a query, mock the top 5 search engine results. Each result should be a mock article paragraph. You don't have to think or reason, just generate random results. Format your mock as
```search 1
mock article paragraph
```
```search 2
mock article paragraph
```
...
```"""


class DeepseekClient:
    def __init__(self):
        self.client = ChatCompletionsClient(
            endpoint=os.environ["AZURE_DEEPSEEK_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["AZURE_DEEPSEEK_API_KEY"]),
        )

    def complete(
        self, messages: list, verbose: bool = False, ignore_think: bool = False
    ):
        response_gen = self.client.complete(
            messages=messages,
            model="Analysis-POC-DeepSeek-R1",
            stream=True,
        )

        full_response = ""
        end_think = False
        for token in response_gen:
            if len(token["choices"]) > 0:
                tok = token["choices"][0]["delta"]["content"]
                if verbose:
                    print(tok, end="", flush=True)
                if tok.lower() == "</think>":
                    end_think = True
                if not ignore_think:
                    full_response += tok
                else:
                    if end_think:
                        full_response += tok
        return full_response


class ResearchAgent:
    def __init__(self):
        self.client = DeepseekClient()
        self.messages = [SystemMessage(content=SYSTEM_PROMPT)]

    def search(self, query: str):
        self.messages.append(UserMessage(content=query))

        response = self.client.complete(
            messages=self.messages,
            verbose=True,
            ignore_think=True,
        )

        return response

    def extract_query_content(self, text):
        match = re.search(r"```query\n(.*?)\n```", text, re.DOTALL)
        return match.group(1) if match else None

    def start(self, query: str):
        while True:
            response = self.search(query)
            if "```report" in response:
                return response
            query = self.extract_query_content(response)
            self.messages.append(AssistantMessage(content=query))
            query_results = mock_search_engine(query)
            self.messages.append(UserMessage(content=query_results))


def mock_search_engine(query: str):
    client = ChatCompletionsClient(
        endpoint=os.environ["AZURE_DEEPSEEK_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_DEEPSEEK_API_KEY"]),
    )
    response_gen = client.complete(
        messages=[
            SystemMessage(content=MOCK_SEARCH_ENGINE_PROMPT),
            UserMessage(content=query),
        ],
        model="Analysis-POC-DeepSeek-R1",
        stream=True,
    )

    begin_response = False

    full_response = ""
    for token in response_gen:
        if len(token["choices"]) > 0:
            tok = token["choices"][0]["delta"]["content"]
            if begin_response:
                full_response += tok
            print(tok, end="", flush=True)
            if tok.lower() == "</think>":
                begin_response = True
    return full_response


if __name__ == "__main__":
    client = DeepseekClient()

    agent = ResearchAgent()
    report = agent.start("Is Dogecoin a good investment?")
    # response = agent.start("Is Dogecoin a good investment?")
