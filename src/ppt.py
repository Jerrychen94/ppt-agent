#!/usr/bin/env python3
"""入口：python3 src/ppt.py <command>

契约见 docs/contract.md：stdin 读参数（eval 模式），stdout 输出 JSON（--json 或 eval）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deck.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
