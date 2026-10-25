"""Weekly self-test of the live scoreboard.

    python3 scripts/health.py [base_url]

Checks that key pages answer, the data is fresh (complete-through within 6 days on weekdays' data), the mirrors still
agree, and a company page from this week resolves. Writes a report to $GITHUB_STEP_SUMMARY and exits 1 on failure.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import date

DEFAULT_BASE = "https://theguysaccount.github.io/espn-of-venture"
UA = "espn-of-venture/1.0 (+https://github.com/theguysaccount/espn-of-venture)"


def get(url):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + "selftest=%d" % int(time.time()), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.status, resp.read()


def main(base):
    base = base.rstrip("/")
    lines, failed = ["## Live scoreboard", ""], False
    for p in ("/", "/weeks/", "/league/tech/", "/league/funds/", "/states/", "/state/ca/", "/season/", "/game/", "/about/",
              "/sitemap.xml", "/data/latest-week.json", "/data/game.json", "/embed/week/"):
        try:
            st, body = get(base + p)
            ok = st == 200 and len(body) > 200
        except Exception as exc:
            st, ok = str(exc), False
        failed |= not ok
        lines.append("- %s %s %s" % ("ok  " if ok else "FAIL", p, st))
    try:
        _, body = get(base + "/data/source.json")
        meta = json.loads(body)
        age = (date.today() - date.fromisoformat(meta["complete_through"])).days
        stale = age > 6
        cc = meta["cross_check"]
        disagree = cc.get("agreement") is not None and cc["agreement"] < 0.995
        failed |= stale or disagree
        lines.append("- %s data complete through %s (%d days old)" % ("FAIL" if stale else "ok  ", meta["complete_through"], age))
        lines.append("- %s mirrors agree on %.2f%% of %s overlapping filings" % ("FAIL" if disagree else "ok  ", 100 * (cc["agreement"] or 0),
                                                                                "{:,}".format(cc["overlap"])))
        lines.append("- info EDGAR direct: %s" % meta.get("edgar"))
        _, wk = get(base + "/data/latest-week.json")
        raises = json.loads(wk)["raises"]
        if raises and raises[0].get("cik"):
            st, _ = get(base + "/company/%s/" % raises[0]["cik"])
            lines.append("- %s top raise box score /company/%s/ %s" % ("ok  " if st == 200 else "FAIL", raises[0]["cik"], st))
            failed |= st != 200
    except Exception as exc:
        failed = True
        lines.append("- FAIL data checks: %s" % exc)
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(text + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SB_BASE_URL", DEFAULT_BASE)))
