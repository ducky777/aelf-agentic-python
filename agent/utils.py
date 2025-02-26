# utils.py

import re


def colorize_think_text(text: str) -> str:
    """
    Color the given text in italic green (where supported).
    \033[3;32m = italic+green
    \033[0m = reset
    """
    return f"\033[3;32m{text}\033[0m"


def extract_query_content(text: str) -> str:
    """Extract content between <query> tags."""
    match = re.search(r"<query>(.*?)</query>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def extract_cypher_content(text: str) -> str:
    """Extract content between <cypher> tags."""
    match = re.search(r"<cypher>(.*?)</cypher>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def parse_and_print_token(
    token_text: str, inside_think: bool, ignore_think: bool, verbose: bool
):
    """
    Given a chunk of text from the stream, decide how to handle:
      - If it's a <think> or </think> delimiter, toggle inside_think state.
      - If inside_think and we are ignoring chain-of-thought for final result,
        we omit from final concatenated response, but still color-print it (if verbose).
      - If not ignoring chain-of-thought, we keep it in the final response,
        but color it in green italics when printing.

    Returns:
      - processed_text: the text we ultimately append to the full response
      - new_inside_think: updated boolean state
    """
    processed_text = ""
    new_inside_think = inside_think

    remaining = token_text
    while remaining:
        think_open_idx = remaining.find("<think>")
        think_close_idx = remaining.find("</think>")

        if think_open_idx == -1 and think_close_idx == -1:
            # No <think> or </think> in the remainder
            if not (ignore_think and new_inside_think):
                processed_text += remaining

            if verbose:
                if new_inside_think:
                    print(colorize_think_text(remaining), end="", flush=True)
                else:
                    print(remaining, end="", flush=True)

            remaining = ""
        else:
            # Find whichever comes first: <think> or </think>
            if 0 <= think_open_idx < think_close_idx or (
                think_open_idx != -1 and think_close_idx == -1
            ):
                # <think> occurs before </think>, or </think> not found
                before = remaining[:think_open_idx]
                if not new_inside_think or ignore_think is False:
                    processed_text += before

                if verbose:
                    # Print outside-think text normally, inside-think text colorized
                    if new_inside_think and not ignore_think:
                        print(colorize_think_text(before), end="", flush=True)
                    else:
                        print(before, end="", flush=True)

                remaining = remaining[think_open_idx + len("<think>") :]
                new_inside_think = True

            else:
                # </think> occurs before <think>, or <think> not found
                before = remaining[:think_close_idx]
                if not ignore_think:
                    processed_text += before

                if verbose:
                    # If we are inside <think>, colorize
                    if new_inside_think:
                        print(colorize_think_text(before), end="", flush=True)
                    else:
                        print(before, end="", flush=True)

                remaining = remaining[think_close_idx + len("</think>") :]
                new_inside_think = False

    return processed_text, new_inside_think
