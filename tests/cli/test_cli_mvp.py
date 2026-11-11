"""Tests for ``autoinfo mvp`` (Concierge MVP pilots, plan todo 13).

Covers the acceptance contract from
``.omo/plans/autoinfo-report-validation-concierge-wave.md`` todo 13:

- ``mvp init --user u1 --domain medical-research --product digest
  --frequency weekly`` provisions the full pilot in a temp project:
  EndUserProfile with ``profile.tier == "premium"`` + status ``active``
  (check_access premium fast path reads UserProfile.tier — billing.py:736),
  a matching premium subscription, the demo domain config imported, and
  ``mvp/u1/`` containing the product file, ``01-QA-GATES/gate-report-<product>``
  (md+json), ``SOURCES.md``, ``README-给试点用户.md``, provenance and
  user.json placeholder metadata.
- ``check_access(premium)`` returns ``allowed=True`` for the provisioned
  user — no Stripe, no trial status.
- ``mvp list`` shows the pilot table (user/domain/product/frequency/
  generated/generated_at/gate) plus subscription status and latest path.
- Idempotency: a second init does not duplicate profile/subscription/
  product files and exits 0 with clear messages.
- Hermetic: no LLM key, no network — the first product is generated via
  the KBStore+LLM injection seam (mirror of
  regression-no-placeholder-magazine-tutorial).

Run inside a temp project dir (monkeypatch.chdir) so neither the CLI nor
the user store touches the repo's runtime state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from autoinfo.billing import check_access
from autoinfo.cli import app as main_app
from autoinfo.user_store import (
    get_profile,
    list_subscriptions,
)
from tests._ansi import strip_ansi


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def temp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated temp project: cwd + user-store DB + no LLM key."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("autoinfo.user_store._DB_PATH", None)
    monkeypatch.setattr(
        "autoinfo.user_store._get_db_path",
        lambda: tmp_path / ".autoinfo" / "users.db",
    )
    monkeypatch.delenv("AUTOINFO_LLM_API_KEY", raising=False)
    _write_min_config(tmp_path)
    return tmp_path


def _write_min_config(root: Path) -> Path:
    """Create a minimal initialized project config under *root*."""
    config_dir = root / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(
            {
                "project": {"name": "Test Project", "created_at": "2026-07-01"},
                "llm": {
                    "provider": "openrouter",
                    "model": "deepseek/deepseek-chat",
                    "api_key": "${AUTOINFO_LLM_API_KEY}",
                },
                "domains": [],
            },
            fh,
            default_flow_style=False,
        )
    return config_path


def _init(runner: CliRunner, **overrides: str) -> Any:
    args = [
        "mvp",
        "init",
        "--user",
        overrides.get("user", "u1"),
        "--domain",
        overrides.get("domain", "medical-research"),
        "--product",
        overrides.get("product", "digest"),
        "--frequency",
        overrides.get("frequency", "weekly"),
    ]
    if "contact" in overrides:
        args.extend(["--contact", overrides["contact"]])
    return runner.invoke(main_app, args)


def _product_files(user_dir: Path) -> list[Path]:
    """The generated product files (not gate reports / readme / sources)."""
    return [
        p
        for p in user_dir.glob("*.md")
        if not p.name.startswith(("gate-report-", "README", "SOURCES"))
    ]


class TestMvpInitHappyPath:
    def test_init_creates_premium_profile_active(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, f"STDOUT/ERR: {result.output}"

        profile = get_profile("u1")
        assert profile is not None, "EndUserProfile u1 missing after mvp init"
        # CRITICAL mechanism: check_access premium fast path reads
        # profile.tier — mvp must provision tier="premium" directly.
        assert profile.tier == "premium"
        assert profile.status == "active", (
            "bare activate_trial sets status=trial which the Stripe fallback "
            "rejects; mvp must provision status=active"
        )

    def test_init_creates_premium_subscription(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        subs = list_subscriptions("u1")
        assert len(subs) == 1, "exactly one subscription expected on first init"
        sub = subs[0]
        assert sub.plan == "premium"
        assert sub.tier == "premium"
        assert sub.status == "active"

    def test_check_access_premium_allowed_without_stripe(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        access = check_access("u1", "premium")
        assert access["allowed"] is True, access
        assert access["upgrade_prompt"] is None

    def test_init_imports_demo_domain_config(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        with open(Path.cwd() / ".autoinfo" / "config.yaml", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        names = [d.get("name") for d in cfg.get("domains", [])]
        assert "medical-research" in names, names

    def test_init_writes_delivery_dir_with_product_and_gate_report(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        user_dir = Path.cwd() / "mvp" / "u1"
        assert user_dir.is_dir(), f"missing {user_dir}"

        products = _product_files(user_dir)
        assert len(products) == 1, [p.name for p in products]
        body = products[0].read_text(encoding="utf-8")
        assert body.strip(), "product file is empty"

        gate_dir = user_dir / "01-QA-GATES"
        assert (gate_dir / "gate-report-digest.md").is_file(), list(gate_dir.iterdir())
        gate_json = gate_dir / "gate-report-digest.json"
        assert gate_json.is_file(), list(gate_dir.iterdir())
        payload = json.loads(gate_json.read_text(encoding="utf-8"))
        assert payload["delivered"] is True
        assert payload["quality"] == "PASS", payload
        assert [g["gate"] for g in payload["gates"]] == [
            "D1",
            "D2",
            "D3",
            "authenticity",
        ]

        assert (user_dir / "SOURCES.md").is_file(), "SOURCES.md missing"
        assert (user_dir / "README-给试点用户.md").is_file(), "pilot README missing"
        assert (user_dir / "provenance.json").is_file(), "provenance missing"
        prov = json.loads((user_dir / "provenance.json").read_text(encoding="utf-8"))
        # Source provenance: every entry carries source_url/type/platform.
        entries = prov.get("entries", [])
        assert entries, "provenance carries no source entries"
        for e in entries:
            assert e.get("source_url"), e
            assert e.get("source_type"), e
            assert e.get("source_platform"), e
        # Honesty: the hermetic seam is disclosed, never hidden.
        assert "hermetic" in json.dumps(prov).lower()

        assert (user_dir / "user.json").is_file(), "user.json missing"

    def test_list_shows_pilot_user_and_status(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        listing = runner.invoke(main_app, ["mvp", "list"])
        assert listing.exit_code == 0, listing.output
        assert "u1" in listing.output
        assert "premium" in listing.output
        assert "active" in listing.output
        # latest product path is shown
        assert "mvp/u1/" in listing.output


class TestMvpInitIdempotency:
    def test_second_init_no_duplicates(self, runner: CliRunner) -> None:
        first = _init(runner)
        assert first.exit_code == 0, first.output

        user_dir = Path.cwd() / "mvp" / "u1"
        products_before = _product_files(user_dir)
        subs_before = list_subscriptions("u1")

        second = _init(runner)
        assert second.exit_code == 0, second.output
        assert "Traceback" not in second.output

        assert get_profile("u1") is not None
        assert len(list_subscriptions("u1")) == len(subs_before) == 1
        assert len(_product_files(user_dir)) == len(products_before) == 1
        # Clear no-op message rather than silent success.
        assert "already" in second.output.lower()

    def test_list_without_pilots_clean_message(self, runner: CliRunner) -> None:
        listing = runner.invoke(main_app, ["mvp", "list"])
        assert listing.exit_code == 0, listing.output
        assert "No MVP pilot users" in listing.output


class TestMvpInitHermeticAndValidation:
    def test_init_succeeds_without_llm_key(self, runner: CliRunner) -> None:
        # autouse fixture already deleted AUTOINFO_LLM_API_KEY; assert the
        # full chain (product generation included) still exits 0.
        result = _init(runner)
        assert result.exit_code == 0, result.output
        user_dir = Path.cwd() / "mvp" / "u1"
        assert _product_files(user_dir), "no product generated without LLM key"

    def test_unknown_product_rejected(self, runner: CliRunner) -> None:
        result = _init(runner, product="podcast")
        assert result.exit_code == 1
        assert "Traceback" not in result.output

    def test_unknown_frequency_rejected(self, runner: CliRunner) -> None:
        result = _init(runner, frequency="hourly")
        assert result.exit_code == 1
        assert "Traceback" not in result.output

    def test_unknown_domain_fails_cleanly(self, runner: CliRunner) -> None:
        result = _init(runner, domain="not-a-demo-domain")
        assert result.exit_code == 1
        assert "Traceback" not in result.output


class TestMvpGroupIdentity:
    def test_mvp_in_top_level_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main_app, ["--help"])
        assert result.exit_code == 0
        assert "mvp" in strip_ansi(result.output)


class TestMvpPilotPackage:
    """The delivery package a pilot can actually read and verify (#740)."""

    def test_sources_md_maps_every_provenance_entry(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        user_dir = Path.cwd() / "mvp" / "u1"
        prov = json.loads((user_dir / "provenance.json").read_text(encoding="utf-8"))
        sources = (user_dir / "SOURCES.md").read_text(encoding="utf-8")
        assert "hermetic" in sources.lower()
        for entry in prov["entries"]:
            assert entry["source_url"] in sources, entry

    def test_readme_is_three_sentences_with_contact_placeholder(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        readme = (Path.cwd() / "mvp" / "u1" / "README-给试点用户.md").read_text(encoding="utf-8")
        assert readme.count("。") == 3, readme
        assert "（待填写）" in readme

    def test_contact_is_persisted_and_surfaced(self, runner: CliRunner) -> None:
        result = _init(runner, contact="pilot@example.com")
        assert result.exit_code == 0, result.output

        user_dir = Path.cwd() / "mvp" / "u1"
        meta = json.loads((user_dir / "user.json").read_text(encoding="utf-8"))
        assert meta["contact"] == "pilot@example.com"
        assert "pilot@example.com" in (user_dir / "README-给试点用户.md").read_text(
            encoding="utf-8"
        )
        assert "pilot@example.com" in (user_dir / "SOURCES.md").read_text(encoding="utf-8")

    def test_list_table_has_required_fields(self, runner: CliRunner) -> None:
        result = _init(runner)
        assert result.exit_code == 0, result.output

        listing = runner.invoke(main_app, ["mvp", "list"])
        assert listing.exit_code == 0, listing.output
        for token in (
            "USER",
            "DOMAIN",
            "PRODUCT",
            "FREQUENCY",
            "GENERATED",
            "GENERATED_AT",
            "GATE",
        ):
            assert token in listing.output, token
        assert "medical-research" in listing.output
        assert "PASS" in listing.output

    def test_pilot_is_domain_agnostic(self, runner: CliRunner) -> None:
        result = _init(runner, domain="ai-commercial")
        assert result.exit_code == 0, result.output

        user_dir = Path.cwd() / "mvp" / "u1"
        product = _product_files(user_dir)[0].read_text(encoding="utf-8")
        assert "ai-commercial" in product
        assert "ai-commercial" in (user_dir / "SOURCES.md").read_text(encoding="utf-8")
        prov = json.loads((user_dir / "provenance.json").read_text(encoding="utf-8"))
        assert len({e["source_url"] for e in prov["entries"]}) == 3

    def test_short_circuited_gate_report_leaves_package_incomplete(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reverse proof: if gate-report writing is skipped, the DoD package
        assertion fails because ``01-QA-GATES/gate-report-digest.*`` is absent.
        """

        def _fake_write_gate_report(
            out_dir: Path,
            product_file: Path,
            *,
            kind: str = "PROCESSED",
            bucket: str = "PROCESSED",
            key: str | None = None,
        ) -> dict[str, Any]:
            report_key = key or "digest"
            return {
                "quality": "PASS",
                "delivered": True,
                "gates": [],
                "key": report_key,
                "md": out_dir / f"gate-report-{report_key}.md",
                "json": out_dir / f"gate-report-{report_key}.json",
            }

        monkeypatch.setattr(
            "autoinfo.delivery.gate_report.write_gate_report",
            _fake_write_gate_report,
        )
        result = _init(runner)
        assert result.exit_code == 0, result.output

        user_dir = Path.cwd() / "mvp" / "u1"
        assert _product_files(user_dir), "product still generated"
        assert not (user_dir / "01-QA-GATES" / "gate-report-digest.md").is_file()
        assert not (user_dir / "01-QA-GATES" / "gate-report-digest.json").is_file()

    def test_mvp_output_is_gitignored(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        ignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
        assert "mvp/" in ignore.splitlines()
