#!/usr/bin/env python3
"""Build and read a small integrity index for collected BTC 5M markets.

The collector files are append-only and some of them are large. This module
streams them once into a compact derived index so the WebUI can show market
quality without rescanning raw data on every request.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

CN = timezone(timedelta(hours=8))
VALID_OPEN_QUALITIES = {"platform", "exact", "good", "close"}
BTC_MIN_PRICE = 1_000.0


def project_base() -> Path:
    if os.name == "nt":
        return Path.home() / "Desktop" / "\u81ea\u52a8\u4ea4\u6613"
    candidate = Path("/mnt/c/Users/yyq/Desktop/\u81ea\u52a8\u4ea4\u6613")
    if candidate.exists():
        return candidate
    return Path.cwd().resolve().parent


BASE = project_base()
DATA_DIR = BASE / "btc5m\u6570\u636e"
TRUE_DIR = DATA_DIR / "true_market"
DERIVED_DIR = DATA_DIR / "derived"
INDEX_PATH = DERIVED_DIR / "market_integrity.jsonl"
SUMMARY_PATH = DERIVED_DIR / "market_integrity_summary.json"


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if v != v:
        return None
    return v


def valid_btc_price(value: Any) -> Optional[float]:
    v = num(value)
    if v is None or v < BTC_MIN_PRICE:
        return None
    return v


def parse_ts(value: Any) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def row_ts(row: Dict[str, Any]) -> float:
    for key in ("server_ts", "received_at", "time"):
        ts = parse_ts(row.get(key))
        if ts:
            return ts
    for key in ("rtds_timestamp_ms", "timestamp_ms", "actual_entry_ts", "entry_time"):
        v = num(row.get(key))
        if v:
            return v / 1000 if v > 1_000_000_000_000 else v
    return 0.0


def merge_window(current: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(current)
    sources = set(merged.get("_sources", []))
    source = row.get("source")
    if source:
        sources.add(str(source))
    merged["_sources"] = sorted(sources)
    merged["_row_count"] = int(merged.get("_row_count") or 0) + 1
    for key, value in row.items():
        if value is None or value == "":
            continue
        merged[key] = value
    return merged


def load_windows() -> Dict[str, Dict[str, Any]]:
    rows_by_slug: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl(TRUE_DIR / "windows.jsonl") or []:
        slug = row.get("slug")
        start = row.get("window_start_ts")
        if not slug or not start:
            continue
        rows_by_slug[str(slug)] = merge_window(rows_by_slug.get(str(slug), {}), row)
    return rows_by_slug


def load_trade_stats() -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0,
            "confirmed": 0,
            "skipped": 0,
            "won": 0,
            "lost": 0,
            "amount": 0.0,
            "pnl": 0.0,
            "final_price": None,
            "final_source": "",
            "open_price": None,
            "probability_sources": Counter(),
            "last_trade_time": "",
        }
    )
    files = [DATA_DIR / "trades.jsonl", DATA_DIR / "sim" / "trades.jsonl", DATA_DIR / "live" / "trades.jsonl"]
    for path in files:
        for row in iter_jsonl(path) or []:
            slug = row.get("slug") or row.get("market_slug")
            if not slug:
                continue
            s = stats[str(slug)]
            s["rows"] += 1
            status = str(row.get("status") or "").lower()
            settlement = str(row.get("settlement_status") or "").lower()
            if settlement == "confirmed":
                s["confirmed"] += 1
            if status == "skipped" or settlement == "skipped":
                s["skipped"] += 1
            if status == "won" or row.get("won") is True:
                s["won"] += 1
            if status == "lost" or (status and row.get("won") is False):
                s["lost"] += 1
            s["amount"] += num(row.get("amount", row.get("buy_amount"))) or 0.0
            s["pnl"] += num(row.get("pnl", row.get("net_profit"))) or 0.0
            source = str(row.get("probability_source") or "")
            if source:
                s["probability_sources"][source] += 1
            open_price = valid_btc_price(row.get("platform_open_price")) or valid_btc_price(row.get("open_price"))
            if open_price is not None:
                s["open_price"] = open_price
            final_price = valid_btc_price(row.get("platform_close_price")) or valid_btc_price(row.get("btc_final"))
            if final_price is not None:
                s["final_price"] = final_price
                s["final_source"] = row.get("settle_source") or "trade_record"
            if row.get("time"):
                s["last_trade_time"] = row.get("time")

    for item in stats.values():
        item["probability_sources"] = dict(item["probability_sources"])
        item["amount"] = round(float(item["amount"]), 6)
        item["pnl"] = round(float(item["pnl"]), 6)
    return stats


def load_tick_stats(windows: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "orderbook_ticks": 0,
            "orderbook_last120": 0,
            "orderbook_last25": 0,
            "orderbook_sides": set(),
            "first_orderbook_ts": None,
            "last_orderbook_ts": None,
            "price_ticks": 0,
            "first_price_ts": None,
            "last_price_ts": None,
        }
    )

    for row in iter_jsonl(TRUE_DIR / "orderbook_ticks.jsonl") or []:
        slug = row.get("slug")
        if not slug:
            continue
        slug = str(slug)
        s = stats[slug]
        ts = row_ts(row)
        s["orderbook_ticks"] += 1
        if ts:
            if s["first_orderbook_ts"] is None or ts < s["first_orderbook_ts"]:
                s["first_orderbook_ts"] = ts
            if s["last_orderbook_ts"] is None or ts > s["last_orderbook_ts"]:
                s["last_orderbook_ts"] = ts
            end_ts = int((windows.get(slug) or {}).get("window_end_ts") or 0)
            if end_ts:
                remaining = end_ts - ts
                if 0 <= remaining <= 120:
                    s["orderbook_last120"] += 1
                if 0 <= remaining <= 25:
                    s["orderbook_last25"] += 1
        side = str(row.get("side") or "").lower()
        if side in {"up", "down"}:
            s["orderbook_sides"].add(side)
        if isinstance(row.get("up"), dict):
            s["orderbook_sides"].add("up")
        if isinstance(row.get("down"), dict):
            s["orderbook_sides"].add("down")

    for row in iter_jsonl(TRUE_DIR / "price_ticks.jsonl") or []:
        slug = row.get("slug")
        if not slug:
            continue
        slug = str(slug)
        s = stats[slug]
        ts = row_ts(row)
        s["price_ticks"] += 1
        if ts:
            if s["first_price_ts"] is None or ts < s["first_price_ts"]:
                s["first_price_ts"] = ts
            if s["last_price_ts"] is None or ts > s["last_price_ts"]:
                s["last_price_ts"] = ts

    for item in stats.values():
        item["orderbook_sides"] = sorted(item["orderbook_sides"])
        for key in ("first_orderbook_ts", "last_orderbook_ts", "first_price_ts", "last_price_ts"):
            if item[key] is not None:
                item[key] = int(item[key])
    return stats


def choose_open(window: Dict[str, Any], trade: Optional[Dict[str, Any]]) -> Tuple[Optional[float], str]:
    platform = valid_btc_price(window.get("platform_ptb"))
    if platform is not None:
        return platform, "platform_validation"
    quality = str(window.get("ptb_quality") or "").lower()
    ptb = valid_btc_price(window.get("ptb"))
    if ptb is not None and quality in VALID_OPEN_QUALITIES:
        return ptb, f"collector_{quality}"
    if trade:
        trade_open = valid_btc_price(trade.get("open_price"))
        if trade_open is not None:
            return trade_open, "trade_record"
    return None, ""


def build_rows() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    windows = load_windows()
    trade_stats = load_trade_stats()
    tick_stats = load_tick_stats(windows)
    now_ts = int(time.time())

    actual_starts = [int(w.get("window_start_ts") or 0) for w in windows.values() if w.get("window_start_ts")]
    if not actual_starts:
        return [], {
            "generated_at": datetime.now(CN).isoformat(),
            "total_expected": 0,
            "total_actual": 0,
            "complete": 0,
            "partial": 0,
            "missing": 0,
            "abnormal": 0,
            "unsettled": 0,
        }

    first_ts = min(actual_starts)
    current_start = (now_ts // 300) * 300
    latest_ts = max(max(actual_starts), current_start)
    expected_starts = list(range(first_ts, latest_ts + 1, 300))
    by_start = {int(w.get("window_start_ts") or 0): w for w in windows.values() if w.get("window_start_ts")}

    rows: List[Dict[str, Any]] = []
    counts = Counter()
    reason_counts = Counter()
    today_start = int(datetime.now(CN).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    today_counts = Counter()

    for start in expected_starts:
        end = start + 300
        slug = f"btc-updown-5m-{start}"
        window = by_start.get(start)
        reasons: List[str] = []
        status = "partial"
        trade = trade_stats.get(slug)
        ticks = tick_stats.get(slug, {})

        if not window:
            status = "missing"
            reasons.append("collector_window_missing")
            row = {
                "slug": slug,
                "window_start_ts": start,
                "window_end_ts": end,
                "market_time": market_time_label(start, end),
                "status": status,
                "usable_for_backtest": False,
                "reasons": reasons,
            }
            rows.append(row)
            counts[status] += 1
            if start >= today_start:
                today_counts[status] += 1
            reason_counts.update(reasons)
            continue

        open_price, open_source = choose_open(window, trade)
        final_price = valid_btc_price((trade or {}).get("final_price"))
        final_source = (trade or {}).get("final_source", "")
        exclude = bool(window.get("exclude_from_backtest"))
        ptb_quality = str(window.get("ptb_quality") or "")
        has_both_sides = set(ticks.get("orderbook_sides") or []) >= {"up", "down"}
        orderbook_ticks = int(ticks.get("orderbook_ticks") or 0)
        orderbook_last120 = int(ticks.get("orderbook_last120") or 0)
        price_ticks = int(ticks.get("price_ticks") or 0)
        token_ready = bool(window.get("token_up") and window.get("token_down"))
        unsettled = end > now_ts - 120

        if unsettled:
            reasons.append("market_not_old_enough_to_settle")
        if open_price is None:
            reasons.append("reliable_open_missing")
        if final_price is None:
            reasons.append("platform_final_missing")
        if orderbook_ticks <= 0:
            reasons.append("orderbook_missing")
        if orderbook_last120 <= 0:
            reasons.append("entry_window_orderbook_missing")
        if not has_both_sides:
            reasons.append("orderbook_side_incomplete")
        if not token_ready:
            reasons.append("token_ids_missing")
        if exclude:
            reasons.append("collector_marked_excluded")
        if ptb_quality.lower() in {"bad", "pending"}:
            reasons.append(f"ptb_quality_{ptb_quality.lower()}")

        usable = (
            not unsettled
            and not exclude
            and open_price is not None
            and final_price is not None
            and orderbook_last120 > 0
            and has_both_sides
            and token_ready
        )
        if usable:
            status = "complete"
        elif unsettled:
            status = "unsettled"
        elif exclude or open_price is None:
            status = "abnormal"
        else:
            status = "partial"

        final_gap = round(final_price - open_price, 4) if final_price is not None and open_price is not None else None
        row = {
            "slug": slug,
            "window_start_ts": start,
            "window_end_ts": end,
            "market_time": market_time_label(start, end),
            "status": status,
            "usable_for_backtest": usable,
            "reasons": sorted(set(reasons)),
            "open_price": round(open_price, 4) if open_price is not None else None,
            "open_source": open_source,
            "final_price": round(final_price, 4) if final_price is not None else None,
            "final_source": final_source,
            "final_gap": final_gap,
            "winner": "Up" if final_gap is not None and final_gap >= 0 else "Down" if final_gap is not None else "",
            "ptb_quality": ptb_quality,
            "exclude_from_backtest": exclude,
            "token_ready": token_ready,
            "orderbook_ticks": orderbook_ticks,
            "orderbook_last120": orderbook_last120,
            "orderbook_last25": int(ticks.get("orderbook_last25") or 0),
            "orderbook_sides": ticks.get("orderbook_sides") or [],
            "price_ticks": price_ticks,
            "trade_rows": int((trade or {}).get("rows") or 0),
            "confirmed_trades": int((trade or {}).get("confirmed") or 0),
            "trade_amount": (trade or {}).get("amount", 0.0),
            "trade_pnl": (trade or {}).get("pnl", 0.0),
            "probability_sources": (trade or {}).get("probability_sources", {}),
            "sources": window.get("_sources", []),
            "window_row_count": int(window.get("_row_count") or 1),
        }
        rows.append(row)
        counts[status] += 1
        if start >= today_start:
            today_counts[status] += 1
        reason_counts.update(row["reasons"])

    complete_rows = [r for r in rows if r.get("status") == "complete"]
    summary = {
        "generated_at": datetime.now(CN).isoformat(),
        "first_window_ts": first_ts,
        "latest_window_ts": latest_ts,
        "total_expected": len(expected_starts),
        "total_actual": len(windows),
        "total_missing": counts["missing"],
        "complete": counts["complete"],
        "partial": counts["partial"],
        "abnormal": counts["abnormal"],
        "unsettled": counts["unsettled"],
        "usable_for_backtest": len(complete_rows),
        "today_expected": len([x for x in expected_starts if x >= today_start]),
        "today_actual": len([x for x in actual_starts if x >= today_start]),
        "today_missing": today_counts["missing"],
        "today_complete": today_counts["complete"],
        "today_partial": today_counts["partial"],
        "today_abnormal": today_counts["abnormal"],
        "today_unsettled": today_counts["unsettled"],
        "reason_counts": dict(reason_counts.most_common()),
        "complete_time_range": {
            "first": market_time_label(complete_rows[0]["window_start_ts"], complete_rows[0]["window_end_ts"]) if complete_rows else "",
            "last": market_time_label(complete_rows[-1]["window_start_ts"], complete_rows[-1]["window_end_ts"]) if complete_rows else "",
        },
    }
    return rows, summary


def market_time_label(start_ts: int, end_ts: int) -> str:
    try:
        start = datetime.fromtimestamp(int(start_ts), CN)
        end = datetime.fromtimestamp(int(end_ts), CN)
        return f"{start.strftime('%m-%d %H:%M')}-{end.strftime('%H:%M')}"
    except Exception:
        return ""


def write_index(rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def generate() -> Dict[str, Any]:
    rows, summary = build_rows()
    write_index(rows, summary)
    return summary


def read_summary() -> Dict[str, Any]:
    if not SUMMARY_PATH.exists():
        return {}
    try:
        return json.loads(SUMMARY_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def read_rows(limit: int = 100, status: str = "", page: int = 1) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    if not INDEX_PATH.exists():
        return {"rows": [], "total": 0, "page": page, "pages": 1, "per_page": limit}
    status = status.strip().lower()
    all_rows = []
    for row in iter_jsonl(INDEX_PATH) or []:
        if status and row.get("status") != status:
            continue
        all_rows.append(row)
    all_rows.sort(key=lambda r: int(r.get("window_start_ts") or 0), reverse=True)
    total = len(all_rows)
    page = max(1, page)
    limit = min(500, max(1, limit))
    pages = max(1, (total + limit - 1) // limit)
    if page > pages:
        page = pages
    start = (page - 1) * limit
    rows = all_rows[start:start + limit]
    return {"rows": rows, "total": total, "page": page, "pages": pages, "per_page": limit}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BTC 5M market integrity index")
    parser.add_argument("--summary-only", action="store_true", help="print existing summary without rebuilding")
    args = parser.parse_args()
    if args.summary_only:
        print(json.dumps(read_summary(), ensure_ascii=False, indent=2))
        return 0
    summary = generate()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
