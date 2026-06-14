"""營運者環境驗證：依賴、設定、RabbitMQ、pytest。

用法：
    uv run python scripts/verify_setup.py
    uv run python scripts/verify_setup.py --smoke-dedup
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GETTING_STARTED = "docs/getting-started.md"
PLACEHOLDER_CHANNELS = frozenset({"", "your_channel"})


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    hint: str = ""


def check_python_version(*, min_major: int = 3, min_minor: int = 11) -> CheckResult:
    version = sys.version_info
    ok = (version.major, version.minor) >= (min_major, min_minor)
    detail = f"{version.major}.{version.minor}.{version.micro}"
    hint = "請安裝 Python 3.11 以上：https://www.python.org/downloads/" if not ok else ""
    return CheckResult("python_version", ok, detail, hint)


def check_uv_available() -> CheckResult:
    path = shutil.which("uv")
    ok = path is not None
    detail = path or "找不到 uv"
    hint = "請安裝 uv：https://docs.astral.sh/uv/getting-started/installation/" if not ok else ""
    return CheckResult("uv", ok, detail, hint)


def check_workspace_packages(root: Path = ROOT) -> CheckResult:
    packages = (
        ("ttvchat-lens", root / "packages" / "ttvchat-lens" / "src" / "ttvchat_lens"),
        ("tubechat-lens", root / "packages" / "tubechat-lens" / "src" / "tubechat_lens"),
    )
    missing = [name for name, path in packages if not path.is_dir()]
    ok = not missing
    if ok:
        detail = "ttvchat-lens, tubechat-lens"
        hint = ""
    else:
        detail = f"缺少：{', '.join(missing)}"
        hint = f"請確認已完整 clone 本 repo（見 {GETTING_STARTED} §0.1）"
    return CheckResult("workspace_packages", ok, detail, hint)


def parse_env_channel(env_path: Path) -> str | None:
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("TWITCH_CHANNEL="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def check_env_file(root: Path = ROOT) -> CheckResult:
    env_path = root / ".env"
    if not env_path.is_file():
        return CheckResult(
            "env_file",
            False,
            "找不到 .env",
            f"請執行：copy .env.example .env（見 {GETTING_STARTED} §0.1）",
        )

    channel = parse_env_channel(env_path)
    if channel is None:
        return CheckResult(
            "env_file",
            False,
            ".env 缺少 TWITCH_CHANNEL",
            f"請在 .env 設定 TWITCH_CHANNEL=你的頻道名（見 {GETTING_STARTED} §0.1）",
        )

    if channel.lower() in PLACEHOLDER_CHANNELS:
        return CheckResult(
            "env_file",
            False,
            f"TWITCH_CHANNEL={channel!r} 仍為範本值",
            "請將 TWITCH_CHANNEL 改為實際 Twitch 頻道名（不含 #）",
        )

    return CheckResult("env_file", True, f"TWITCH_CHANNEL={channel}")


def check_rabbitmq(url: str | None = None) -> CheckResult:
    if url is None:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        from bus.config import rabbitmq_url

        url = rabbitmq_url()

    try:
        from bus.rabbitmq import connect_blocking

        connection = connect_blocking(url)
        connection.close()
    except Exception as exc:
        return CheckResult(
            "rabbitmq",
            False,
            str(exc),
            "請執行 docker compose up -d，並確認 RABBITMQ_URL 正確",
        )

    return CheckResult("rabbitmq", True, url)


def run_pytest(root: Path = ROOT) -> CheckResult:
    result = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    tail = "\n".join(output.splitlines()[-5:]) if output else "(無輸出)"
    if result.returncode == 0:
        return CheckResult("pytest", True, tail)

    return CheckResult(
        "pytest",
        False,
        tail,
        "請修正失敗測試或回報問題；開發者見 docs/development.md",
    )


def run_dedup_smoke(root: Path = ROOT) -> CheckResult:
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "verify_dedup.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    ok = result.returncode == 0 and "VERIFICATION_PASS" in output
    tail = "\n".join(output.splitlines()[-3:]) if output else "(無輸出)"
    if ok:
        return CheckResult("dedup_smoke", True, tail)
    return CheckResult(
        "dedup_smoke",
        False,
        tail,
        "跨 process 去重自測失敗，見 scripts/verify_dedup.py",
    )


def run_checks(*, root: Path = ROOT, smoke_dedup: bool = False) -> list[CheckResult]:
    checks = [
        check_python_version(),
        check_uv_available(),
        check_workspace_packages(root),
        check_env_file(root),
        check_rabbitmq(),
        run_pytest(root),
    ]
    if smoke_dedup:
        checks.append(run_dedup_smoke(root))
    return checks


def print_results(results: list[CheckResult]) -> int:
    failures: list[CheckResult] = []
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[check] {status} {result.name}: {result.detail}")
        if not result.ok:
            failures.append(result)
            if result.hint:
                print(f"        → {result.hint}")

    print()
    if failures:
        names = ", ".join(item.name for item in failures)
        print(f"SETUP_VERIFICATION_FAIL ({len(failures)} 項：{names})")
        print(f"完整步驟見 {GETTING_STARTED}")
        return 1

    print("SETUP_VERIFICATION_PASS")
    print(f"下一步：手動 smoke 見 {GETTING_STARTED} §第 2 層")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="驗證 streamer-toolbox 營運者環境")
    parser.add_argument(
        "--smoke-dedup",
        action="store_true",
        help="額外執行跨 process 去重自測（verify_dedup.py）",
    )
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    results = run_checks(smoke_dedup=args.smoke_dedup)
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
