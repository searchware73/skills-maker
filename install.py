#!/usr/bin/env python3
"""skills-maker 安装工具

用法：
  python install.py install <skill-name>    安装技能到 ~/.claude/skills/
  python install.py uninstall <skill-name>  卸载技能
  python install.py link <skill-name>       开发模式：创建符号链接
  python install.py unlink <skill-name>     移除符号链接
  python install.py list                    列出可用和已安装技能
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"
TARGET_DIR = Path.home() / ".claude" / "skills"


def get_available_skills():
    """列出 skills/ 下所有可用技能"""
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        d.name for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def get_installed_skills():
    """列出 ~/.claude/skills/ 下已安装的技能"""
    if not TARGET_DIR.exists():
        return []
    return sorted(
        d.name for d in TARGET_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def install_skill(name: str):
    """复制技能目录到 ~/.claude/skills/"""
    src = SKILLS_DIR / name
    dst = TARGET_DIR / name

    if not src.exists():
        print(f"错误：技能 '{name}' 不存在于 {SKILLS_DIR}", file=sys.stderr)
        sys.exit(1)

    if not (src / "SKILL.md").exists():
        print(f"错误：{src} 缺少 SKILL.md", file=sys.stderr)
        sys.exit(1)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        if dst.is_symlink():
            print(f"提示：'{name}' 当前是符号链接，先移除...")
            dst.unlink()
        else:
            print(f"提示：'{name}' 已安装，覆盖...")
            shutil.rmtree(dst)

    shutil.copytree(src, dst)
    print(f"✓ 已安装 '{name}' → {dst}")
    print(f"  重启 Claude Code 后生效（/help 查看技能列表）")


def uninstall_skill(name: str):
    """从 ~/.claude/skills/ 移除技能"""
    dst = TARGET_DIR / name

    if not dst.exists():
        print(f"提示：'{name}' 未安装", file=sys.stderr)
        sys.exit(1)

    if dst.is_symlink():
        dst.unlink()
        print(f"✓ 已移除符号链接 '{name}'")
    else:
        shutil.rmtree(dst)
        print(f"✓ 已卸载 '{name}'")


def link_skill(name: str):
    """创建符号链接（开发模式）"""
    src = SKILLS_DIR / name
    dst = TARGET_DIR / name

    if not src.exists():
        print(f"错误：技能 '{name}' 不存在于 {SKILLS_DIR}", file=sys.stderr)
        sys.exit(1)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        if dst.is_symlink():
            dst.unlink()
        else:
            shutil.rmtree(dst)

    try:
        dst.symlink_to(src.resolve(), target_is_directory=True)
        print(f"✓ 已链接 '{name}' → {src.resolve()}")
        print(f"  修改即时生效（无需重启）")
    except OSError as e:
        print(f"错误：创建符号链接失败: {e}", file=sys.stderr)
        print("提示：Windows 需要管理员权限或开发者模式", file=sys.stderr)
        sys.exit(1)


def unlink_skill(name: str):
    """移除符号链接"""
    dst = TARGET_DIR / name
    if dst.is_symlink():
        dst.unlink()
        print(f"✓ 已移除链接 '{name}'")
    else:
        print(f"提示：'{name}' 不是符号链接", file=sys.stderr)


def list_skills():
    """列出所有技能状态"""
    available = get_available_skills()
    installed = get_installed_skills()

    print("\n可用技能（skills/ 目录）：")
    for name in available:
        status = []
        dst = TARGET_DIR / name
        if dst.is_symlink():
            status.append("已链接")
        elif name in installed:
            status.append("已安装")
        status_str = f" [{', '.join(status)}]" if status else ""
        print(f"  • {name}{status_str}")

    if not available:
        print("  （无）")

    print(f"\n安装目录：{TARGET_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="skills-maker 技能安装工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    sub = parser.add_subparsers(dest="command", help="操作")

    for cmd in ["install", "uninstall", "link", "unlink"]:
        p = sub.add_parser(cmd)
        p.add_argument("name", help="技能名称")

    sub.add_parser("list", help="列出技能")

    args = parser.parse_args()

    if args.command == "install":
        install_skill(args.name)
    elif args.command == "uninstall":
        uninstall_skill(args.name)
    elif args.command == "link":
        link_skill(args.name)
    elif args.command == "unlink":
        unlink_skill(args.name)
    elif args.command == "list":
        list_skills()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
