# main.py

from pathlib import Path

import dotenv

from .agent import ResearchAgent


def main():
    # Load environment variables
    dotenv.load_dotenv()

    # Create output directory if it doesn't exist
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    agent = ResearchAgent()
    final_report = agent.start("Is Solana a good investment?")

    # Save final report
    with open(output_dir / "final_report.md", "w", encoding="utf-8") as f:
        f.write(final_report)

    print("\n\n=========== FINAL REPORT ===========")
    print(final_report)

    # Generate and save visualizations
    print("\n\n=========== RESEARCH PATH VISUALIZATIONS ===========")

    # Save Mermaid diagram
    mermaid_path = output_dir / "research_path.mmd"
    agent.visualize_research_path(format="mermaid", output_file=mermaid_path)
    print(f"Mermaid diagram saved to: {mermaid_path}")

    # Save JSON visualization data
    json_path = output_dir / "research_path.json"
    agent.visualize_research_path(format="json", output_file=json_path)
    print(f"JSON visualization data saved to: {json_path}")

    # Print Mermaid diagram to console
    agent.print_research_path()


if __name__ == "__main__":
    main()
