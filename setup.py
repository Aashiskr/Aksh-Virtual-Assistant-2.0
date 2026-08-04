"""Install Aksh dependencies into the Python interpreter running this script."""

import subprocess
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 10):
        raise SystemExit(
            "Aksh uses Python 3.10. Run: py -3.10 setup.py"
        )
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    )


if __name__ == "__main__":
    main()
