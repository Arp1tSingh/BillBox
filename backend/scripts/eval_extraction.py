"""Run the extraction provider over local bills and compute Gate 1 metrics.

Usage:
    python scripts/eval_extraction.py --bills ../evals/bills \
        --truth ../evals/truth.csv --out ../evals/results.csv

Real bills live under `evals/`, which is gitignored. This script never uploads
anything to Supabase; it only calls the configured provider.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.domain import ExtractionResult  # noqa: E402
from app.services.extraction import (  # noqa: E402
    ExtractionError,
    build_extraction_provider,
)

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}
TRUTH_COLUMNS = {"filename", "bill_type", "merchant", "amount", "bill_date"}


@dataclass
class Truth:
    bill_type: str
    merchant: str
    amount: Decimal | None
    bill_date: str


def load_truth(path: Path | None) -> dict[str, Truth]:
    if path is None or not path.is_file():
        return {}
    truth: dict[str, Truth] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = TRUTH_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"truth CSV is missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            amount: Decimal | None = None
            if row["amount"].strip():
                try:
                    amount = Decimal(row["amount"].strip()).quantize(Decimal("0.01"))
                except InvalidOperation:
                    amount = None
            truth[row["filename"]] = Truth(
                bill_type=row["bill_type"].strip(),
                merchant=row["merchant"].strip(),
                amount=amount,
                bill_date=row["bill_date"].strip(),
            )
    return truth


def truth_csv_value(value: object) -> str:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if value is None:
        return ""
    return str(value)


async def evaluate(args: argparse.Namespace) -> int:
    bills_dir = args.bills.resolve()
    if not bills_dir.is_dir():
        raise SystemExit(f"bills directory not found: {bills_dir}")

    files = sorted(
        path for path in bills_dir.rglob("*") if path.suffix.lower() in SUPPORTED
    )
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit(f"no supported bills found in {bills_dir}")

    provider = build_extraction_provider(get_settings())
    truth = load_truth(args.truth)
    rows: list[dict[str, object]] = []
    latencies: list[float] = []

    for path in files:
        mime = MIME[path.suffix.lower()]
        started = time.perf_counter()
        result: ExtractionResult | None = None
        error = ""
        try:
            result = await provider.extract([(path.read_bytes(), mime)])
        except ExtractionError as exc:
            error = exc.user_message
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)

        expected = truth.get(path.name)
        amount_ok = bool(
            expected
            and expected.amount is not None
            and result
            and result.amount is not None
            and expected.amount == result.amount
        )
        date_ok = bool(
            expected
            and expected.bill_date
            and result
            and result.bill_date is not None
            and expected.bill_date == result.bill_date.isoformat()
        )
        type_ok = bool(
            expected
            and result
            and (result.bill_type or "") == (expected.bill_type or "")
        )
        merchant_ok = bool(
            expected
            and result
            and expected.merchant.casefold() in (result.merchant or "").casefold()
        )
        raw_ok = bool(result and result.raw_text and result.raw_text.strip())

        rows.append(
            {
                "filename": path.name,
                "latency_s": f"{elapsed:.2f}",
                "bill_type": result.bill_type if result else "",
                "merchant": result.merchant if result else "",
                "amount": truth_csv_value(result.amount if result else None),
                "bill_date": (
                    result.bill_date.isoformat() if result and result.bill_date else ""
                ),
                "language": result.language if result else "",
                "tags": "|".join(result.tags) if result else "",
                "error": error,
                "expected_bill_type": expected.bill_type if expected else "",
                "expected_amount": truth_csv_value(expected.amount) if expected else "",
                "expected_bill_date": expected.bill_date if expected else "",
                "amount_ok": int(amount_ok),
                "date_ok": int(date_ok),
                "bill_type_ok": int(type_ok),
                "merchant_ok": int(merchant_ok),
                "raw_text_ok": int(raw_ok),
            }
        )
        print(f"{path.name}: {elapsed:.1f}s {error or 'ok'}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {args.out}")

    scored = [row for row in rows if row["expected_bill_type"] or row["expected_amount"]]
    if scored:
        def rate(key: str) -> float:
            return sum(int(row[key]) for row in scored) / len(scored) * 100

        print("\nGate 1 (scored rows only):")
        print(f"  amount correct:    {rate('amount_ok'):.0f}% (target 80%)")
        print(f"  bill_date correct: {rate('date_ok'):.0f}% (target 80%)")
        print(f"  bill_type correct: {rate('bill_type_ok'):.0f}% (target 70%)")
        print(f"  merchant correct:  {rate('merchant_ok'):.0f}%")
        print(f"  raw_text present:  {rate('raw_text_ok'):.0f}% (target 90%)")
    else:
        print("\nNo truth CSV rows matched; metrics are latency only.")

    if latencies:
        ordered = sorted(latencies)
        p95_index = max(0, int(round(len(ordered) * 0.95)) - 1)
        print("\nLatency:")
        print(f"  median: {statistics.median(latencies):.1f}s (target <15s)")
        print(f"  p95:    {ordered[p95_index]:.1f}s (target <30s)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bills", type=Path, required=True, help="directory of bill files")
    parser.add_argument("--truth", type=Path, help="truth CSV with manual fields")
    parser.add_argument("--out", type=Path, default=Path("evals/results.csv"))
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(evaluate(parse_args())))
