#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_pdf.py — PDF 下载与文本提取脚本

功能：
  1. 从 URL 下载 PDF（或使用本地已有 PDF）
  2. 命名为 NNN_src_XXX.pdf，文本提取为 NNN_extract_XXX.txt，写入 output-dir
  3. 提取策略：前 8 页 + 后 3 页（当总页数 > 8），每页最多 3000 字符
  4. 处理 Windows GBK 编码问题
  5. 以 JSON 输出结果到 stdout

依赖：PyMuPDF (fitz), requests

用法：
  # 从 URL 下载并提取
  python extract_pdf.py --url "https://arxiv.org/pdf/2602.10453" \\
      --number 104 --name Wang_PromptInjection_LLM --output-dir "d:/WS/t5/参考资料/104_Wang_PromptInjection_LLM"

  # 使用本地已有 PDF
  python extract_pdf.py --file "d:/downloads/paper.pdf" \\
      --number 104 --name Wang_PromptInjection_LLM --output-dir "..."

输出（stdout，JSON）：
  {"pdf_path": "...", "extract_path": "...", "pages": N, "chars": N, "success": true}

退出码：0=成功；1=失败（下载/提取错误，详见 JSON 与 stderr）；2=参数错误。
"""
import argparse
import io
import json
import os
import re
import sys

# 修复 Windows 下 GBK 编码问题，强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HEAD_PAGES = 8          # 提取前 N 页
TAIL_PAGES = 3          # 总页数超过 HEAD_PAGES 时，追加提取末尾 N 页
CHARS_PER_PAGE = 3000   # 每页最多提取字符数


def _safe_name(name):
    """将描述性名称规范化为可用作文件名的形式（保留中英文数字下划线，其余转下划线）"""
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|\s]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "unnamed"


def download_pdf(url, dest_path):
    """下载 PDF 到 dest_path，返回 (ok, message)"""
    try:
        import requests
    except ImportError:
        return False, "缺少依赖 requests（pip install requests）"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; lit-research/1.0; academic use)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=60, stream=True)
        if resp.status_code != 200:
            return False, "HTTP %d 下载失败: %s" % (resp.status_code, url)
        ctype = resp.headers.get("Content-Type", "").lower()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        size = os.path.getsize(dest_path)
        if size < 1024:
            return False, "下载文件过小（%d 字节），可能不是有效 PDF" % size
        # PDF 魔数校验（部分站点返回 HTML 错误页）
        with open(dest_path, "rb") as f:
            magic = f.read(5)
        if magic != b"%PDF-":
            return False, "下载内容不是 PDF（魔数=%r，Content-Type=%s）" % (magic, ctype)
        return True, "已下载 %d 字节" % size
    except Exception as e:  # noqa: BLE001
        return False, "下载异常: %s" % e


def extract_text(pdf_path, extract_path):
    """按策略提取 PDF 文本写入 extract_path，返回 (ok, pages, chars, message)"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return False, 0, 0, "缺少依赖 PyMuPDF（pip install PyMuPDF）"
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:  # noqa: BLE001
        return False, 0, 0, "无法打开 PDF: %s" % e

    total_pages = doc.page_count
    head_end = min(HEAD_PAGES, total_pages)
    parts = []
    parts.append("文件: %s" % os.path.basename(pdf_path))
    parts.append("总页数: %d" % total_pages)
    parts.append("=" * 60)

    def _page_indices():
        idxs = list(range(head_end))
        if total_pages > HEAD_PAGES:
            start = max(HEAD_PAGES, total_pages - TAIL_PAGES)
            idxs += list(range(start, total_pages))
        return idxs

    char_count = 0
    for i in _page_indices():
        try:
            text = doc[i].get_text()
        except Exception:  # noqa: BLE001
            text = ""
        if text.strip():
            near_end = " (near end)" if i >= head_end else ""
            parts.append("\n--- Page %d%s ---" % (i + 1, near_end))
            parts.append(text[:CHARS_PER_PAGE])
            char_count += len(text[:CHARS_PER_PAGE])
    doc.close()

    if char_count == 0:
        return False, total_pages, 0, "未提取到文本（可能是扫描图片型 PDF，需 OCR）"

    with open(extract_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return True, total_pages, char_count, "提取完成"


def main():
    parser = argparse.ArgumentParser(
        prog="extract_pdf.py",
        description="下载 PDF 并提取文本（前8页+后3页，每页3000字），输出 JSON。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", metavar="URL", help="从此 URL 下载 PDF")
    src.add_argument("--file", metavar="PATH", help="使用本地已有 PDF 文件")
    parser.add_argument("--number", metavar="NNN", required=True,
                        help="文献编号（3 位数字，如 104）")
    parser.add_argument("--name", metavar="XXX", required=True,
                        help="描述性名称（用于文件命名，如 Wang_PromptInjection_LLM）")
    parser.add_argument("--output-dir", metavar="DIR", required=True,
                        help="输出目录（src/extract 文件写于此）")
    args = parser.parse_args()

    # 规范化编号为 3 位
    num = args.number.strip()
    if not num.isdigit():
        print("错误：--number 必须是数字，收到 %r" % args.number, file=sys.stderr)
        sys.exit(2)
    num = "%03d" % int(num)
    name = _safe_name(args.name)

    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    pdf_path = os.path.abspath(os.path.join(out_dir, "%s_src_%s.pdf" % (num, name)))
    extract_path = os.path.abspath(os.path.join(out_dir, "%s_extract_%s.txt" % (num, name)))

    result = {
        "pdf_path": pdf_path,
        "extract_path": extract_path,
        "pages": 0,
        "chars": 0,
        "success": False,
        "message": "",
    }

    # 1) 获取 PDF
    if args.url:
        ok, msg = download_pdf(args.url, pdf_path)
        if not ok:
            result["message"] = msg
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("错误：%s" % msg, file=sys.stderr)
            sys.exit(1)
        print("下载：%s" % msg, file=sys.stderr)
    else:
        if not os.path.isfile(args.file):
            result["message"] = "本地文件不存在: %s" % args.file
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("错误：%s" % result["message"], file=sys.stderr)
            sys.exit(1)
        src_file = os.path.abspath(args.file)
        if src_file != pdf_path:
            try:
                import shutil
                shutil.copyfile(src_file, pdf_path)
            except OSError as e:
                result["message"] = "复制本地文件失败: %s" % e
                print(json.dumps(result, ensure_ascii=False, indent=2))
                print("错误：%s" % result["message"], file=sys.stderr)
                sys.exit(1)

    # 2) 提取文本
    ok, pages, chars, msg = extract_text(pdf_path, extract_path)
    result["pages"] = pages
    result["chars"] = chars
    result["message"] = msg
    result["success"] = ok

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ok:
        print("错误：%s" % msg, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
