# main.py

import os

import dotenv

from agent.agent import ResearchAgent


def main():
    # Load environment variables
    dotenv.load_dotenv()

    agent = ResearchAgent(
        tool="neo4j",
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_username=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
    )
    final_report = agent.start(
        "Among the memecoins DOGEX, HONK, and MOO, which one is most favored by prime KOLs? Also, list any high-weight wallets (weight ≥ 0.8) that hold or develop it, check if it’s been bridged via Wormhole, and show me relevant tweets (including retweets) about it."
    )

    with open("final_report.md", "w", encoding="utf-8") as f:
        f.write(final_report)

    print("\n\n=========== FINAL REPORT ===========")
    print(final_report)

    # Print the path the agent took
    agent.print_research_path()


if __name__ == "__main__":
    main()
