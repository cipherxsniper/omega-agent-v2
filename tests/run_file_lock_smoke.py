import os
import threading
from agent.core.action_engine import Action, ActionExecutor, ActionNode, ActionValidator, SideEffectAnalyzer

TARGET = os.path.expanduser("~/omega_workspace/.omega-file-lock-smoke.txt")


def main():
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    executor = ActionExecutor(ActionValidator(), SideEffectAnalyzer())
    failures = []

    def writer(index):
        try:
            with executor._file_lock(TARGET, exclusive=True):
                executor._atomic_write(TARGET, (f"writer-{index}\n" * 2000))
        except Exception as exc:
            failures.append(str(exc))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    locks = []
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with open(TARGET, encoding="utf-8") as stream:
        content = stream.read()
    assert not failures, failures
    assert content.count("\n") == 2000
    assert content.startswith("writer-")
    os.remove(TARGET)
    print("FILE_LOCK_ATOMIC_WRITE_SMOKE_OK")


if __name__ == "__main__":
    main()
