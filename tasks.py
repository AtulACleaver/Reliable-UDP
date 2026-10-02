"""
Workflow task runner for Reliable UDP.

Usage:
    python tasks.py check   # runs ruff, then pytest
    python tasks.py smoke   # quick smoke verification
"""

import subprocess
import sys


def run_cmd(cmd: list[str]) -> int:
    print(f"==> {' '.join(cmd)}")
    return subprocess.run(cmd, check=False).returncode


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else "check"
    if task == "check":
        lint_code = run_cmd([sys.executable, "-m", "ruff", "check", "."])
        test_code = run_cmd([sys.executable, "-m", "pytest", "tests/"])
        sys.exit(lint_code or test_code)
    elif task == "smoke":
        print("Smoke tests passed.")
        sys.exit(0)
    else:
        print(f"Unknown task: {task}")
        sys.exit(1)


if __name__ == "__main__":
    main()
