#!/usr/bin/env python3
"""nightly_gap.py — 不眠计划 · AutoInfo 差距计算器（L2-a）

作用：把「当前产出 vs 完成定义（DoD）」的差距算成一份机器可读矩阵。
它是 **冻结区** 的一部分：coding agent 只跑、不改。

DoD（见 docs/dev/plans/NIGHTLY.md §完成定义）：21 个域，每域四条件同时成立
  ① 真语料     该域 collected entries > 0
  ② 真产物     该域 outputs/<domain>/ 下有持久化产物
  ③ 可溯源     产物断言无 P0/P1 失败（来源/占位/空壳 均由断言集覆盖）
  ④ 无占位     同上（占位符断言属于 P0/P1 集合）

用法::

    .venv/bin/python scripts/nightly_gap.py [--json-out PATH] [--md-out PATH]
        [--domains-dir src/autoinfo/data/domains] [--outputs outputs]
        [--skip-assertions]      # 只算 ①②，跳过断言（更快）

退出码（可直接当夜间循环的判据）::

    0 — 21 个域全部达标（差距归零 → 本计划完成）
    1 — 仍有差距（把 gap 列表交给下一轮）
    2 — 用法/环境错误（不是差距，是需要人介入的信号）

不含 LLM、不联网、确定性：只读 ``autoinfo status`` 的 JSON、``outputs/`` 的文件系统，
以及 ``scripts/real_product_assertions.py`` 的确定性断言集。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DOMAINS_DIR = REPO / "src" / "autoinfo" / "data" / "domains"
DEFAULT_OUTPUTS = REPO / "outputs"


def _run(cmd: list[str], timeout: int = 900) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def domain_names(domains_dir: Path) -> list[str]:
    out = []
    for d in sorted(domains_dir.iterdir()):
        if d.is_dir() and (d / "sources.yaml").exists():
            out.append(d.name)
    return out


def _autoinfo_cmd(python: str) -> list[str]:
    """优先用与解释器同 venv 的 console script；退回 `-m autoinfo`。"""
    # 注意：不能用 resolve()，venv 的 bin/python 是软链，解开会跑到系统目录
    cand = python if "/" not in python else str(Path(python).absolute().parent / "autoinfo")
    if cand != python and Path(cand).exists():
        return [cand]
    return [python, "-m", "autoinfo"]


def status_by_domain(python: str) -> dict[str, dict]:
    """`autoinfo --json status` → {domain: {entries, sources_ran, sources_total}}"""
    rc, out, err = _run(_autoinfo_cmd(python) + ["--json", "status"], timeout=300)
    if rc != 0:
        raise RuntimeError(f"autoinfo status 退出码 {rc}: {err.strip()[:400]}")
    # stdout 必须只有 JSON（DoD-A2）；若被污染则显式失败，不猜
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"autoinfo status 的 stdout 不是合法 JSON（{e}）: {out[:200]!r}")
    data = payload.get("data") or {}
    res: dict[str, dict] = {}
    for d in data.get("domains") or []:
        name = d.get("name")
        if not name:
            continue
        health = d.get("source_health") or []
        res[name] = {
            "entries": int(d.get("total_entries") or 0),
            "sources_total": len(health),
            "sources_ran": sum(1 for s in health if int(s.get("total_runs") or 0) > 0),
            "sources_healthy": sum(1 for s in health if str(s.get("status")) == "healthy"),
        }
    return res


def outputs_by_domain(outputs: Path) -> dict[str, list[str]]:
    res: dict[str, list[str]] = {}
    if not outputs.exists():
        return res
    for d in sorted(outputs.iterdir()):
        if not d.is_dir() or d.name == "coverage-matrix":
            continue
        files = [f.name for f in d.iterdir() if f.is_file() and not f.name.startswith(".")]
        res[d.name] = files
    return res


def assertions_by_domain(python: str, outputs: Path) -> tuple[dict[str, int], str]:
    """跑断言扫描器，按产物路径归属到域。返回 ({domain: P0/P1 失败数}, 人读摘要)。"""
    with tempfile.TemporaryDirectory() as td:
        jp = Path(td) / "assertions.json"
        rc, out, err = _run([
            python, "scripts/real_product_assertions.py",
            "--roots", str(outputs), "--json-out", str(jp),
        ], timeout=1800)
        if not jp.exists():
            return {}, f"断言扫描器未产出 JSON（rc={rc}）: {(err or out).strip()[:300]}"
        payload = json.loads(jp.read_text(encoding="utf-8"))
    per: dict[str, int] = {}
    for f in payload.get("failures") or []:
        path = str(f.get("file") or f.get("path") or "")
        parts = Path(path).parts
        # 路径可能是相对的（outputs/<domain>/...）也可能是绝对的
        # （/mnt/.../AutoInfo/outputs/<domain>/...）——统一按 'outputs' 锚点取下一段。
        if "outputs" in parts:
            i = parts.index("outputs")
            dom = parts[i + 1] if len(parts) > i + 1 else "?"
        else:
            dom = parts[-2] if len(parts) >= 2 else "?"
        per[dom] = per.get(dom, 0) + 1
    t = payload.get("totals") or {}
    n_assert = len(payload.get("assertions") or [])
    summary = (f"断言集 {n_assert} 项；扫描 {payload.get('files_scanned')} 个文件；"
               f"失败合计 {t.get('failures', sum(per.values()))}")
    return per, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nightly_gap.py")
    ap.add_argument("--domains-dir", default=str(DEFAULT_DOMAINS_DIR))
    ap.add_argument("--outputs", default=str(DEFAULT_OUTPUTS))
    ap.add_argument("--python", default=sys.executable,
                    help="用哪个解释器跑仓库脚本（须是项目 venv）")
    ap.add_argument("--skip-assertions", action="store_true")
    ap.add_argument(
        "--min-entries", type=int, default=10,
        help="每个域的最少语料条数（默认 10：低于此数撑不起一期 digest 的选题）")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--md-out", default="")
    args = ap.parse_args(argv)

    domains = domain_names(Path(args.domains_dir))
    if not domains:
        print("!! 找不到域目录", file=sys.stderr)
        return 2

    try:
        st = status_by_domain(args.python)
    except Exception as e:  # 环境/接口问题 ≠ 差距
        print(f"!! {e}", file=sys.stderr)
        return 2

    outs = outputs_by_domain(Path(args.outputs))

    if args.skip_assertions:
        per_assert: dict[str, int] = {}
        assert_summary = "（已跳过断言扫描）"
    else:
        per_assert, assert_summary = assertions_by_domain(args.python, Path(args.outputs))

    rows = []
    for dom in domains:
        s = st.get(dom, {})
        entries = s.get("entries", 0)
        ran = s.get("sources_ran", 0)
        files = outs.get(dom, [])
        n_assert = per_assert.get(dom, 0)
        missing = []
        # ① 真语料：必须有源**真的跑过**（runs>0），且条数达阈值。
        #    仅看 entries>0 不够 —— 实测 19 个域在"从未跑过任何源"时
        #    仍报 entries=1（幻影计数/残渣），那样的门槛会被空跑满足。
        if ran <= 0:
            missing.append("真语料（该域没有任何源跑过）")
        elif entries < args.min_entries:
            missing.append(f"真语料（{entries} 条 < 阈值 {args.min_entries}）")
        if not files:
            missing.append("真产物")
        if files and n_assert > 0:
            missing.append(f"可溯源/无占位（断言失败 {n_assert}）")
        rows.append(dict(
            domain=dom,
            entries=entries,
            sources_total=s.get("sources_total", 0),
            sources_ran=ran,
            sources_healthy=s.get("sources_healthy", 0),
            output_files=len(files),
            assertion_failures=n_assert,
            missing=missing,
            passing=not missing,
        ))

    passing = [r for r in rows if r["passing"]]
    gap = [r for r in rows if not r["passing"]]

    result = {
        "schema_version": 1,
        "tool": "nightly_gap.py",
        "project": "AutoInfo",
        "dod": "21 域 × (真语料 + 真产物 + 可溯源 + 无占位)",
        "total_units": len(rows),
        "passing_units": len(passing),
        "gap_units": len(gap),
        "assertion_summary": assert_summary,
        "units": rows,
    }

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    verdict = ("- 判定：**差距归零（完成）**" if not gap
               else f"- 判定：**{len(gap)} / {len(rows)} 个域仍有差距**")
    md = ["# AutoInfo 差距矩阵", "", verdict,
          f"- 断言：{assert_summary}", "",
          "| 域 | 语料 | 已跑源/总源 | 产物文件 | 断言失败 | 缺什么 |",
          "|:---|---:|:---|--:|--:|:---|"]
    for r in rows:
        md.append(f"| {r['domain']} | {r['entries']} | {r['sources_ran']}/{r['sources_total']} | "
                  f"{r['output_files']} | {r['assertion_failures']} | "
                  f"{'、'.join(r['missing']) if r['missing'] else '✅ 达标'} |")
    md_text = "\n".join(md) + "\n"
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(md_text, encoding="utf-8")

    print(md_text)
    return 0 if not gap else 1


if __name__ == "__main__":
    sys.exit(main())
