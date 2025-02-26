# agent.py

from azure.ai.inference.models import SystemMessage, UserMessage

from agent.deepseek_client import DeepseekClient
from agent.neo4j_client import Neo4jClient
from agent.prompts import NEO4J_SYSTEM_PROMPT, SYSTEM_PROMPT
from agent.search import mock_search_engine
from agent.utils import extract_cypher_content, extract_query_content
from agent.visualization import ResearchPathVisualizer


class ResearchAgent:
    def __init__(
        self,
        tool: str = "search",
        neo4j_uri: str = None,
        neo4j_username: str = None,
        neo4j_password: str = None,
    ):
        """
        Initialize the research agent.

        Args:
            tool: Either "search" or "neo4j" to specify which tool to use
            neo4j_uri: Neo4j database URI (required if tool="neo4j")
            neo4j_username: Neo4j username (required if tool="neo4j")
            neo4j_password: Neo4j password (required if tool="neo4j")
        """
        if tool not in ["search", "neo4j"]:
            raise ValueError('tool must be either "search" or "neo4j"')

        self.tool = tool
        self.client = DeepseekClient()

        # Initialize appropriate system prompt and tool client
        if tool == "search":
            self.system_prompt = SYSTEM_PROMPT
            self.tool_client = None
        else:  # neo4j
            if not all([neo4j_uri, neo4j_username, neo4j_password]):
                raise ValueError("Neo4j connection details required when tool='neo4j'")
            self.system_prompt = NEO4J_SYSTEM_PROMPT
            self.tool_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)

        self.messages = [SystemMessage(content=self.system_prompt)]
        # Keep track of each step for "path" visualization
        # Each entry = {"query": ..., "assistant_response": ..., "results": ...}
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
            verbose=True,  # color-print chain-of-thought
            ignore_think=True,  # do not include chain-of-thought in the final text
        )
        return assistant_response

    def start(self, initial_question: str) -> str:
        """
        Continues reading the assistant's responses. If we see a final <report>, we stop.
        Otherwise, we extract a query from the assistant's response and pass it to
        either the search engine or Neo4j database. Then we feed those results back
        into the conversation.
        """
        current_query = initial_question
        while True:
            # Ask the model for the next step using the current_query
            response = self.search(
                f"""{current_query}\n\nREMEMBER TO ONLY STICK TO ONE SUB TOPIC FIRST. Write down ONE query."""
            )

            # If the assistant ended with a final <report>, we are done
            if "<report>" in response:
                self.research_path.append(
                    {
                        "query": current_query,
                        "assistant_response": response,
                        "results": None,
                    }
                )
                return response

            # Extract the next query based on the tool being used
            if self.tool == "search":
                next_query = extract_query_content(response)
                if next_query:
                    results = mock_search_engine(next_query)
            else:  # neo4j
                next_query = extract_cypher_content(response)
                if next_query:
                    # Use mock_query for development/testing
                    results = self.tool_client.mock_query(next_query)
                    # For production:
                    # results = self.tool_client.execute_query(next_query)

            if not next_query:
                # No new query => can't continue
                self.research_path.append(
                    {
                        "query": current_query,
                        "assistant_response": response,
                        "results": None,
                    }
                )
                break

            # Store path before we do the search/query
            self.research_path.append(
                {
                    "query": current_query,
                    "assistant_response": response,
                    "results": results,
                }
            )

            # Feed the results back into the conversation
            self.messages.append(UserMessage(content=results))

            # Move on
            current_query = next_query

        return "No final report received."

    def visualize_research_path(self, format: str = "mermaid", output_file: str = None):
        """
        Visualize the research path in the specified format.

        Args:
            format: Either "mermaid" or "json"
            output_file: Optional file path to save the visualization
        """
        visualizer = ResearchPathVisualizer(self.research_path)

        if format == "mermaid":
            mermaid_diagram = visualizer.to_mermaid()
            if output_file:
                with open(output_file, "w") as f:
                    f.write(mermaid_diagram)
            return mermaid_diagram

        elif format == "json":
            return visualizer.to_json(output_file)

        else:
            raise ValueError(f"Unsupported visualization format: {format}")

    def print_research_path(self):
        """Prints the research path as a Mermaid diagram."""
        print("\n=== RESEARCH PATH VISUALIZATION ===")
        print(self.visualize_research_path(format="mermaid"))

    def __del__(self):
        """Clean up Neo4j connection if it exists."""
        if hasattr(self, "tool_client") and self.tool_client:
            self.tool_client.close()
