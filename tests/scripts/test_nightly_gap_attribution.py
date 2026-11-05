"""nightly_gap 归因能力回归（goal doc 2026-11-06 #3）。

- ``assertions_by_domain`` 返回带 file/assertion/severity/details 的失败明细
  （此前明细 JSON 写进 TemporaryDirectory 随函数退出删除，只剩每域一个计数）。
- ``kb_failures_ledger`` 消费 G0/G4 的 ``_failed/*.json`` 与 CurationGate 的
  ``knowledge/_failed/<domain>/*.md`` —— 这两类条目级记录此前从未被任何汇总
  视图消费。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import nightly_gap  # noqa: E402  (sys.path insert above)


class TestAssertionsDetailRetained:
    def test_failures_carry_file_assertion_details(self, tmp_path, monkeypatch):
        def fake_run(cmd, timeout=0):
            jp = Path(cmd[cmd.index("--json-out") + 1])
            jp.parent.mkdir(parents=True, exist_ok=True)
            jp.write_text(
                json.dumps(
                    {
                        "assertions": [{"name": "a"}, {"name": "b"}],
                        "files_scanned": 7,
                        "totals": {"failures": 2},
                        "failures": [
                            {
                                "file": "outputs/d1/report.md",
                                "assertion": "no_placeholder",
                                "severity": "P0",
                                "details": "found `TODO` at line 4",
                            },
                            {
                                "file": "outputs/d2/digest.md",
                                "assertion": "traceable",
                                "severity": "P1",
                                "details": "no source link",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return 0, "", ""

        monkeypatch.setattr(nightly_gap, "_run", fake_run)
        per, failures, summary = nightly_gap.assertions_by_domain("python", tmp_path)

        assert per == {"d1": 1, "d2": 1}
        assert failures[0]["domain"] == "d1"
        assert failures[0]["file"] == "outputs/d1/report.md"
        assert failures[0]["assertion"] == "no_placeholder"
        assert failures[0]["severity"] == "P0"
        assert "TODO" in failures[0]["details"]
        assert "失败合计 2" in summary

    def test_scanner_without_json_returns_empty_detail(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nightly_gap, "_run", lambda cmd, timeout=0: (1, "", "boom"))
        per, failures, summary = nightly_gap.assertions_by_domain("python", tmp_path)

        assert per == {}
        assert failures == []
        assert "未产出 JSON" in summary


class TestKbFailuresLedger:
    def test_collections_and_knowledge_records_are_consumed(self, tmp_path):
        failed_dir = tmp_path / "collections" / "d1" / "_failed"
        failed_dir.mkdir(parents=True)
        (failed_dir / "item-1.json").write_text(
            json.dumps(
                {
                    "item_id": "item-1",
                    "gate": "G0",
                    "gate_result": {
                        "passed": False,
                        "score": 0.0,
                        "details": {
                            "failed_fields": [
                                {"field": "source_url", "reason": "missing", "value": ""}
                            ]
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        kb_failed = tmp_path / "knowledge" / "_failed" / "d2"
        kb_failed.mkdir(parents=True)
        (kb_failed / "entry-9.md").write_text(
            "---\nentry_id: entry-9\ndomain: d2\ngate: CurationGate\n"
            'reasons: "promote rejected: stale"\ndraft_path: x\n---\nbody\n',
            encoding="utf-8",
        )

        ledger = nightly_gap.kb_failures_ledger(tmp_path)

        assert ledger["total"] == 2
        assert ledger["by_domain"] == {"d1": 1, "d2": 1}
        g0 = next(i for i in ledger["items"] if i["source"] == "collections")
        assert g0["id"] == "item-1"
        assert g0["gate"] == "G0"
        assert "source_url" in g0["reason"]
        cg = next(i for i in ledger["items"] if i["source"] == "knowledge")
        assert cg["id"] == "entry-9"
        assert "stale" in cg["reason"]

    def test_corrupt_record_does_not_crash_the_ledger(self, tmp_path):
        failed_dir = tmp_path / "collections" / "d1" / "_failed"
        failed_dir.mkdir(parents=True)
        (failed_dir / "broken.json").write_text("{not json", encoding="utf-8")

        ledger = nightly_gap.kb_failures_ledger(tmp_path)

        assert ledger["total"] == 1
        assert ledger["items"][0]["id"] == "broken"

    def test_empty_repo_yields_empty_ledger(self, tmp_path):
        assert nightly_gap.kb_failures_ledger(tmp_path) == {
            "total": 0,
            "by_domain": {},
            "items": [],
        }
