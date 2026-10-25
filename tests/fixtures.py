"""Synthetic Form D rows for tests: two complete weeks plus a partial one, every league, and every rule-breaker."""
import gzip
import json
import os

from scoreboard import sources


def row(acc, filed, cik, name, industry, state, sold, first_sale, form="D", combo="false", offering=None, source="weio",
        confirmed="true", city="Austin", fund_type=""):
    r = {f: "" for f in sources.FIELDS}
    r.update({"accession": acc, "filing_date": filed, "form_type": form, "cik": cik, "name": name, "industry": industry,
              "state": state, "amount_sold": str(sold), "first_sale": first_sale, "business_combination": combo,
              "offering_amount": str(offering if offering is not None else sold), "offering_indefinite": "false",
              "filing_url": sources.filing_url(cik, acc), "source": source, "confirmed": confirmed, "city": city,
              "entity_type": "Corporation", "fund_type": fund_type, "securities": "Equity", "exemptions": "06b"})
    return r


def rows():
    out = []
    n = 0

    def add(*a, **k):
        nonlocal n
        n += 1
        out.append(row("0000000001-26-%06d" % n, *a, **k))

    # Week 42 of 2026 (Oct 12-18)
    add("2026-10-13", "101", "ALPHA ROBOTICS INC", "Other Technology", "CA", 50_000_000, "2026-10-01")
    add("2026-10-14", "102", "Beta Bio, Inc.", "Biotechnology", "MA", 20_000_000, "2026-10-02")
    add("2026-10-15", "103", "Gamma Grid LLC", "Other Energy", "TX", 5_000_000, "2026-09-20")
    add("2026-10-16", "901", "Venture Fund IV, L.P.", "Pooled Investment Fund", "NY", 300_000_000, "2026-10-01",
        fund_type="Venture Capital Fund")
    # Week 43 (Oct 19-25), complete through Friday the 23rd
    add("2026-10-19", "104", "Delta Realty Partners LLC", "Commercial", "FL", 8_000_000, "2026-10-05")
    add("2026-10-20", "105", "Epsilon AI Corp", "Other Technology", "NY", 120_000_000, "2026-10-10")
    add("2026-10-21", "106", "Zeta Foods Inc", "Restaurants", "IL", 2_000_000, "2026-10-01")
    add("2026-10-22", "107", "Eta Pay Inc", "Other Banking and Financial Services", "CA", 9_000_000, "2026-10-12")
    add("2026-10-23", "108", "Theta Labs", "Other", "WA", 30_000_000, "2026-10-15", source="xoomar", confirmed="false")
    add("2026-10-23", "109", "Iota Holdings Ltd", "Other Technology", "A1", 15_000_000, "2026-10-14")
    # rule-breakers (never ranked)
    add("2026-10-20", "101", "ALPHA ROBOTICS INC", "Other Technology", "CA", 60_000_000, "2026-10-01", form="D/A")
    add("2026-10-21", "110", "Kappa Merger Sub", "Other Technology", "DE", 900_000_000, "2026-10-15", combo="true")
    add("2026-10-21", "111", "Lambda Annuity Co", "Insurance", "NY", 700_000_000, "2020-01-01")
    add("2026-10-22", "112", "Mu Seed Inc", "Other Technology", "CA", 0, "")
    # earlier history for company 102 (not a rookie) and a 2025 season raise
    add("2025-03-03", "102", "Beta Bio, Inc.", "Biotechnology", "MA", 10_000_000, "2025-02-20")
    return out


def write_work(path, complete_through="2026-10-23"):
    os.makedirs(path, exist_ok=True)
    rs = rows()
    sources.write_rows(os.path.join(path, "filings.csv.gz"), rs)
    first = {}
    for r in rs:
        if r["cik"] not in first or r["filing_date"] < first[r["cik"]]:
            first[r["cik"]] = r["filing_date"]
    first["101"] = "2019-05-01"  # an older company
    with open(os.path.join(path, "first_seen.json"), "w") as fh:
        json.dump(first, fh)
    meta = {"fetched": "2026-10-25T09:00:00Z", "rows": len(rs), "start": "2024-01-01", "complete_through": complete_through,
            "weio": {"dataset": "weio-ops/sec-form-d", "as_of": "2026-10-25", "complete_through": "2026-10-23", "sha256": "x",
                     "license": "CC BY 4.0"},
            "xoomar": {"dataset": "XOOMAR/sec-form-d-offerings", "last_modified": "2026-10-25", "latest_filing": "2026-10-23",
                       "sha256": "y", "license": "public domain"},
            "edgar": "off (no EDGAR_CONTACT_EMAIL)",
            "cross_check": {"since": "2025-01-01", "overlap": 5000, "agree": 5000, "agreement": 1.0, "only_first": 0,
                            "only_second": 0, "mismatches": {}, "examples": []}, "first_seen_ciks": len(first)}
    with open(os.path.join(path, "source.json"), "w") as fh:
        json.dump(meta, fh)
    return meta
