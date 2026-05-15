#!/usr/bin/env python3
"""Run offline evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from case3.eval.runner import run_eval


def main() -> None:
    report = run_eval()
    print(f"Report: {report.get('report_path')}")


if __name__ == "__main__":
    main()
