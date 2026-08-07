#!/usr/bin/env python3
"""
OMEGA — interactive terminal agent
Real Groq-backed reasoning, real file Q&A, real web fetch.
No simulated output.
"""
import sys
import os
import time
import threading
import itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api.groq_client import chat_completion

try:
    import requests
except ImportError:
    requests = None

GREEN = "\033[38;5;48m"
TEAL = "\033[38;5;51m"
YELLOW = "\033[38;5;220m"
PURPLE = "\033[38;5;135m"
GRAY = "\033[38;5;240m"
BOLD = "\033[1m"
RESET = "\033[0m"

OMEGA_SYMBOL = "\u03a9"


def banner():
    print(f"\n{TEAL}{BOLD}  {OMEGA_SYMBOL}  OMEGA AGENT{RESET}")
    print(f"{GRAY}  live Groq reasoning . real file Q&A . real web fetch{RESET}")
    print(f"{GRAY}  commands: :file <path>  :web <url>  :task  :exit{RESET}\n")


class Spinner:
    def __init__(self, label="thinking"):
        self.label = label
        self.running = False
        self.thread = None

    def _spin(self):
        frames = itertools.cycle(["|", "/", "-", "\\"])
        while self.running:
            sys.stdout.write(f"\r{PURPLE}{next(frames)} {self.label}...{RESET}   ")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()


def fetch_url(url: str) -> str:
    if requests is None:
        return "ERROR: requests module not installed"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        return resp.text[:8000]
    except Exception as e:
        return f"ERROR fetching {url}: {e}"


def ask_groq(prompt: str) -> str:
    return chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=800,
    )


def answer_about_file(filepath: str, question: str) -> str:
    if not os.path.exists(filepath):
        return f"ERROR: file not found: {filepath}"
    with open(filepath, "r", errors="replace") as f:
        code = f.read()
    truncated = len(code) > 12000
    code = code[:12000]
    prompt = (
        "Answer precisely based only on this file's actual content. "
        "If unsure, say so.\n\n"
        f"FILE: {filepath}{' (TRUNCATED)' if truncated else ''}\n\n"
        "-----CODE START-----\n" + code + "\n-----CODE END-----\n\n"
        f"QUESTION: {question}\n\nAnswer concisely, citing real names from the code."
    )
    return ask_groq(prompt)


def answer_about_url(url: str, question: str) -> str:
    content = fetch_url(url)
    if content.startswith("ERROR"):
        return content
    prompt = (
        "Answer based only on this real fetched web content. "
        "If the answer isn't in the content, say so.\n\n"
        f"URL: {url}\n\nCONTENT:\n{content}\n\nQUESTION: {question}"
    )
    return ask_groq(prompt)


def main():
    banner()
    current_file = None
    current_url = None
    task_log = []

    while True:
        try:
            mode = f"file:{current_file}" if current_file else (f"web:{current_url}" if current_url else "none")
            raw = input(f"{TEAL}{OMEGA_SYMBOL} [{mode}] > {RESET}").strip()

            if not raw:
                continue
            if raw in (":exit", ":quit"):
                break
            if raw == ":task":
                if not task_log:
                    print(f"{GRAY}No tasks run yet.{RESET}\n")
                else:
                    for i, t in enumerate(task_log[-10:], 1):
                        print(f"{GRAY}{i}. {t}{RESET}")
                    print()
                continue
            if raw.startswith(":file "):
                path = raw[6:].strip()
                if os.path.exists(path):
                    current_file = path
                    current_url = None
                    print(f"{GREEN}Loaded file: {path}{RESET}\n")
                else:
                    print(f"{YELLOW}Not found: {path}{RESET}\n")
                continue
            if raw.startswith(":web "):
                current_url = raw[5:].strip()
                current_file = None
                print(f"{GREEN}Set target URL: {current_url}{RESET}\n")
                continue

            if not current_file and not current_url:
                print(f"{YELLOW}Set a target first: :file <path>  or  :web <url>{RESET}\n")
                continue

            spinner = Spinner("thinking")
            spinner.start()
            try:
                if current_file:
                    answer = answer_about_file(current_file, raw)
                    task_log.append(f"[file:{current_file}] {raw}")
                else:
                    answer = answer_about_url(current_url, raw)
                    task_log.append(f"[web:{current_url}] {raw}")
            finally:
                spinner.stop()

            print(f"{GREEN}{answer}{RESET}\n")

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Interrupted.{RESET}")
            break
        except Exception as e:
            print(f"{YELLOW}Error: {e}{RESET}\n")

    print(f"{PURPLE}{OMEGA_SYMBOL} session ended.{RESET}")


if __name__ == "__main__":
    main()
