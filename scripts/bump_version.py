#!/usr/bin/env python3
"""
版號管理工具 — 單一來源 VERSION 檔案，自動同步至所有檔案。

用法：
    python scripts/bump_version.py --check             # 檢查版號一致性
    python scripts/bump_version.py --bump patch        # 遞增 patch (1.0.0 → 1.0.1)
    python scripts/bump_version.py --bump minor        # 遞增 minor (1.0.0 → 1.1.0)
    python scripts/bump_version.py --bump major        # 遞增 major (1.0.0 → 2.0.0)
    python scripts/bump_version.py --bump 1.2.0        # 指定版號
    python scripts/bump_version.py --bump 1.2.0 --tag  # 更新 + commit + tag
    python scripts/bump_version.py --bump patch --dry-run  # 預覽，不寫入

--tag 流程：bump → git add → git commit → git tag（tag 永遠指向含新版號的 commit）。
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"

# ── 需要同步版號的檔案與替換規則 ──────────────────────────────
# 每條規則: (相對路徑, regex pattern, replacement template)
# replacement template 中 {v} 會被替換為新版號
#
# backend/main.py 從 VERSION 檔案讀取（runtime），不在此列。
TARGETS = [
    (
        "Dockerfile",
        r'(version=")[0-9]+\.[0-9]+\.[0-9]+(")',
        'version="{v}"',
    ),
    (
        "README.md",
        r"(追蹤紀錄系統 v)[0-9]+\.[0-9]+\.[0-9]+",
        "追蹤紀錄系統 v{v}",
    ),
    (
        "CLAUDE.md",
        r"(System v)[0-9]+\.[0-9]+\.[0-9]+",
        "System v{v}",
    ),
]

_VER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_version() -> str:
    """讀取 VERSION 檔案。"""
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def write_version(version: str) -> None:
    """寫入 VERSION 檔案。"""
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")


def calc_next_version(current: str, bump_type: str) -> str:
    """計算下一版號。bump_type = patch | minor | major | X.Y.Z"""
    parts = current.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f"ERROR: 無法解析目前版號 '{current}'，格式須為 X.Y.Z")
        sys.exit(1)

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        return bump_type  # 直接指定版號，由呼叫端驗證格式

    return f"{major}.{minor}.{patch}"


def sync_files(version: str, dry_run: bool = False) -> list[tuple[str, str]]:
    """同步版號至所有目標檔案。回傳 [(filepath, status), ...]。

    status: UPDATED | NO_CHANGE | NO_MATCH | NOT_FOUND
    """
    results = []
    for rel_path, pattern, template in TARGETS:
        filepath = ROOT / rel_path
        if not filepath.exists():
            results.append((rel_path, "NOT_FOUND"))
            continue

        content = filepath.read_text(encoding="utf-8")
        replacement = template.format(v=version)
        new_content, count = re.subn(pattern, replacement, content)

        if count == 0:
            results.append((rel_path, "NO_MATCH"))
        elif new_content == content:
            results.append((rel_path, "NO_CHANGE"))
        else:
            if not dry_run:
                filepath.write_text(new_content, encoding="utf-8")
            results.append((rel_path, "UPDATED"))

    return results


def check_consistency() -> bool:
    """檢查所有檔案版號是否與 VERSION 一致。"""
    version = read_version()
    print(f"VERSION file: {version}")

    all_ok = True
    for rel_path, pattern, template in TARGETS:
        filepath = ROOT / rel_path
        if not filepath.exists():
            print(f"  SKIP  {rel_path} (not found)")
            continue

        content = filepath.read_text(encoding="utf-8")
        expected = template.format(v=version)

        if expected in content:
            print(f"  OK    {rel_path}")
        else:
            match = re.search(pattern, content)
            actual = match.group(0) if match else "(pattern not found)"
            print(f"  DRIFT {rel_path}: found '{actual}', expected '{expected}'")
            all_ok = False

    return all_ok


def _git_working_tree_clean() -> bool:
    """檢查 git working tree 是否乾淨。"""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return result.stdout.strip() == ""


def create_release_commit_and_tag(version: str) -> bool:
    """建立 release commit + tag。確保 tag 指向含新版號的 commit。"""
    tag = f"v{version}"

    # 檢查 tag 是否已存在
    result = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True, text=True, cwd=ROOT,
    )
    if tag in result.stdout.strip().split("\n"):
        print(f"ERROR: tag '{tag}' already exists")
        sys.exit(1)

    # Stage 所有被 bump 修改的檔案
    files_to_stage = ["VERSION"] + [t[0] for t in TARGETS if (ROOT / t[0]).exists()]
    subprocess.run(
        ["git", "add"] + files_to_stage,
        check=True, cwd=ROOT,
    )

    # Commit
    subprocess.run(
        ["git", "commit", "-m", f"chore: bump version to {tag}"],
        check=True, cwd=ROOT,
    )

    # Tag（現在指向包含新版號的 commit）
    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Release {tag}"],
        check=True, cwd=ROOT,
    )

    print(f"Created commit + tag: {tag}")
    print(f"  Push with: git push origin main {tag}")
    return True


def main():
    parser = argparse.ArgumentParser(description="版號管理工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="檢查版號一致性")
    group.add_argument(
        "--bump", metavar="VERSION",
        help="更新版號 (X.Y.Z | patch | minor | major)",
    )
    parser.add_argument("--tag", action="store_true", help="同時 commit + 建立 git tag")
    parser.add_argument("--dry-run", action="store_true", help="只顯示變更，不寫入")

    args = parser.parse_args()

    if args.check:
        ok = check_consistency()
        sys.exit(0 if ok else 1)

    # --bump 必須有值
    if not args.bump:
        print("ERROR: --bump 需要版號參數 (patch | minor | major | X.Y.Z)")
        sys.exit(1)

    current = read_version()
    new_version = calc_next_version(current, args.bump)

    if not _VER_RE.match(new_version):
        print(f"ERROR: 版號格式錯誤 '{new_version}'，須為 X.Y.Z")
        sys.exit(1)

    if new_version == current:
        print(f"版號未變更: {current}")
        sys.exit(0)

    # --tag 前檢查 working tree
    if args.tag and not args.dry_run:
        if not _git_working_tree_clean():
            print("ERROR: working tree 有未 commit 的變更，請先 commit 或 stash")
            print("  --tag 會自動 commit 版號變更，不能與其他變更混合")
            sys.exit(1)

    print(f"Bumping: {current} → {new_version}")

    if not args.dry_run:
        write_version(new_version)

    results = sync_files(new_version, dry_run=args.dry_run)

    has_error = False
    for rel_path, status in results:
        label = status
        if args.dry_run and status == "UPDATED":
            label = "WOULD UPDATE"
        if status == "NO_MATCH":
            label = "⚠ NO_MATCH"
            has_error = True
        print(f"  {label:16s} {rel_path}")

    if has_error:
        print("\nWARNING: 部分檔案的 regex pattern 沒有 match，請檢查 TARGETS 設定")

    if args.dry_run:
        print("\n(dry run — no files changed)")
        return

    print(f"\nVERSION → {new_version}")

    if args.tag:
        create_release_commit_and_tag(new_version)
    else:
        print("Remember to update CHANGELOG.md and commit before tagging.")


if __name__ == "__main__":
    main()
