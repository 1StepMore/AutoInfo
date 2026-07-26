"""Internal cost metering — tracks LLM tokens, API calls, and storage.

Provides the :class:`CostMeter` class that logs usage events to a ``cost_log``
SQLite table and computes estimated costs using configurable rates from
``.autoinfo/config.yaml`` (section ``cost_rates``).

Typical usage::

    from autoinfo.cost import CostMeter

    meter = CostMeter()
    meter.log_llm_tokens(
        model="deepseek/deepseek-chat",
        input_tokens=500,
        output_tokens=200,
        domain="medical-research",
    )
    report = meter.get_report(domain="medical-research", period="all")
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoinfo.config import (
    Config,
    CostRatesConfig,
    get_config_path,
    load_config,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default DB path
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path("autoinfo.db")
"""Default path to the shared SQLite database."""


# ---------------------------------------------------------------------------
# CostMeter
# ---------------------------------------------------------------------------


class CostMeter:
    """Track and estimate costs for LLM tokens, API calls, and storage.

    All usage events are written to the ``cost_log`` table in the shared
    ``autoinfo.db`` SQLite database.

    Parameters
    ----------
    db_path : Path, optional
        Path to the SQLite database.  Defaults to ``autoinfo.db`` in CWD.
    config : Config, optional
        Application configuration with ``cost_rates``.  When omitted the
        meter loads the config from the default paths; if none is found
        the built-in default rates are used.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        config: Config | None = None,
    ) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._config = config or self._load_config()
        self._rates: CostRatesConfig = (
            self._config.cost_rates if self._config else CostRatesConfig.defaults()
        )
        self._init_db()

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config() -> Config | None:
        """Try loading config from default paths; return ``None`` on failure."""
        try:
            config_path = get_config_path()
            if config_path is not None:
                return load_config(config_path)
        except Exception:
            logger.debug("Could not load config for CostMeter — using default rates")
        return None

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        """Open a connection (with row factory for dict-like rows)."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        """Create the ``cost_log`` table if it does not exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cost_log (
                    log_id          TEXT PRIMARY KEY,
                    meter_type      TEXT NOT NULL,
                    meter_category  TEXT NOT NULL,
                    units           REAL NOT NULL DEFAULT 0,
                    estimated_cost  REAL NOT NULL DEFAULT 0,
                    domain          TEXT DEFAULT '',
                    user_id         TEXT DEFAULT '',
                    item_id         TEXT DEFAULT '',
                    model           TEXT DEFAULT '',
                    source_type     TEXT DEFAULT '',
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_cost_log_type
                    ON cost_log(meter_type);

                CREATE INDEX IF NOT EXISTS idx_cost_log_domain
                    ON cost_log(domain);

                CREATE INDEX IF NOT EXISTS idx_cost_log_created
                    ON cost_log(created_at);

                CREATE INDEX IF NOT EXISTS idx_cost_log_domain_type
                    ON cost_log(domain, meter_type);
            """)

    def _insert_log(
        self,
        meter_type: str,
        meter_category: str,
        units: float,
        estimated_cost: float,
        domain: str = "",
        user_id: str = "",
        item_id: str = "",
        model: str = "",
        source_type: str = "",
    ) -> str:
        """Insert a row into ``cost_log`` and return its ``log_id``."""
        log_id = f"cl-{uuid.uuid4().hex[:12]}"
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cost_log
                    (log_id, meter_type, meter_category, units, estimated_cost,
                     domain, user_id, item_id, model, source_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    meter_type,
                    meter_category,
                    units,
                    estimated_cost,
                    domain,
                    user_id,
                    item_id,
                    model,
                    source_type,
                    ts,
                ),
            )
        return log_id

    # ------------------------------------------------------------------
    # Logging methods
    # ------------------------------------------------------------------

    def log_llm_tokens(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        domain: str = "",
        item_id: str = "",
        user_id: str = "",
    ) -> dict[str, Any]:
        """Log an LLM token usage event and return cost + log_id.

        Parameters
        ----------
        model:
            Model identifier (e.g. ``"deepseek/deepseek-chat"``).
        input_tokens:
            Number of prompt (input) tokens.
        output_tokens:
            Number of completion (output) tokens.
        domain:
            Optional domain name for attribution.
        item_id:
            Optional item ID for attribution.
        user_id:
            Optional user ID for attribution.

        Returns
        -------
        dict
            Keys: ``log_id``, ``input_tokens``, ``output_tokens``,
            ``total_tokens``, ``estimated_cost``, ``rate_used``.
        """
        total_tokens = input_tokens + output_tokens
        rate = self._rates.llm.get(model)

        if rate is not None:
            input_cost = (input_tokens / 1000.0) * rate.input_per_1k
            output_cost = (output_tokens / 1000.0) * rate.output_per_1k
            estimated_cost = round(input_cost + output_cost, 8)
            rate_desc = {
                "input_per_1k": rate.input_per_1k,
                "output_per_1k": rate.output_per_1k,
            }
        else:
            # Fallback: use a generic default rate
            input_cost = (input_tokens / 1000.0) * 0.00015
            output_cost = (output_tokens / 1000.0) * 0.00060
            estimated_cost = round(input_cost + output_cost, 8)
            rate_desc = {"input_per_1k": 0.00015, "output_per_1k": 0.00060}

        # Use model string cleaned for category
        meter_category = model.split("/")[-1] if "/" in model else model

        log_id = self._insert_log(
            meter_type="llm_tokens",
            meter_category=meter_category,
            units=float(total_tokens),
            estimated_cost=estimated_cost,
            domain=domain,
            user_id=user_id,
            item_id=item_id,
            model=model,
        )

        return {
            "log_id": log_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": estimated_cost,
            "rate_used": rate_desc,
        }

    def log_api_call(
        self,
        *,
        source_type: str,
        domain: str = "",
        item_id: str = "",
        user_id: str = "",
    ) -> dict[str, Any]:
        """Log an API call event and return cost + log_id.

        Parameters
        ----------
        source_type:
            Source type (e.g. ``"pubmed"``, ``"rss"``, ``"web"``).
        domain:
            Optional domain name for attribution.
        item_id:
            Optional item ID for attribution.
        user_id:
            Optional user ID for attribution.

        Returns
        -------
        dict
            Keys: ``log_id``, ``estimated_cost``, ``rate_used``.
        """
        rate = self._rates.api_calls.get(source_type)
        if rate is not None:
            estimated_cost = rate.per_call
            rate_desc = {"per_call": rate.per_call}
        else:
            # Fallback: generic default
            estimated_cost = 0.005
            rate_desc = {"per_call": 0.005}

        log_id = self._insert_log(
            meter_type="api_call",
            meter_category=source_type,
            units=1.0,
            estimated_cost=round(estimated_cost, 8),
            domain=domain,
            user_id=user_id,
            item_id=item_id,
            source_type=source_type,
        )

        return {
            "log_id": log_id,
            "estimated_cost": round(estimated_cost, 8),
            "rate_used": rate_desc,
        }

    def log_storage(
        self,
        *,
        domain: str,
        item_count: int = 0,
        bytes_stored: int = 0,
        user_id: str = "",
    ) -> dict[str, Any]:
        """Log a storage usage event and return cost + log_id.

        Storage costs are computed from two dimensions:
        - Per-item cost (``cost_rates.storage.per_item``)
        - Per-MB cost (``cost_rates.storage.per_mb``)

        Parameters
        ----------
        domain:
            Domain name for attribution.
        item_count:
            Number of items stored.
        bytes_stored:
            Total bytes stored.
        user_id:
            Optional user ID for attribution.

        Returns
        -------
        dict
            Keys: ``log_id``, ``item_count``, ``mb_stored``,
            ``estimated_cost``, ``rate_used``.
        """
        rate = self._rates.storage
        mb_stored = bytes_stored / (1024.0 * 1024.0)
        item_cost = item_count * rate.per_item
        mb_cost = mb_stored * rate.per_mb
        estimated_cost = round(item_cost + mb_cost, 8)

        log_id = self._insert_log(
            meter_type="storage",
            meter_category="kb_storage",
            units=float(item_count),
            estimated_cost=estimated_cost,
            domain=domain,
            user_id=user_id,
        )

        return {
            "log_id": log_id,
            "item_count": item_count,
            "mb_stored": round(mb_stored, 4),
            "estimated_cost": estimated_cost,
            "rate_used": {
                "per_item": rate.per_item,
                "per_mb": rate.per_mb,
            },
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_report(
        self,
        domain: str = "",
        period: str = "all",
    ) -> dict[str, Any]:
        """Return aggregated cost report.

        Parameters
        ----------
        domain:
            Filter by domain.  When empty, report covers all domains.
        period:
            Time period filter: ``"all"``, ``"today"``, ``"week"``,
            ``"month"``.  Defaults to ``"all"``.

        Returns
        -------
        dict
            Keys: ``period``, ``domain``, ``total_cost``,
            ``by_type`` (dict of meter_type → cost),
            ``by_category`` (dict of meter_category → cost),
            ``llm_models`` (dict of model → tokens + cost),
            ``api_sources`` (dict of source_type → calls + cost),
            ``log_count``, ``domain_filter``.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if domain:
            clauses.append("domain = ?")
            params.append(domain)

        if period and period != "all":
            if period == "today":
                clauses.append("DATE(created_at) = DATE('now')")
            elif period == "week":
                clauses.append("created_at >= DATE('now', '-7 days')")
            elif period == "month":
                clauses.append("created_at >= DATE('now', '-30 days')")

        where = " WHERE " + " AND ".join(clauses) if clauses else ""

        def _with_extra(extra_clause: str) -> str:
            """Return WHERE clause extended with an extra condition."""
            if where:
                return f"{where} AND {extra_clause}"
            return f" WHERE {extra_clause}"

        with self._connect() as conn:
            # Total cost
            row = conn.execute(
                f"SELECT COALESCE(SUM(estimated_cost), 0) AS total_cost,"
                f"       COUNT(*) AS log_count"
                f"  FROM cost_log{where}",
                params,
            ).fetchone()
            total_cost = row["total_cost"] if row else 0.0
            log_count = row["log_count"] if row else 0

            # By meter_type
            by_type: dict[str, float] = {}
            rows = conn.execute(
                f"SELECT meter_type, COALESCE(SUM(estimated_cost), 0) AS cost"
                f"  FROM cost_log{where}"
                f" GROUP BY meter_type"
                f" ORDER BY cost DESC",
                params,
            ).fetchall()
            for r in rows:
                by_type[r["meter_type"]] = r["cost"]

            # By meter_category
            by_category: dict[str, float] = {}
            rows = conn.execute(
                f"SELECT meter_category, COALESCE(SUM(estimated_cost), 0) AS cost"
                f"  FROM cost_log{where}"
                f" GROUP BY meter_category"
                f" ORDER BY cost DESC",
                params,
            ).fetchall()
            for r in rows:
                by_category[r["meter_category"]] = r["cost"]

            # LLM models breakdown
            llm_models: dict[str, dict[str, Any]] = {}
            extra_llm = "meter_type = 'llm_tokens'"
            rows = conn.execute(
                f"SELECT model,"
                f"       SUM(units) AS total_tokens,"
                f"       COUNT(*) AS call_count,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost"
                f"  FROM cost_log{_with_extra(extra_llm)}"
                f" GROUP BY model"
                f" ORDER BY cost DESC",
                params,
            ).fetchall()
            for r in rows:
                if r["model"]:
                    llm_models[r["model"]] = {
                        "total_tokens": r["total_tokens"],
                        "call_count": r["call_count"],
                        "cost": r["cost"],
                    }

            # API sources breakdown
            api_sources: dict[str, dict[str, Any]] = {}
            extra_api = "meter_type = 'api_call'"
            rows = conn.execute(
                f"SELECT source_type,"
                f"       SUM(units) AS call_count,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost"
                f"  FROM cost_log{_with_extra(extra_api)}"
                f" GROUP BY source_type"
                f" ORDER BY cost DESC",
                params,
            ).fetchall()
            for r in rows:
                if r["source_type"]:
                    api_sources[r["source_type"]] = {
                        "call_count": r["call_count"],
                        "cost": r["cost"],
                    }

        return {
            "period": period,
            "domain": domain or "*",
            "total_cost": round(total_cost, 8),
            "by_type": by_type,
            "by_category": by_category,
            "llm_models": llm_models,
            "api_sources": api_sources,
            "log_count": log_count,
            "domain_filter": domain if domain else None,
        }

    def get_cost_allocation(
        self,
        domain: str = "",
        user_id: str = "",
        period: str = "all",
    ) -> dict[str, Any]:
        """Return cost allocation broken down by domain and user.

        When *domain* is provided the result includes a ``by_user`` breakdown
        for that domain.  When *user_id* is provided the result is filtered to
        that user across all domains (or within *domain* if also specified).

        Parameters
        ----------
        domain:
            Optional domain filter.
        user_id:
            Optional user ID filter.
        period:
            Time period: ``"all"``, ``"today"``, ``"week"``, ``"month"``.

        Returns
        -------
        dict
            Keys: ``period``, ``domain_filter``, ``user_id_filter``,
            ``total_cost``, ``log_count``, ``by_domain``, ``by_user``.
            Each breakdown entry includes ``cost``, ``pct_of_total``,
            and ``log_count``.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if domain:
            clauses.append("domain = ?")
            params.append(domain)

        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)

        if period and period != "all":
            if period == "today":
                clauses.append("DATE(created_at) = DATE('now')")
            elif period == "week":
                clauses.append("created_at >= DATE('now', '-7 days')")
            elif period == "month":
                clauses.append("created_at >= DATE('now', '-30 days')")

        where = " WHERE " + " AND ".join(clauses) if clauses else ""

        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COALESCE(SUM(estimated_cost), 0) AS total_cost,"
                f"       COUNT(*) AS log_count"
                f"  FROM cost_log{where}",
                params,
            ).fetchone()
            total_cost = row["total_cost"] if row else 0.0
            log_count = row["log_count"] if row else 0

            by_domain: list[dict[str, Any]] = []
            rows = conn.execute(
                f"SELECT domain,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost,"
                f"       COUNT(*) AS cnt"
                f"  FROM cost_log{where}"
                f" GROUP BY domain"
                f" ORDER BY cost DESC",
                params,
            ).fetchall()
            for r in rows:
                domain_name = r["domain"] or "(empty)"
                by_domain.append(
                    {
                        "domain": domain_name,
                        "cost": round(r["cost"], 8),
                        "pct_of_total": (
                            round(r["cost"] / total_cost * 100, 2)
                            if total_cost > 0
                            else 0.0
                        ),
                        "log_count": r["cnt"],
                    }
                )

            by_user: list[dict[str, Any]] = []
            user_clauses = list(clauses)
            user_params = list(params)
            user_where = f" WHERE {' AND '.join(user_clauses)}" if user_clauses else ""
            rows = conn.execute(
                f"SELECT domain, user_id,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost,"
                f"       COUNT(*) AS cnt"
                f"  FROM cost_log{user_where}"
                f" GROUP BY domain, user_id"
                f" ORDER BY cost DESC",
                user_params,
            ).fetchall()
            for r in rows:
                uid = r["user_id"] or "(anonymous)"
                by_user.append(
                    {
                        "domain": r["domain"] or "(empty)",
                        "user_id": uid,
                        "cost": round(r["cost"], 8),
                        "pct_of_total": (
                            round(r["cost"] / total_cost * 100, 2)
                            if total_cost > 0
                            else 0.0
                        ),
                        "log_count": r["cnt"],
                    }
                )

        return {
            "period": period,
            "domain_filter": domain if domain else None,
            "user_id_filter": user_id if user_id else None,
            "total_cost": round(total_cost, 8),
            "log_count": log_count,
            "by_domain": by_domain,
            "by_user": by_user,
        }

    def get_cost_dashboard(
        self,
        period: str = "week",
    ) -> dict[str, Any]:
        """Return a cost dashboard for the current period.

        The dashboard aggregates costs from ``cost_log`` and presents:
        - Total cost and log count for the period
        - Costs broken down by domain
        - Daily cost trend over the period
        - Top 5 most expensive LLM models
        - Top 5 most expensive API sources
        - Usage vs budget comparison (against configured budget alerts)

        Parameters
        ----------
        period:
            Time period: ``"today"``, ``"week"``, ``"month"``, ``"all"``.
            Defaults to ``"week"``.

        Returns
        -------
        dict
            Keys: ``period``, ``total_cost``, ``log_count``,
            ``by_domain``, ``daily_trend``, ``top_models``,
            ``top_sources``, ``budget_status``.
        """
        if period not in ("today", "week", "month", "all"):
            period = "week"

        # Build WHERE clause for period
        clauses: list[str] = []
        params: list[Any] = []
        if period and period != "all":
            if period == "today":
                clauses.append("DATE(created_at) = DATE('now')")
            elif period == "week":
                clauses.append("created_at >= DATE('now', '-7 days')")
            elif period == "month":
                clauses.append("created_at >= DATE('now', '-30 days')")

        where = " WHERE " + " AND ".join(clauses) if clauses else ""

        with self._connect() as conn:
            # -- Total cost & log count ------------------------------------
            row = conn.execute(
                f"SELECT COALESCE(SUM(estimated_cost), 0) AS total_cost,"
                f"       COUNT(*) AS log_count"
                f"  FROM cost_log{where}",
                params,
            ).fetchone()
            total_cost = row["total_cost"] if row else 0.0
            log_count = row["log_count"] if row else 0

            # -- Costs by domain -------------------------------------------
            by_domain: list[dict[str, Any]] = []
            rows = conn.execute(
                f"SELECT domain,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost,"
                f"       COUNT(*) AS cnt"
                f"  FROM cost_log{where}"
                f" GROUP BY domain"
                f" ORDER BY cost DESC",
                params,
            ).fetchall()
            for r in rows:
                domain_name = r["domain"] or "(empty)"
                by_domain.append({
                    "domain": domain_name,
                    "cost": round(r["cost"], 8),
                    "pct_of_total": (
                        round(r["cost"] / total_cost * 100, 2)
                        if total_cost > 0 else 0.0
                    ),
                    "log_count": r["cnt"],
                })

            # -- Daily cost trend ------------------------------------------
            daily_trend: list[dict[str, Any]] = []
            rows = conn.execute(
                f"SELECT DATE(created_at) AS day,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost,"
                f"       COUNT(*) AS log_count"
                f"  FROM cost_log{where}"
                f" GROUP BY DATE(created_at)"
                f" ORDER BY day ASC",
                params,
            ).fetchall()
            for r in rows:
                daily_trend.append({
                    "day": r["day"],
                    "cost": round(r["cost"], 8),
                    "log_count": r["log_count"],
                })

            # -- Top 5 LLM models by cost ----------------------------------
            top_models: list[dict[str, Any]] = []
            extra_llm = "meter_type = 'llm_tokens'"
            llm_where = f"{where} AND {extra_llm}" if where else f" WHERE {extra_llm}"
            rows = conn.execute(
                f"SELECT model,"
                f"       SUM(units) AS total_tokens,"
                f"       COUNT(*) AS call_count,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost"
                f"  FROM cost_log{llm_where}"
                f" GROUP BY model"
                f" ORDER BY cost DESC"
                f" LIMIT 5",
                params,
            ).fetchall()
            for r in rows:
                if r["model"]:
                    top_models.append({
                        "model": r["model"],
                        "total_tokens": r["total_tokens"],
                        "call_count": r["call_count"],
                        "cost": round(r["cost"], 8),
                    })

            # -- Top 5 API sources by cost ---------------------------------
            top_sources: list[dict[str, Any]] = []
            extra_api = "meter_type = 'api_call'"
            api_where = f"{where} AND {extra_api}" if where else f" WHERE {extra_api}"
            rows = conn.execute(
                f"SELECT source_type,"
                f"       SUM(units) AS call_count,"
                f"       COALESCE(SUM(estimated_cost), 0) AS cost"
                f"  FROM cost_log{api_where}"
                f" GROUP BY source_type"
                f" ORDER BY cost DESC"
                f" LIMIT 5",
                params,
            ).fetchall()
            for r in rows:
                if r["source_type"]:
                    top_sources.append({
                        "source_type": r["source_type"],
                        "call_count": r["call_count"],
                        "cost": round(r["cost"], 8),
                    })

            # -- Budget status: compare cost vs configured alerts ----------
            budget_status: list[dict[str, Any]] = []
            try:
                from autoinfo.alerts import get_budget_alerts

                # Collect unique domains from cost_log
                domain_rows = conn.execute(
                    f"SELECT DISTINCT domain FROM cost_log{where} WHERE domain != ''"
                ).fetchall()
                active_domains = [r["domain"] for r in domain_rows]

                for d in active_domains:
                    alerts = get_budget_alerts(domain=d)
                    for alert in alerts:
                        threshold = getattr(alert, "cost_threshold", None) or getattr(alert, "threshold", None)
                        if threshold is None:
                            continue
                        # Find cost for this domain
                        domain_cost = next(
                            (item["cost"] for item in by_domain if item["domain"] == d),
                            0.0,
                        )
                        pct = round(domain_cost / threshold * 100, 2) if threshold > 0 else 0.0
                        budget_status.append({
                            "domain": d,
                            "cost": domain_cost,
                            "budget": threshold,
                            "pct_used": pct,
                            "status": "breached" if pct >= 100 else "warning" if pct >= 80 else "ok",
                            "alert_period": getattr(alert, "cost_period", period),
                        })
            except Exception:
                # Budget alerts are optional — silently skip on error
                pass

        return {
            "period": period,
            "total_cost": round(total_cost, 8),
            "log_count": log_count,
            "by_domain": by_domain,
            "daily_trend": daily_trend,
            "top_models": top_models,
            "top_sources": top_sources,
            "budget_status": budget_status,
        }

    def clear_logs(self, domain: str = "") -> int:
        """Delete cost logs, optionally filtered by domain.

        Returns the number of deleted rows.
        """
        with self._connect() as conn:
            if domain:
                cur = conn.execute(
                    "DELETE FROM cost_log WHERE domain = ?", (domain,)
                )
            else:
                cur = conn.execute("DELETE FROM cost_log")
            return cur.rowcount
