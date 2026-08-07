#!/usr/bin/env python3
"""
Interactive, colored terminal chat for asking questions about real files
in the codebase. Uses the same real Groq-backed Q&A as code_qa.py.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from code_qa import answer_question_about_file

GREEN = "\033[92m"
TEAL = "\033[96m"
YELLOW = "\033[93m"
PURPLE = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"


def banner():
    print(f"{TEAL}{BOLD}")
    print("╔══════════════════════════════════════╗")
    print("║        OMEGA CODE Q&A  —  live        ║")
    print("╚══════════════════════════════════════╝")
    print(f"{RESET}{DIM}Real Groq-backed answers about real files. Type 'exit' to quit.{RESET}\n")


def main():
    banner()
    current_file = None

    while True:
        try:
            if not current_file:
                current_file = input(f"{PURPLE}Which file? {RESET}").strip()
                if current_file.lower() in ("exit", "quit"):
                    break
                if not os.path.exists(current_file):
                    print(f"{YELLOW}File not found: {current_file}{RESET}\n")
                    current_file = None
                    continue
                print(f"{GREEN}Loaded: {current_file}{RESET}\n")
                continue

            question = input(f"{TEAL}Ask (or 'switch' to change file, 'exit' to quit) > {RESET}").strip()

            if question.lower() in ("exit", "quit"):
                break
            if question.lower() == "switch":
                current_file = None
                continue
            if not question:
                continue

            print(f"{DIM}Thinking...{RESET}")
            answer = answer_question_about_file(current_file, question)
            print(f"\n{GREEN}{answer}{RESET}\n")

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Interrupted.{RESET}")
            break
        except Exception as e:
            print(f"{YELLOW}Error: {e}{RESET}\n")

    print(f"{PURPLE}Goodbye.{RESET}")


if __name__ == "__main__":
    main()
