import json
from datetime import datetime
from typing import Dict, List


class ResearchPathVisualizer:
    def __init__(self, research_path: List[Dict]):
        self.research_path = research_path

    def to_mermaid(self) -> str:
        """Generate a detailed Mermaid flowchart of the research process."""
        mermaid = [
            "```mermaid",
            "flowchart TD",
            "    classDef query fill:#e1f5fe,stroke:#01579b",
            "    classDef thinking fill:#f3e5f5,stroke:#4a148c",
            "    classDef search fill:#f1f8e9,stroke:#33691e",
            "    classDef report fill:#fff3e0,stroke:#e65100",
            "    classDef error fill:#ffebee,stroke:#b71c1c",
        ]

        # Start node
        mermaid.append('    start["🔍 Initial Question"]')
        last_node = "start"

        for idx, step in enumerate(self.research_path, 1):
            # Create unique IDs for each node
            query_id = f"query_{idx}"
            thinking_id = f"thinking_{idx}"
            search_id = f"search_{idx}"

            # Add query node
            query_text = self._truncate_text(step["query"])
            mermaid.append(f'    {query_id}["❓ Query:\\n{query_text}"]:::query')
            mermaid.append(f"    {last_node} --> {query_id}")

            # Extract and add thinking process if present
            if "<think>" in step["assistant_response"]:
                thinking_text = self._extract_thinking(step["assistant_response"])
                if thinking_text:
                    mermaid.append(
                        f'    {thinking_id}["🤔 Thinking:\\n{thinking_text}"]:::thinking'
                    )
                    mermaid.append(f"    {query_id} --> {thinking_id}")
                    last_node = thinking_id

            # Add search results if present
            if step["search_results"]:
                search_summary = self._summarize_search_results(step["search_results"])
                mermaid.append(
                    f'    {search_id}["🔍 Search Results:\\n{search_summary}"]:::search'
                )
                mermaid.append(f"    {last_node} --> {search_id}")
                last_node = search_id

            # Check if this is the final report
            if "<report>" in step["assistant_response"]:
                report_id = f"report_{idx}"
                mermaid.append(f'    {report_id}["📊 Final Report"]:::report')
                mermaid.append(f"    {last_node} --> {report_id}")

        mermaid.append("```")
        return "\n".join(mermaid)

    def to_json(self, output_file: str = None) -> str:
        """Export the research path as JSON for external visualization tools."""
        export_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_steps": len(self.research_path),
            },
            "path": self.research_path,
        }

        json_str = json.dumps(export_data, indent=2)
        if output_file:
            with open(output_file, "w") as f:
                f.write(json_str)
        return json_str

    @staticmethod
    def _truncate_text(text: str, max_length: int = 50) -> str:
        """Truncate text and add ellipsis if needed."""
        return f"{text[:max_length]}..." if len(text) > max_length else text

    @staticmethod
    def _extract_thinking(response: str) -> str:
        """Extract thinking process from between <think> tags."""
        import re

        think_matches = re.findall(r"<think>(.*?)</think>", response, re.DOTALL)
        if think_matches:
            return ResearchPathVisualizer._truncate_text(think_matches[0].strip())
        return ""

    @staticmethod
    def _summarize_search_results(results: str) -> str:
        """Create a brief summary of search results."""
        # Count the number of search results
        result_count = results.count("```search")
        return f"{result_count} results found"
