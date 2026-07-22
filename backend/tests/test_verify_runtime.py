import subprocess
from pathlib import Path


def test_verify_runtime_self_test() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        ["python3", "scripts/verify_runtime.py", "--self-test"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
