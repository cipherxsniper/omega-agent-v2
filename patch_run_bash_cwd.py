path = "agent/core/action_engine.py"
with open(path) as f:
    src = f.read()

anchor = '''            try:
                import subprocess
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30
                )'''

assert src.count(anchor) == 1, "anchor not found/not unique - aborting"

replacement = '''            try:
                import subprocess
                # Match list_dir/read_file's path resolution: this process's
                # actual cwd is whatever directory the server happened to be
                # launched from, which drifts across restarts. Anchor every
                # run_bash call to the same OMEGA_WORKSPACE root those tools
                # already use, so relative paths behave identically across
                # every tool instead of only working in list_dir/read_file.
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30,
                    cwd=self.OMEGA_WORKSPACE,
                )'''

src = src.replace(anchor, replacement, 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
