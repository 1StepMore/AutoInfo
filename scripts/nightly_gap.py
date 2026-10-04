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
        [--collections collections]
        [--skip-assertions]      # 只算 ①②，跳过断言（更快）

退出码（可直接当夜间循环的判据）::

    0 — 21 个域全部达标（差距归零 → 本计划完成）
    1 — 仍有差距（把 gap 列表交给下一轮）
    2 — 用法/环境错误（不是差距，是需要人介入的信号）

不含 LLM、不联网、确定性：只读 ``autoinfo status`` 的 JSON、``outputs/`` 与
``collections/`` 的文件系统，以及 ``scripts/real_product_assertions.py`` 的确定性断言集。

「已跑」的三态口径（#455）
----------------------------
``_log_run``（src/autoinfo/collect.py）对 ``status="skipped"`` 也追加一条运行记录，
于是「被策略跳过的源」只要 ``_runs.json`` 非空就被算成已跑 —— 被应用审核闸 / robots 门
挡住的源在差距矩阵里伪装成覆盖。本脚本因此把每个源归成**互斥**的一态：

============= ==========================================================
``produced``  真跑过：有 success 运行且拿到过条目
``ran_empty`` 跑过但空：有 success 运行，条目恒为 0
``skipped``   被跳过：**最近一次**运行是 skipped（带原因）
``failed``    有运行记录，但一次都没成功（error/其它）
``never_ran`` 没有任何运行记录
============= ==========================================================

- skipped **不计**「已跑/覆盖」，也**不计**「采集失败/源损坏」——它是单独一类，
  原因从跳过条目的 errors 归纳（``app_review_required`` / ``robots_disallowed`` / 其它）。
- skipped 源**既不算 healthy 也不算 unhealthy**
  （``sources_unhealthy`` = 总数 − healthy − skipped）。
- 除 skipped 外的历史口径一律保持不变：error-only 的源仍算「已跑」。改 error 的记账
  是另一个决定，会在没有任何证据支撑的情况下移动整张矩阵的通过/不通过计数。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DOMAINS_DIR = REPO / "src" / "autoinfo" / "data" / "domains"
DEFAULT_OUTPUTS = REPO / "outputs"
DEFAULT_COLLECTIONS = REPO / "collections"

# -- 源的三态与跳过原因（#455）------------------------------------------------
STATE_PRODUCED = "produced"
STATE_RAN_EMPTY = "ran_empty"
STATE_SKIPPED = "skipped"
STATE_FAILED = "failed"
STATE_NEVER_RAN = "never_ran"

SKIP_REASON_APP_REVIEW = "app_review_required"
SKIP_REASON_ROBOTS = "robots_disallowed"
SKIP_REASON_OTHER = "other"


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


def _read_runs(collections: Path, domain: str, source: str) -> list[dict[str, Any]]:
    """读 ``collections/<domain>/<source>/_runs.json``；读不到/坏了就当没有记录。"""
    runs_file = collections / domain / source / "_runs.json"
    if not runs_file.is_file():
        return []
    try:
        payload = json.loads(runs_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(payload, list):
        return []
    return [r for r in payload if isinstance(r, dict)]


def _run_status(run: dict[str, Any]) -> str:
    """运行状态。缺 ``status`` 的历史条目按 success 读 —— 与 ``status.py`` 的
    ``run.get("status", "success")`` 保持同一口径，两边不能各读各的。"""
    return str(run.get("status") or "success")


def _run_has_items(run: dict[str, Any]) -> bool:
    return int(run.get("items_new") or 0) > 0 or int(run.get("items_found") or 0) > 0


def classify_skip_reason(runs: list[dict[str, Any]]) -> tuple[str, str]:
    """归纳被跳过的原因 → ``(reason_key, 简短说明)``。

    先读 errors 上的**显式标记**（``app_review_required`` / ``robots_disallowed``），
    读不到再退回 message 文本嗅探 —— handler 构造失败（collect.py 的 ValueError 分支）
    只写 message，没有标记。两个标记都有时 app_review 优先：它是「加一句 ack 就能解开」
    的可操作闸，优先级高于 robots 遵从性阻断；两者都没命中就归 ``other``。
    """
    errors: list[dict[str, Any]] = []
    for run in runs:
        if _run_status(run) != "skipped":
            continue
        for err in run.get("errors") or []:
            if isinstance(err, dict):
                errors.append(err)
    if not errors:
        return SKIP_REASON_OTHER, ""
    detail = next((str(e.get("message") or "") for e in errors if e.get("message")), "")
    if any(bool(e.get("app_review_required")) for e in errors):
        return SKIP_REASON_APP_REVIEW, detail
    if any(bool(e.get("robots_disallowed")) for e in errors):
        return SKIP_REASON_ROBOTS, detail
    blob = " ".join(str(e.get("message") or "") for e in errors).lower()
    if "app review" in blob or "app/interface review" in blob:
        return SKIP_REASON_APP_REVIEW, detail
    if "robots" in blob:
        return SKIP_REASON_ROBOTS, detail
    return SKIP_REASON_OTHER, detail


def source_run_state(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """把一个源的运行记录归成**互斥**的一态（#455）。

    边界语义：**最近一次运行决定 skipped**（而不是「历史上有过任一次成功」）。
    理由：这张矩阵是**当前**差距报表，策略跳过是一个当下可操作、待解开的阻断 ——
    一个曾经能采、现在被应用审核闸/robots 门挡住的源，在「任一成功」口径下会继续
    显示为已覆盖，#455 报的正是这种伪装；同时这个读法与 AutoInfo 自身健康逻辑
    取 ``runs[-1]`` 当 last_status/last_run 的口径一致，两边不会互相打架。
    历史跳过不丢：``runs_skipped`` 始终记录跳过条目的总次数。

    历史口径保留：非 skipped 的 error-only 源仍记为 ``failed``，且仍计入「已跑」
    （见模块 docstring —— 改 error 记账是另一个决定）。
    """
    if not runs:
        return {
            "state": STATE_NEVER_RAN,
            "skipped": False,
            "skip_reason": "",
            "skip_detail": "",
            "runs_total": 0,
            "runs_skipped": 0,
            "runs_productive": 0,
            "runs_empty": 0,
        }

    statuses = [_run_status(r) for r in runs]
    skip_runs = sum(1 for s in statuses if s == "skipped")
    productive = sum(1 for r, s in zip(runs, statuses) if s == "success" and _run_has_items(r))
    empty = sum(1 for r, s in zip(runs, statuses) if s == "success" and not _run_has_items(r))

    # skipped 优先于其它状态：最近一次是跳过，这一轮它就没产出。
    if statuses[-1] == "skipped":
        state = STATE_SKIPPED
    elif productive:
        state = STATE_PRODUCED
    elif empty:
        state = STATE_RAN_EMPTY
    else:
        state = STATE_FAILED

    reason, detail = classify_skip_reason(runs) if state == STATE_SKIPPED else ("", "")
    return {
        "state": state,
        "skipped": state == STATE_SKIPPED,
        "skip_reason": reason,
        "skip_detail": detail,
        "runs_total": len(runs),
        "runs_skipped": skip_runs,
        "runs_productive": productive,
        "runs_empty": empty,
    }


def summarize_sources(
    health: list[dict[str, Any]], collections: Path, domain: str
) -> dict[str, Any]:
    """``source_health`` + ``collections/`` → 域级覆盖统计（#455）。

    ``sources_ran`` = 「有过运行记录」减去「当前被策略跳过」，因此
    ``sources_productive + sources_ran_empty + sources_failed == sources_ran``
    （历史口径，见模块 docstring），跳过的源不落在这三者里。
    """
    states: dict[str, dict[str, Any]] = {}
    for src in health:
        name = str(src.get("name") or "")
        states[name] = source_run_state(_read_runs(collections, domain, name))

    ran_before = sum(1 for s in health if int(s.get("total_runs") or 0) > 0)
    skipped_names = sorted(n for n, st in states.items() if st["skipped"])
    healthy = sum(
        1
        for s in health
        if str(s.get("status")) == "healthy" and not states[str(s.get("name") or "")]["skipped"]
    )
    total = len(health)
    return {
        "sources_total": total,
        "sources_ran": ran_before - len(skipped_names),
        "sources_productive": sum(1 for st in states.values() if st["state"] == STATE_PRODUCED),
        "sources_ran_empty": sum(1 for st in states.values() if st["state"] == STATE_RAN_EMPTY),
        "sources_failed": sum(1 for st in states.values() if st["state"] == STATE_FAILED),
        "sources_skipped": len(skipped_names),
        # 跳过的源既不算 healthy 也不算 unhealthy（它是第三类，不是坏源）
        "sources_healthy": healthy,
        "sources_unhealthy": total - healthy - len(skipped_names),
        "skipped_sources": [
            {
                "source": name,
                "reason": states[name]["skip_reason"],
                "detail": states[name]["skip_detail"],
                "runs_total": states[name]["runs_total"],
                "runs_skipped": states[name]["runs_skipped"],
                "runs_productive": states[name]["runs_productive"],
            }
            for name in skipped_names
        ],
    }


def status_by_domain(python: str, collections: Path | None = None) -> dict[str, dict[str, Any]]:
    """`autoinfo --json status` → {domain: {entries, sources_ran, sources_total, ...}}"""
    col = Path(collections) if collections is not None else DEFAULT_COLLECTIONS
    rc, out, err = _run(_autoinfo_cmd(python) + ["--json", "status"], timeout=300)
    if rc != 0:
        raise RuntimeError(f"autoinfo status 退出码 {rc}: {err.strip()[:400]}")
    # stdout 必须只有 JSON（DoD-A2）；若被污染则显式失败，不猜
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"autoinfo status 的 stdout 不是合法 JSON（{e}）: {out[:200]!r}")
    data = payload.get("data") or {}
    res: dict[str, dict[str, Any]] = {}
    for d in data.get("domains") or []:
        name = d.get("name")
        if not name:
            continue
        health = d.get("source_health") or []
        res[name] = {
            "entries": int(d.get("total_entries") or 0),
            **summarize_sources(health, col, str(name)),
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
        rc, out, err = _run(
            [
                python,
                "scripts/real_product_assertions.py",
                "--roots",
                str(outputs),
                "--json-out",
                str(jp),
            ],
            timeout=1800,
        )
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
    summary = (
        f"断言集 {n_assert} 项；扫描 {payload.get('files_scanned')} 个文件；"
        f"失败合计 {t.get('failures', sum(per.values()))}"
    )
    return per, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nightly_gap.py")
    ap.add_argument("--domains-dir", default=str(DEFAULT_DOMAINS_DIR))
    ap.add_argument("--outputs", default=str(DEFAULT_OUTPUTS))
    ap.add_argument(
        "--collections",
        default=str(DEFAULT_COLLECTIONS),
        help="采集运行记录根目录（读 <domain>/<source>/_runs.json 判 skipped，#455）",
    )
    ap.add_argument(
        "--python", default=sys.executable, help="用哪个解释器跑仓库脚本（须是项目 venv）"
    )
    ap.add_argument("--skip-assertions", action="store_true")
    ap.add_argument(
        "--min-entries",
        type=int,
        default=10,
        help="每个域的最少语料条数（默认 10：低于此数撑不起一期 digest 的选题）",
    )
    ap.add_argument("--json-out", default="")
    ap.add_argument("--md-out", default="")
    args = ap.parse_args(argv)

    domains = domain_names(Path(args.domains_dir))
    if not domains:
        print("!! 找不到域目录", file=sys.stderr)
        return 2

    try:
        st = status_by_domain(args.python, Path(args.collections))
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
        skipped = s.get("sources_skipped", 0)
        files = outs.get(dom, [])
        n_assert = per_assert.get(dom, 0)
        missing = []
        # ① 真语料：必须有源**真的跑过**（runs>0），且条数达阈值。
        #    仅看 entries>0 不够 —— 实测 19 个域在"从未跑过任何源"时
        #    仍报 entries=1（幻影计数/残渣），那样的门槛会被空跑满足。
        #    策略跳过的源不算跑过（#455），但要说清是被闸挡住，不是源坏了。
        if ran <= 0:
            if skipped:
                missing.append(f"真语料（该域没有任何源跑过：{skipped} 个源被策略跳过）")
            else:
                missing.append("真语料（该域没有任何源跑过）")
        elif entries < args.min_entries:
            missing.append(f"真语料（{entries} 条 < 阈值 {args.min_entries}）")
        if not files:
            missing.append("真产物")
        if files and n_assert > 0:
            missing.append(f"可溯源/无占位（断言失败 {n_assert}）")
        rows.append(
            dict(
                domain=dom,
                entries=entries,
                sources_total=s.get("sources_total", 0),
                sources_ran=ran,
                sources_healthy=s.get("sources_healthy", 0),
                sources_productive=s.get("sources_productive", 0),
                sources_ran_empty=s.get("sources_ran_empty", 0),
                sources_failed=s.get("sources_failed", 0),
                sources_skipped=skipped,
                sources_unhealthy=s.get("sources_unhealthy", 0),
                skipped_sources=s.get("skipped_sources", []),
                output_files=len(files),
                assertion_failures=n_assert,
                missing=missing,
                passing=not missing,
            )
        )

    passing = [r for r in rows if r["passing"]]
    gap = [r for r in rows if not r["passing"]]

    # 跳过的源单独归类（#455）：不进覆盖、不进失败，按原因汇总，供夜间直接处理。
    skip_by_reason: dict[str, int] = {}
    for r in rows:
        for entry in r["skipped_sources"]:
            key = str(entry.get("reason") or SKIP_REASON_OTHER)
            skip_by_reason[key] = skip_by_reason.get(key, 0) + 1
    total_skipped = sum(r["sources_skipped"] for r in rows)

    result = {
        "schema_version": 2,
        "tool": "nightly_gap.py",
        "project": "AutoInfo",
        "dod": "21 域 × (真语料 + 真产物 + 可溯源 + 无占位)",
        "total_units": len(rows),
        "passing_units": len(passing),
        "gap_units": len(gap),
        "assertion_summary": assert_summary,
        "skip_summary": {
            "sources_skipped": total_skipped,
            "by_reason": {k: skip_by_reason[k] for k in sorted(skip_by_reason)},
        },
        "units": rows,
    }

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    verdict = (
        "- 判定：**差距归零（完成）**"
        if not gap
        else f"- 判定：**{len(gap)} / {len(rows)} 个域仍有差距**"
    )
    md = [
        "# AutoInfo 差距矩阵",
        "",
        verdict,
        f"- 断言：{assert_summary}",
        "",
        "| 域 | 语料 | 已跑源/总源 | 产物文件 | 断言失败 | 缺什么 |",
        "|:---|---:|:---|--:|--:|:---|",
    ]
    for r in rows:
        # 跳过数只在该域真的被跳过时出现（无 skip 的域逐字保持原样）
        cov = f"{r['sources_ran']}/{r['sources_total']}"
        if r["sources_skipped"]:
            cov += f"（含 {r['sources_skipped']} 策略跳过）"
        md.append(
            f"| {r['domain']} | {r['entries']} | {cov} | "
            f"{r['output_files']} | {r['assertion_failures']} | "
            f"{'、'.join(r['missing']) if r['missing'] else '✅ 达标'} |"
        )
    if total_skipped:
        md += ["", "## 策略跳过的源（不计覆盖，也不计源损坏，#455）", ""]
        for r in rows:
            for entry in r["skipped_sources"]:
                detail = entry.get("detail") or ""
                tail = f" —— {detail}" if detail else ""
                md.append(
                    f"- {r['domain']} / {entry['source']} — "
                    f"`{entry['reason']}`（跳过 {entry['runs_skipped']}/"
                    f"{entry['runs_total']} 次；历史产出 "
                    f"{entry['runs_productive']} 次）{tail}"
                )
    md_text = "\n".join(md) + "\n"
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(md_text, encoding="utf-8")

    print(md_text)
    return 0 if not gap else 1


if __name__ == "__main__":
    sys.exit(main())
