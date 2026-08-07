#!/usr/bin/env python3
"""
Real code Q&A tool - reads an actual file and answers a real question
about it using Groq. No hardcoded responses, no simulated output.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api.groq_client import chat_completion


def answer_question_about_file(filepath: str, question: str) -> str:
    if not os.path.exists(filepath):
        return f"ERROR: file not found: {filepath}"

    with open(filepath, "r", errors="replace") as f:
        code = f.read()

    max_chars = 12000
    truncated = False
    if len(code) > max_chars:
        code = code[:max_chars]
        truncated = True

    trunc_note = "  (TRUNCATED - showing first " + str(max_chars) + " chars)" if truncated else ""
    prompt = (
        "You are answering a question about a real code file.\n"
        "Be precise and only state things you can actually see in the code below.\n"
        "If you're not sure, say so - do not guess or make up behavior.\n\n"
        "FILE: " + filepath + trunc_note + "\n\n"
        "-----CODE START-----\n"
        + code +
        "\n-----CODE END-----\n\n"
        "QUESTION: " + question + "\n\n"
        "Answer concisely, citing specific function/variable names from the code."
    )

    return chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=600,
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 code_qa.py <filepath> <question>")
        sys.exit(1)

    filepath = sys.argv[1]
    question = " ".join(sys.argv[2:])

    print(f"File: {filepath}")
    print(f"Question: {question}")
    print("-" * 50)
    answer = answer_question_about_file(filepath, question)
    print(answer)
