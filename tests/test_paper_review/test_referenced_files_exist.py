#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_referenced_files_exist.py — 条目24 守卫②：文档引用文件存在性

扫描 SKILL.md 与 references/*.md 中出现的 `scripts/*`、`templates/*`、
`references/*` 路径提及，任一不存在即 fail（防止 format-notes.md 曾出现的
「引用悬空脚本路径」类漂移：文档教用户调一个仓库里根本没有的文件）。

反向守卫：scripts/*.py、numeric_checks/、templates/*.md、references/*.md
必须被 SKILL.md 收录（脚本清单/模板表/正文提及），防止「文件在、文档漏」
导致孤儿产物。新增文件时：要么写入 SKILL.md，要么它就不是技能的一部分。

运行：python tests/test_paper_review/test_referenced_files_exist.py
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "paper-review")
REFERENCES_DIR = os.path.join(SKILL_DIR, "references")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")

# scripts/<name>[.py] | templates/<name.ext> | references/<name.ext>
# 名字字符类只含 ASCII，全角标点/反引号/括号天然截断
PATH_MENTION_RE = re.compile(r"\b(scripts|templates|references)/([A-Za-z0-9_.-]+)")

# 至少应扫到这些提及（防正则失配空转假通过）
EXPECTED_MENTIONS = {
    ("scripts", "setup_env.py"),
    ("scripts", "migrate_layout.py"),
    ("scripts", "numeric_checks"),
    ("templates", "final-report.md"),
    ("templates", "chain.md"),
    ("references", "re-review-protocol.md"),
    ("references", "format-notes.md"),
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def scan_docs():
    """[(kind, name, 来源文件, 行号)] — SKILL.md + references/*.md 的全部路径提及。"""
    docs = [SKILL_MD]
    for fn in sorted(os.listdir(REFERENCES_DIR)):
        if fn.endswith(".md"):
            docs.append(os.path.join(REFERENCES_DIR, fn))
    hits = []
    for doc in docs:
        for lineno, line in enumerate(read(doc).splitlines(), 1):
            for kind, name in PATH_MENTION_RE.findall(line):
                hits.append((kind, name, os.path.basename(doc), lineno))
    return hits


def resolve(kind, name):
    """提及 → (期望路径, 校验方式)。带扩展名按文件校验；不带扩展名
    （numeric_checks）文件或目录任一存在即可。"""
    path = os.path.join(SKILL_DIR, kind, name)
    return path, ("file" if "." in name else "any")


class TestMentionedPathsExist(unittest.TestCase):

    def test_all_mentioned_paths_exist(self):
        missing = []
        for kind, name, src, lineno in scan_docs():
            path, mode = resolve(kind, name)
            ok = os.path.isfile(path) if mode == "file" else os.path.exists(path)
            if not ok:
                missing.append("%s/%s（%s:%d 引用）" % (kind, name, src, lineno))
        self.assertFalse(missing, "文档引用了不存在的路径:\n" + "\n".join(missing))

    def test_meta_scan_not_vacuous(self):
        found = {(kind, name) for kind, name, _, _ in scan_docs()}
        missing = EXPECTED_MENTIONS - found
        self.assertFalse(missing, "提及扫描缺期望项（正则失配？）: %s" % sorted(missing))
        self.assertGreaterEqual(len(found), 15, "提及总数异常偏少: %d" % len(found))


class TestNoOrphanArtifacts(unittest.TestCase):
    """反向：技能目录内的脚本/模板/参考文件必须被 SKILL.md 收录。"""

    @classmethod
    def setUpClass(cls):
        cls.skill_text = read(SKILL_MD)

    def _assert_listed(self, subdir, suffix):
        names = [fn for fn in sorted(os.listdir(os.path.join(SKILL_DIR, subdir)))
                 if fn.endswith(suffix) and not fn.startswith(("_", "."))]
        self.assertTrue(names, "%s/ 下未找到 %s 文件" % (subdir, suffix))
        orphans = [fn for fn in names if fn not in self.skill_text]
        self.assertFalse(orphans,
                         "%s/ 中存在 SKILL.md 未收录的孤儿文件: %s" % (subdir, orphans))

    def test_all_scripts_listed(self):
        self._assert_listed("scripts", ".py")
        self.assertIn("numeric_checks", self.skill_text)

    def test_all_templates_listed(self):
        self._assert_listed("templates", ".md")

    def test_all_references_listed(self):
        self._assert_listed("references", ".md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
