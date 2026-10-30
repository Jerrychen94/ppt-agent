#!/usr/bin/env python3
"""通用评测执行器。

用法：
    python3 scripts/run-evals.py <项目目录> [--update-baseline] [--tag smoke] [--verbose]

约定（被测程序只需满足这一条）：
    stdin  <- 用例的 input（字符串原样，对象则转 JSON）
    stdout -> 结果（JSON 优先）
    退出码 -> 用例可用 expect.exit_code 声明期望值，默认 0

用例格式见 docs/04-评测与质量规范.md。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def load_cases(cases_dir: Path, tag: str | None) -> list[dict]:
    cases: list[dict] = []
    for path in sorted(cases_dir.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            for index, item in enumerate(data):
                item.setdefault("id", f"{path.stem}-{index}")
                cases.append(item)
        else:
            data.setdefault("id", path.stem)
            cases.append(data)
    for path in sorted(cases_dir.glob("*.jsonl")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if line:
                item = json.loads(line)
                item.setdefault("id", f"{path.stem}-{lineno}")
                cases.append(item)
    if tag:
        cases = [c for c in cases if tag in c.get("tags", [])]
    return cases


def get_path(obj, path: str):
    current = obj
    for part in path.split("."):
        if not part:
            continue
        match = re.match(r"^([^\[]*)(?:\[(\d+)\])?$", part)
        if not match:
            raise KeyError(path)
        name, index = match.group(1), match.group(2)
        if name:
            if not isinstance(current, dict) or name not in current:
                raise KeyError(path)
            current = current[name]
        if index is not None:
            if not isinstance(current, list) or int(index) >= len(current):
                raise KeyError(path)
            current = current[int(index)]
    return current


def same(expected, actual) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 1e-9
    return expected == actual


def check(case: dict, stdout: str, exit_code: int) -> list[str]:
    expect = case.get("expect", {})
    problems: list[str] = []

    for text in expect.get("contains", []):
        if text not in stdout:
            problems.append(f"缺少内容: {text!r}")
    for text in expect.get("not_contains", []):
        if text in stdout:
            problems.append(f"出现禁止内容: {text!r}")

    pattern = expect.get("regex")
    if pattern and not re.search(pattern, stdout, re.S):
        problems.append(f"正则不匹配: {pattern!r}")

    wanted_exit = expect.get("exit_code", 0)
    if exit_code != wanted_exit:
        problems.append(f"退出码 {exit_code}，期望 {wanted_exit}")

    raw_paths = expect.get("json_path")
    if raw_paths:
        paths = raw_paths if isinstance(raw_paths, list) else [raw_paths]
        try:
            payload = json.loads(stdout.strip().splitlines()[-1] if stdout.strip() else "")
        except (json.JSONDecodeError, IndexError):
            return problems + ["stdout 不是合法 JSON，无法按 json_path 断言"]
        for spec in paths:
            try:
                actual = get_path(payload, spec["path"])
            except KeyError:
                problems.append(f"字段不存在: {spec['path']}")
                continue
            if "equals" in spec and not same(spec["equals"], actual):
                problems.append(
                    f"{spec['path']} = {actual!r}，期望 {spec['equals']!r}"
                )
            if "length" in spec:
                try:
                    size = len(actual)
                except TypeError:
                    problems.append(f"{spec['path']} 没有长度")
                else:
                    if size != spec["length"]:
                        problems.append(f"{spec['path']} 长度 {size}，期望 {spec['length']}")
            if "contains" in spec and str(spec["contains"]) not in str(actual):
                problems.append(f"{spec['path']} 不包含 {spec['contains']!r}")

    return problems


def run_case(case: dict, cmd: list[str], cwd: Path, timeout: float) -> dict:
    raw = case.get("input", "")
    payload = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    argv = [part.replace("{input}", payload) for part in cmd]

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            input=payload,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        return {"case": case, "passed": False, "problems": [f"超时 > {timeout}s"], "ms": timeout * 1000}
    except FileNotFoundError:
        return {"case": case, "passed": False, "problems": [f"命令不存在: {argv[0]}"], "ms": 0}

    elapsed_ms = (time.perf_counter() - started) * 1000
    problems = check(case, proc.stdout, proc.returncode)
    if proc.returncode != 0 and case.get("expect", {}).get("exit_code") is None:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        problems.append(f"非零退出码 {proc.returncode}: {tail[0][:160]}")
    return {"case": case, "passed": not problems, "problems": problems, "ms": elapsed_ms, "stdout": proc.stdout}


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 agent 评测用例")
    parser.add_argument("project", nargs="?", default=".", help="项目目录（含 evals/config.json）")
    parser.add_argument("--update-baseline", action="store_true", help="全部通过时写入基线")
    parser.add_argument("--tag", help="只跑含该标签的用例")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印每个用例的输出")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    config_path = project / "evals" / "config.json"
    if not config_path.exists():
        print(f"{RED}找不到 {config_path}{RESET}")
        return 1
    config = json.loads(config_path.read_text(encoding="utf-8"))

    cases_dir = project / "evals" / config.get("cases_dir", "cases")
    cases = load_cases(cases_dir, args.tag)
    if not cases:
        print(f"{YELLOW}没有可跑的用例（{cases_dir}）{RESET}")
        return 1

    cmd = config["cmd"]
    timeout = float(config.get("timeout_sec", 60))
    print(f"跑 {len(cases)} 条用例  cmd={' '.join(cmd)}  cwd={project}")
    print("-" * 64)

    results = []
    for case in cases:
        result = run_case(case, cmd, project, timeout)
        results.append(result)
        mark = f"{GREEN}通过{RESET}" if result["passed"] else f"{RED}失败{RESET}"
        tags = ",".join(case.get("tags", []))
        print(f"{mark}  {case['id']:<18} {result['ms']:7.0f}ms  {DIM}{tags}{RESET}")
        if not result["passed"]:
            for problem in result["problems"]:
                print(f"        {RED}· {problem}{RESET}")
        if args.verbose:
            print(f"        {DIM}{result.get('stdout', '').strip()[:300]}{RESET}")

    passed = sum(1 for r in results if r["passed"])
    rate = passed / len(results)
    print("-" * 64)
    color = GREEN if passed == len(results) else (YELLOW if rate >= 0.85 else RED)
    print(f"通过率 {color}{passed}/{len(results)} = {rate:.1%}{RESET}")

    baseline_path = project / "evals" / config.get("baseline", "baseline.json")
    tolerance = float(config.get("tolerance", 0.05))
    regressed = False
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        old_rate = baseline.get("rate", 0)
        delta = rate - old_rate
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        print(f"基线 {old_rate:.1%} {arrow} {rate:.1%}（{delta:+.1%}，容差 {tolerance:.0%}）")
        if delta < -tolerance:
            regressed = True
            print(f"{RED}判定为回归：跌幅超过容差{RESET}")

    if args.update_baseline:
        if passed == len(results):
            baseline_path.write_text(
                json.dumps(
                    {
                        "rate": rate,
                        "passed": passed,
                        "total": len(results),
                        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "cases": {r["case"]["id"]: r["passed"] for r in results},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"{GREEN}基线已更新: {baseline_path}{RESET}")
        else:
            print(f"{YELLOW}存在失败用例，不更新基线{RESET}")

    if regressed:
        return 2
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
