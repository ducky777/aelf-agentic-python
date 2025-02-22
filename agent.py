import os
import re

import dotenv
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

dotenv.load_dotenv()

# =========================
#      GLOBAL PROMPTS
# =========================
SYSTEM_PROMPT = """You are a meticulous research assistant with access to a search engine. Your goal is to produce a **comprehensive, critically verified report** by iterating through research cycles until **all guardrails are satisfied**. Follow this protocol strictly:

---

### **Research Workflow**
1. **Deconstruct the Query**: Break the user’s request into sub-topics/key components.
2. **Iterative Searching**:
   - Use ONE `<query>` per message. Prioritize specificity (e.g., "Apple stock analysis Q3 2024 + competitor trends" vs. "Is Apple a good buy?").
   - For *every claim or data point* found, conduct follow-up searches to:
     - Verify with **3+ independent, authoritative sources** (e.g., .gov, .edu, peer-reviewed journals, reputable news).
     - Investigate conflicting claims (e.g., "Apple car project delays 2024" vs. "Apple car launch confirmed").
     - Uncover recent updates (<12 months) unless historical context is required.
3. **Source Criticism**:
   - Reject low-credibility sources (unverified blogs, social media). If uncertain, search "Is [source] credible?".
   - Flag potential biases (e.g., "Tesla analysis" → search "Tesla analyst conflicts of interest").
4. **Depth Checks**:
   - For financial/medical/legal topics, include regulatory filings, expert consensus, or peer-reviewed data.
   - For trends/forecasts, identify supporting *and* opposing viewpoints.
5. **Thinking**:
    - Only think ONE thing at a time.
    - Keep your thoughts strictly to a single topic. For example, if you are thinking about market volatility, stick only to that topic.

---

### **Guardrails to Prevent Premature Termination**
Before finalizing, confirm **ALL** of the following:
- **Coverage**: All sub-topics are addressed with **minimum 3 verified sources each**.
- **Verification**: No claim is accepted without cross-checking. Conflicting evidence is explicitly analyzed.
- **Timeliness**: Data is updated (search "[topic] + latest developments 2024" if unsure).
- **Gaps Resolved**: All "Unknown" or "Inconclusive" areas are explicitly acknowledged in the report.
- **User Intent**: The report aligns with the user’s explicit *and* implicit needs (ask clarifying questions if ambiguous).

---

### **Stopping Condition Checklist**
Only generate `<report>` after answering **YES** to all:
1. Have I addressed every component of the user’s query *and* its logical sub-questions?
2. Are all claims backed by multiple high-quality sources, with discrepancies documented?
3. Did I search for "[topic] + criticisms", "[topic] + counterarguments", and "[topic] + controversies"?
4. Have I reviewed the past 3 iterations to ensure no new gaps were introduced?
5. Would adding 1-2 more searches *significantly* improve depth or reliability?

---

### **Output Format**
- **During Research**: Only output `<query>[specific, optimized search term]</query>`.
- **Final Report**: Wrap in `<report>[Full analysis with inline citations, dates, and source evaluation. Acknowledge limitations.]</report>`.

**Example**:
User: "Should I invest in Tesla?"
Assistant:
`<query>Tesla Q4 2024 financial performance + SEC filings vs. analyst projections</query>`
User:
(results of the query)
Assistant:
<query>(next query)</query>
... (after iterations) ...
`<report>**Tesla Investment Analysis**
1. **Financial Health**: Q4 revenue rose 12% (SEC, 2024), but margins fell to 8% (Reuters, 2024)...
2. **Risks**: CEO controversies (WSJ, 2023)...
**Unresolved**: Impact of pending EU battery regulations (sources outdated)...</report>`

---

**Begin by deconstructing the user’s query into sub-topics. Proceed step-by-step.**
"""

MOCK_SEARCH_ENGINE_PROMPT = """You are a search engine results mocker. Given a query, mock the top 5 search engine results. Each result should be a mock article paragraph. You don't have to think or reason, just generate random results. Format your mock as:
```search 1
mock article paragraph
```
```search 2
mock article paragraph
```
...
```search 5
mock article paragraph
```
"""

# =========================
#   HELPER FUNCTIONS
# =========================


def colorize_think_text(text: str) -> str:
    """
    Color the given text in italic green (where supported).
    \033[3;32m = italic+green
    \033[0m = reset
    """
    return f"\033[3;32m{text}\033[0m"


def extract_query_content(text: str) -> str:
    """
    Given a text that may contain:
    <query>
    <some query>
    </query>
    This function extracts and returns the <some query> part.
    """
    matches = re.findall(r"<query>(.*?)</q", text, re.DOTALL)
    query = matches[0].strip() if matches else None
    return query


def parse_and_print_token(
    token_text: str, inside_think: bool, ignore_think: bool, verbose: bool
):
    """
    Given a chunk of text from the stream, decide how to handle:
      - If it's a <think> or </think> delimiter, toggle inside_think state.
      - If inside_think and we are ignoring chain-of-thought for final result,
        we omit from final concatenated response, but we can still color-print it (if verbose).
      - If not ignoring chain-of-thought, we keep it in the final response,
        but color it in green italics when printing.
    Returns:
      - processed_text: the text we ultimately append to the full response
      - new_inside_think: updated boolean state
    """
    processed_text = ""
    new_inside_think = inside_think

    # We have to consider that token_text might contain multiple <think> or </think>.
    # We'll handle them in a simple loop-based approach.
    remaining = token_text
    while remaining:
        if "<think>" in remaining or "</think>" in remaining:
            # find the earliest bracket
            think_open_idx = remaining.find("<think>")
            think_close_idx = remaining.find("</think>")

            # If we find <think> first or that is the only one
            if think_open_idx != -1 and (
                think_close_idx == -1 or think_open_idx < think_close_idx
            ):
                # everything before <think>
                before = remaining[:think_open_idx]
                if not new_inside_think or ignore_think is False:
                    processed_text += before

                # print the 'before' text if verbose (and if outside think, we do normal color)
                if verbose:
                    if new_inside_think and not ignore_think:
                        print(colorize_think_text(before), end="", flush=True)
                    else:
                        print(before, end="", flush=True)

                # update remaining
                remaining = remaining[think_open_idx + len("<think>") :]

                # now we've encountered <think>, toggle inside_think on
                new_inside_think = True

            # else if we find </think> first or is the only one
            elif think_close_idx != -1 and (
                think_open_idx == -1 or think_close_idx < think_open_idx
            ):
                # everything before </think>
                before = remaining[:think_close_idx]
                if not ignore_think:
                    processed_text += before

                # print if verbose
                if verbose:
                    if new_inside_think:
                        print(colorize_think_text(before), end="", flush=True)
                    else:
                        print(before, end="", flush=True)

                # update remaining
                remaining = remaining[think_close_idx + len("</think>") :]

                # we've encountered </think>, toggle inside_think off
                new_inside_think = False
            else:
                # safety net in case of weird partial overlap
                processed_text += remaining
                if verbose:
                    print(remaining, end="", flush=True)
                remaining = ""
        else:
            # no <think> or </think> in the remainder
            if not (ignore_think and new_inside_think):
                processed_text += remaining

            if verbose:
                # if we are inside <think>, color it
                if new_inside_think:
                    print(colorize_think_text(remaining), end="", flush=True)
                else:
                    print(remaining, end="", flush=True)
            remaining = ""

    return processed_text, new_inside_think


# =========================
#   Deepseek Client
# =========================


class DeepseekClient:
    """
    Handles streaming responses from the model.
    If ignore_think=True, we do not add <think> content to the final text
    (but still color-print it if verbose=True).
    """

    def __init__(self):
        self.client = ChatCompletionsClient(
            endpoint=os.environ["AZURE_DEEPSEEK_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["AZURE_DEEPSEEK_API_KEY"]),
        )

    def complete(
        self,
        messages: list,
        model: str = "Analysis-POC-DeepSeek-R1",
        verbose: bool = False,
        ignore_think: bool = False,
        temperature: float = 0.5,
    ):
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

            # The model returns tokens like: token["choices"][0]["delta"]["content"]
            token_text = token["choices"][0]["delta"].get("content", "")
            if not token_text:
                continue

            processed_text, inside_think = parse_and_print_token(
                token_text, inside_think, ignore_think, verbose
            )
            full_response += processed_text

        return full_response


# =========================
#   Mock Search Engine
# =========================


def mock_search_engine(query: str) -> str:
    """
    Mocks search engine results by calling the same model with a 'mocker' prompt.
    We do not want chain-of-thought from the mocker, so we can ignore_think=True here
    or you could choose to see it for debugging.
    """
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

    full_response = ""
    inside_think = False

    for token in response_gen:
        if not token["choices"]:
            continue
        token_text = token["choices"][0]["delta"].get("content", "")

        # For the mock search, let's just print raw. We'll ignore chain-of-thought if any.
        processed_text, inside_think = parse_and_print_token(
            token_text,
            inside_think,
            ignore_think=True,  # ignoring chain-of-thought
            verbose=True,
        )
        full_response += processed_text

    return full_response


# =========================
#   Research Agent
# =========================


class ResearchAgent:
    def __init__(self):
        self.client = DeepseekClient()
        self.messages = [SystemMessage(content=SYSTEM_PROMPT)]
        # Keep track of each step for "path" visualization
        # Each entry can be: {"query": ..., "assistant_response": ..., "search_results": ...}
        self.research_path = []

    def search(self, query: str) -> str:
        """
        Passes the latest user query to the model.
        We intentionally ignore chain-of-thought in the final returned string
        (the user sees no chain-of-thought),
        but we do color-print any <think> segments for debugging if verbose=True.
        """
        self.messages.append(UserMessage(content=query))
        assistant_response = self.client.complete(
            messages=self.messages,
            model="Analysis-POC-DeepSeek-R1",
            verbose=True,  # show chain-of-thought in green if present
            ignore_think=True,  # do not include chain-of-thought in the final text
        )
        return assistant_response

    def start(self, initial_question: str) -> str:
        """
        Continues reading the assistant's responses. If we see a final <report>, we stop.
        Otherwise, we extract a query from the assistant's response and pass it to the
        'mock_search_engine'. Then we feed those search results back into the conversation.
        """
        current_query = initial_question
        while True:
            response = self.search(
                f"""{current_query}\n\n REMEMBER TO ONLY STICK TO ONE SUB TOPIC FIRST. Write down ONE query."""
            )

            # If the assistant ended with a final report, we are done:
            if "<report>" in response:
                # Keep this final piece in the path for clarity
                self.research_path.append(
                    {
                        "query": current_query,
                        "assistant_response": response,
                        "search_results": None,
                    }
                )
                return response

            # Otherwise, extract the next query (assistant is telling us what to search)
            next_query = extract_query_content(response)
            print(f"\n\nNext query: {next_query}\n\n")
            if not next_query:
                # If there's no new query, we can't proceed further. We just break.
                self.research_path.append(
                    {
                        "query": current_query,
                        "assistant_response": response,
                        "search_results": None,
                    }
                )
                break

            self.research_path.append(
                {
                    "query": current_query,
                    "assistant_response": response,
                    "search_results": None,
                }
            )

            # Actually run the search with the newly extracted query
            results = mock_search_engine(next_query)

            # Store the search results in the path
            self.research_path[-1]["search_results"] = results

            # Now feed those results back to the conversation
            self.messages.append(UserMessage(content=results))

            # Move on to the next query
            current_query = next_query

        return "No final report received."

    def print_research_path(self):
        """
        Prints a summary (path) of all the queries, responses, and search results
        in Mermaid diagram format. This helps visualize the research steps as a tree.
        """
        print("\n=== RESEARCH PATH VISUALIZATION ===")
        print("```mermaid")
        print("graph TD")

        # Track the last node ID to connect nodes
        last_node_id = "start"
        print(f'    {last_node_id}["Initial Question"]')

        for i, step in enumerate(self.research_path, 1):
            # Create node IDs for this step
            query_id = f"query{i}"
            response_id = f"response{i}"
            search_id = f"search{i}"

            # Add query node and connect it
            query_text = (
                step["query"][:50] + "..." if len(step["query"]) > 50 else step["query"]
            )
            print(f'    {last_node_id} --> {query_id}["{query_text}"]')

            # Add assistant response node
            response_text = step["assistant_response"]
            if "<report>" in response_text:
                # For final report, show it differently
                print(f'    {query_id} --> {response_id}{{"Final Report"}}')
            else:
                # Extract query from response for intermediate steps
                next_query = extract_query_content(response_text)

                if next_query:
                    next_query = (
                        next_query[:50] + "..." if len(next_query) > 50 else next_query
                    )
                    print(
                        f'    {query_id} --> {response_id}["Search for: {next_query}"]'
                    )

            # Add search results if they exist
            if step["search_results"]:
                print(f'    {response_id} --> {search_id}["Search Results"]')
                last_node_id = search_id
            else:
                last_node_id = response_id

        print("```")


# =========================
#         MAIN
# =========================

if __name__ == "__main__":
    agent = ResearchAgent()
    final_report = agent.start("Is Solana a good investment?")

    with open("final_report.md", "w") as f:
        f.write(final_report)

    print("\n\n=========== FINAL REPORT ===========")
    print(final_report)

    # Print the path the agent took
    agent.print_research_path()
