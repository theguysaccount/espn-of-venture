"""Fetch SEC Form D filings and normalise them into one table.

    python3 -m scoreboard.sources work/        # download, verify, cross-check, normalise into work/

Sources, in order of preference for each filing (all are the SEC's public-domain Form D data):
  1. EDGAR direct: the daily form index plus each filing's primary_doc.xml. Used only when the repository variable
     EDGAR_CONTACT_EMAIL is set, because sec.gov refuses automated clients whose User-Agent has no contact email.
  2. weio-ops/sec-form-d on Hugging Face (CC BY 4.0): every Form D since 2009 rebuilt weekly from the SEC's quarterly
     data sets and filing XML, with a SHA-256 manifest that is verified on download.
  3. XOOMAR/sec-form-d-offerings on Hugging Face (public domain): updated daily. Used to cross-check (2) and to fill
     the days after (2)'s last complete day.
A filing seen in two independent sources is marked confirmed. The build refuses data that fails the guard in
`guard()`: fewer rows than the last build, a complete-through date that went backwards, or mirrors that disagree.
"""
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

HF = "https://huggingface.co/datasets"
WEIO = "weio-ops/sec-form-d"
XOOMAR = "XOOMAR/sec-form-d-offerings"
UA_BASE = "espn-of-venture/1.0 (+https://github.com/theguysaccount/espn-of-venture)"
START = "2024-01-01"            # filings kept in full; older history is kept only as each CIK's first-seen date
FIELDS = ["accession", "filing_date", "form_type", "prev_accession", "cik", "name", "entity_type", "jurisdiction",
          "year_of_inc", "city", "state", "industry", "fund_type", "revenue_range", "nav_range", "exemptions",
          "first_sale", "yet_to_occur", "securities", "business_combination", "min_investment", "offering_amount",
          "offering_indefinite", "amount_sold", "remaining", "investors", "non_accredited", "filing_url", "source",
          "confirmed"]
SECURITY_LABELS = {"equity": "Equity", "debt": "Debt", "option": "Option/Warrant", "options": "Option/Warrant",
                   "warrant": "Option/Warrant", "pooled fund": "Pooled investment fund", "security to be acquired":
                   "Security to be acquired", "tenant-in-common": "Tenant-in-common", "mineral property":
                   "Mineral property", "other": "Other"}


def now_ts():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_get(url, ua=UA_BASE, tries=3, timeout=120, binary=False):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return body if binary else body.decode("utf-8")
        except Exception as exc:  # retried, then reported to the caller
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("GET %s failed: %s" % (url, last))


def to_int(v):
    if v in (None, "", "Indefinite"):
        return ""
    try:
        return str(int(round(float(str(v).replace(",", "")))))
    except ValueError:
        return ""


def norm_bool(v):
    s = str(v or "").strip().lower()
    if s in ("true", "y", "yes", "1"):
        return "true"
    if s in ("false", "n", "no", "0"):
        return "false"
    return ""


def norm_exemptions(v):
    parts = [p.strip() for p in re.split(r"[;,]", v or "") if p.strip()]
    return ";".join(parts)


def filing_url(cik, accession):
    return "https://www.sec.gov/Archives/edgar/data/%s/%s/" % (cik, accession.replace("-", ""))


# ---------------------------------------------------------------- weio mirror

def weio_row(r):
    cik = str(int(r["cik"])) if r.get("cik") else ""
    return {
        "accession": r["accession_number"], "filing_date": r["filing_date"], "form_type": r["form_type"],
        "prev_accession": r.get("previous_accession_number", ""), "cik": cik, "name": r["entity_name"],
        "entity_type": r.get("entity_type", ""), "jurisdiction": r.get("jurisdiction_of_inc", ""),
        "year_of_inc": r.get("year_of_inc", ""), "city": r.get("issuer_city", ""),
        "state": r.get("issuer_state_or_country", ""), "industry": r.get("industry_group", ""),
        "fund_type": r.get("investment_fund_type", ""), "revenue_range": r.get("revenue_range", ""),
        "nav_range": r.get("aggregate_nav_range", ""), "exemptions": norm_exemptions(r.get("federal_exemptions")),
        "first_sale": r.get("date_of_first_sale", ""), "yet_to_occur": norm_bool(r.get("first_sale_yet_to_occur")),
        "securities": r.get("securities_types", ""), "business_combination": norm_bool(r.get("is_business_combination")),
        "min_investment": to_int(r.get("minimum_investment")), "offering_amount": to_int(r.get("total_offering_amount")),
        "offering_indefinite": norm_bool(r.get("total_offering_indefinite")),
        "amount_sold": to_int(r.get("total_amount_sold")) or "0", "remaining": to_int(r.get("total_remaining")),
        "investors": to_int(r.get("total_number_already_invested")),
        "non_accredited": to_int(r.get("num_non_accredited_investors")),
        "filing_url": r.get("filing_index_url") or filing_url(cik, r["accession_number"]), "source": "weio",
        "confirmed": "",
    }


def read_weio(path, start=START):
    """Return (rows since `start`, {cik: first filing date ever})."""
    rows, first_seen = [], {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            cik = str(int(r["cik"])) if r.get("cik") else ""
            d = r["filing_date"]
            if cik and (cik not in first_seen or d < first_seen[cik]):
                first_seen[cik] = d
            if d >= start:
                rows.append(weio_row(r))
    return rows, first_seen


# ---------------------------------------------------------------- XOOMAR mirror

def xoomar_row(r):
    cik = str(int(r["cik"])) if r.get("cik") else ""
    secs = []
    for s in (r.get("security_types") or "").split(","):
        s = s.strip().lower()
        if s:
            secs.append(SECURITY_LABELS.get(s, s.capitalize()))
    amend = norm_bool(r.get("is_amendment")) == "true"
    offering = to_int(r.get("total_offering_amount"))
    return {
        "accession": r["accession_no"], "filing_date": r["filed_at"], "form_type": "D/A" if amend else "D",
        "prev_accession": "", "cik": cik, "name": r.get("issuer_name", ""), "entity_type": r.get("entity_type", ""),
        "jurisdiction": "", "year_of_inc": "", "city": "", "state": r.get("state", ""),
        "industry": r.get("industry_group", ""), "fund_type": r.get("fund_type", ""),
        "revenue_range": r.get("revenue_range", ""), "nav_range": "", "exemptions": norm_exemptions(r.get("exemptions")),
        "first_sale": r.get("date_of_first_sale", ""), "yet_to_occur": "", "securities": ";".join(secs),
        "business_combination": "", "min_investment": to_int(r.get("minimum_investment")), "offering_amount": offering,
        "offering_indefinite": "true" if not offering else "false", "amount_sold": to_int(r.get("total_amount_sold")) or "0",
        "remaining": "", "investors": to_int(r.get("investors_count")), "non_accredited": "",
        "filing_url": filing_url(cik, r["accession_no"]), "source": "xoomar", "confirmed": "",
    }


def read_xoomar(path, start=START):
    with open(path, encoding="utf-8", newline="") as fh:
        return [xoomar_row(r) for r in csv.DictReader(fh) if r.get("filed_at", "") >= start]


# ---------------------------------------------------------------- EDGAR direct (needs a contact email)

def edgar_ua(email):
    return "espn-of-venture %s (+https://github.com/theguysaccount/espn-of-venture)" % email


def daily_index_url(d):
    q = (d.month - 1) // 3 + 1
    return "https://www.sec.gov/Archives/edgar/daily-index/%d/QTR%d/form.%s.idx" % (d.year, q, d.strftime("%Y%m%d"))


IDX_RE = re.compile(r"^(D(?:/A)?)\s+(.+?)\s{2,}(\d+)\s+(\d{8})\s+(edgar/data/\S+\.txt)\s*$")


def parse_daily_index(text):
    out = []
    for line in text.splitlines():
        m = IDX_RE.match(line)
        if m:
            form, name, cik, filed, path = m.groups()
            acc = path.rsplit("/", 1)[1][:-4]
            out.append({"form_type": form, "name": name.strip(), "cik": str(int(cik)),
                        "filing_date": "%s-%s-%s" % (filed[:4], filed[4:6], filed[6:]), "accession": acc})
    return out


def _strip_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _t(node, path):
    if node is None:
        return ""
    el = node.find(path)
    return (el.text or "").strip() if el is not None and el.text else ""


def parse_primary_doc(xml_text, index_row):
    root = _strip_ns(ET.fromstring(xml_text))
    iss = root.find("primaryIssuer")
    off = root.find("offeringData")
    types = []
    t = off.find("typesOfSecuritiesOffered") if off is not None else None
    for tag, label in (("isEquityType", "Equity"), ("isDebtType", "Debt"), ("isOptionToAcquireType", "Option/Warrant"),
                       ("isSecurityToBeAcquiredType", "Security to be acquired"),
                       ("isPooledInvestmentFundType", "Pooled investment fund"), ("isTenantInCommonType", "Tenant-in-common"),
                       ("isMineralPropertyType", "Mineral property"), ("isOtherType", "Other")):
        if t is not None and norm_bool(_t(t, tag)) == "true":
            types.append(label)
    amounts = off.find("offeringSalesAmounts") if off is not None else None
    total_offering = _t(amounts, "totalOfferingAmount")
    exemptions = [(_x.text or "").strip() for _x in off.findall("federalExemptionsExclusions/item")] if off is not None else []
    cik = str(int(_t(iss, "cik") or index_row["cik"]))
    return {
        "accession": index_row["accession"], "filing_date": index_row["filing_date"], "form_type": index_row["form_type"],
        "prev_accession": _t(off, "typeOfFiling/newOrAmendment/previousAccessionNumber"), "cik": cik,
        "name": _t(iss, "entityName") or index_row["name"], "entity_type": _t(iss, "entityType"),
        "jurisdiction": _t(iss, "jurisdictionOfInc"), "year_of_inc": _t(iss, "yearOfInc/value"),
        "city": _t(iss, "issuerAddress/city"), "state": _t(iss, "issuerAddress/stateOrCountry"),
        "industry": _t(off, "industryGroup/industryGroupType"),
        "fund_type": _t(off, "industryGroup/investmentFundInfo/investmentFundType"),
        "revenue_range": _t(off, "issuerSize/revenueRange"), "nav_range": _t(off, "issuerSize/aggregateNetAssetValueRange"),
        "exemptions": ";".join(e for e in exemptions if e), "first_sale": _t(off, "typeOfFiling/dateOfFirstSale/value"),
        "yet_to_occur": norm_bool(_t(off, "typeOfFiling/dateOfFirstSale/yetToOccur")), "securities": ";".join(types),
        "business_combination": norm_bool(_t(off, "businessCombinationTransaction/isBusinessCombinationTransaction")),
        "min_investment": to_int(_t(off, "minimumInvestmentAccepted")), "offering_amount": to_int(total_offering),
        "offering_indefinite": "true" if total_offering.lower() == "indefinite" else "false",
        "amount_sold": to_int(_t(amounts, "totalAmountSold")) or "0", "remaining": to_int(_t(amounts, "totalRemaining")),
        "investors": to_int(_t(off, "investors/totalNumberAlreadyInvested")),
        "non_accredited": to_int(_t(off, "investors/numberNonAccreditedInvestors")),
        "filing_url": filing_url(cik, index_row["accession"]), "source": "edgar", "confirmed": "",
    }


def fetch_edgar(email, since, until, max_rate=5.0):
    """Filings from EDGAR's daily index for days after `since` up to `until` (dates). Fair access: <= 5 req/s."""
    ua = edgar_ua(email)
    rows, gap = [], 1.0 / max_rate
    d = since + timedelta(days=1)
    while d <= until:
        if d.weekday() < 5:
            try:
                index = parse_daily_index(http_get(daily_index_url(d), ua=ua, tries=2))
            except RuntimeError as exc:
                print("  EDGAR index %s unavailable: %s" % (d, str(exc)[:120]))
                index = []
            time.sleep(gap)
            for ir in index:
                url = filing_url(ir["cik"], ir["accession"]) + "primary_doc.xml"
                try:
                    rows.append(parse_primary_doc(http_get(url, ua=ua, tries=2), ir))
                except Exception as exc:
                    print("  EDGAR %s skipped: %s" % (ir["accession"], str(exc)[:120]))
                time.sleep(gap)
        d += timedelta(days=1)
    return rows


# ---------------------------------------------------------------- merge, cross-check, guard

COMPARE = ("amount_sold", "offering_amount", "state", "industry", "cik")


def cross_check(a_rows, b_rows, since="2025-01-01"):
    a = {r["accession"]: r for r in a_rows if r["filing_date"] >= since}
    b = {r["accession"]: r for r in b_rows if r["filing_date"] >= since}
    both = set(a) & set(b)
    mism = {f: 0 for f in COMPARE}
    examples = []
    for acc in both:
        bad = [f for f in COMPARE if (a[acc][f] or "") != (b[acc][f] or "")]
        for f in bad:
            mism[f] += 1
        if bad and len(examples) < 10:
            examples.append({"accession": acc, "fields": bad})
    agree = sum(1 for acc in both if all((a[acc][f] or "") == (b[acc][f] or "") for f in COMPARE))
    return {"since": since, "overlap": len(both), "agree": agree, "agreement": (agree / float(len(both))) if both else None,
            "only_first": len(set(a) - set(b)), "only_second": len(set(b) - set(a)), "mismatches": mism,
            "examples": examples}


def merge(weio_rows, xoomar_rows, edgar_rows):
    """One row per accession: weio first (richest), then EDGAR, then XOOMAR. confirmed = seen in two sources."""
    seen = {}
    for src, rows in (("weio", weio_rows), ("edgar", edgar_rows), ("xoomar", xoomar_rows)):
        for r in rows:
            cur = seen.get(r["accession"])
            if cur is None:
                seen[r["accession"]] = dict(r, confirmed="false", _sources=[src])
            else:
                cur["_sources"].append(src)
                cur["confirmed"] = "true"
    out = []
    for r in seen.values():
        r.pop("_sources", None)
        out.append(r)
    out.sort(key=lambda r: (r["filing_date"], r["accession"]))
    return out


def guard(new_meta, old_meta, min_agreement=0.995):
    """Problems that should stop a deploy (empty list = OK)."""
    problems = []
    cc = new_meta.get("cross_check", {})
    if cc.get("overlap", 0) < 1000:
        problems.append("cross-check overlap too small (%s filings)" % cc.get("overlap"))
    elif cc.get("agreement") is not None and cc["agreement"] < min_agreement:
        problems.append("mirrors agree on only %.2f%% of overlapping filings" % (100 * cc["agreement"]))
    if old_meta:
        if new_meta["complete_through"] < old_meta.get("complete_through", ""):
            problems.append("complete-through date went backwards (%s < %s)" % (new_meta["complete_through"],
                                                                                 old_meta["complete_through"]))
        old_n = old_meta.get("rows", 0)
        if old_n and new_meta["rows"] < old_n * 0.98:
            problems.append("row count fell from %d to %d" % (old_n, new_meta["rows"]))
    return problems


def write_rows(path, rows):
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def download(url, dest, expect_sha=None):
    if expect_sha and os.path.exists(dest) and sha256_file(dest) == expect_sha:
        return dest
    data = http_get(url, binary=True, timeout=300)
    if expect_sha and hashlib.sha256(data).hexdigest() != expect_sha:
        raise RuntimeError("checksum mismatch for %s" % url)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dest)
    return dest


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(work):
    os.makedirs(work, exist_ok=True)
    manifest = json.loads(http_get("%s/%s/resolve/main/manifest.json" % (HF, WEIO)))
    wf = manifest["files"]["data/offerings.csv.gz"]
    weio_path = download("%s/%s/resolve/main/data/offerings.csv.gz" % (HF, WEIO), os.path.join(work, "weio_offerings.csv.gz"),
                         expect_sha=wf["sha256"])
    weio_rows, first_seen = read_weio(weio_path)
    print("  weio: %d rows since %s, complete through %s" % (len(weio_rows), START, manifest["complete_through"]))
    info = json.loads(http_get("https://huggingface.co/api/datasets/%s?blobs=true" % XOOMAR))
    xsib = [s for s in info.get("siblings", []) if s["rfilename"].endswith(".csv")][0]
    xsha = (xsib.get("lfs") or {}).get("sha256")
    xoomar_path = download("%s/%s/resolve/main/%s" % (HF, XOOMAR, xsib["rfilename"]), os.path.join(work, "xoomar.csv"),
                           expect_sha=xsha)
    xoomar_rows = read_xoomar(xoomar_path)
    x_through = max(r["filing_date"] for r in xoomar_rows)
    print("  xoomar: %d rows since %s, latest %s" % (len(xoomar_rows), START, x_through))
    edgar_rows, edgar_note = [], "off (no EDGAR_CONTACT_EMAIL)"
    email = os.environ.get("EDGAR_CONTACT_EMAIL", "").strip()
    if email:
        since = date.fromisoformat(max(manifest["complete_through"], x_through))
        edgar_rows = fetch_edgar(email, since, date.today())
        edgar_note = "on: %d filings after %s" % (len(edgar_rows), since)
    print("  edgar: %s" % edgar_note)
    cc = cross_check(weio_rows, xoomar_rows)
    print("  cross-check: %d overlapping filings since %s, agreement %.4f" % (cc["overlap"], cc["since"], cc["agreement"] or 0))
    rows = merge(weio_rows, xoomar_rows, edgar_rows)
    complete = max(r["filing_date"] for r in rows)
    meta = {"fetched": now_ts(), "rows": len(rows), "start": START, "complete_through": complete,
            "weio": {"dataset": WEIO, "as_of": manifest.get("as_of_date"), "complete_through": manifest["complete_through"],
                     "sha256": wf["sha256"], "license": "CC BY 4.0"},
            "xoomar": {"dataset": XOOMAR, "last_modified": info.get("lastModified"), "latest_filing": x_through,
                       "sha256": xsha, "license": "public domain (SEC filings)"},
            "edgar": edgar_note, "cross_check": cc, "first_seen_ciks": len(first_seen)}
    write_rows(os.path.join(work, "filings.csv.gz"), rows)
    with open(os.path.join(work, "first_seen.json"), "w") as fh:
        json.dump(first_seen, fh, separators=(",", ":"))
    with open(os.path.join(work, "source.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    return meta


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "work"
    m = fetch(out)
    print("normalised %d filings through %s into %s" % (m["rows"], m["complete_through"], out))
