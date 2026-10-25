"""Submit URLs to IndexNow: every priority URL (scoreboard, weeks, leagues, states, companies filed in the last 14 days),
then a slice of all other URLs that rotates by calendar day, up to IndexNow's 10,000-URL limit per request.

    python3 scripts/indexnow.py dist [base_url]

Failures are printed, never raised: search pings must not fail a deploy.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BASE = "https://theguysaccount.github.io/espn-of-venture"
LIMIT = 10000


def pick(priority, everything, day=None):
    seen = set(priority)
    rest = [u for u in everything if u not in seen]
    room = max(0, LIMIT - len(priority))
    if not rest or not room:
        return priority[:LIMIT]
    day = day if day is not None else date.today().toordinal()
    start = (day * room) % len(rest)
    rot = (rest + rest)[start:start + min(room, len(rest))]
    return priority + rot


def read(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [u.strip() for u in fh if u.strip()]


def main(dist, base):
    base = base.rstrip("/")
    with open(os.path.join(ROOT, "site", "indexnow-key.txt")) as fh:
        key = fh.read().strip()
    urls = [u for u in pick(read(os.path.join(dist, "urls-priority.txt")), read(os.path.join(dist, "urls-all.txt")))
            if u.startswith(base + "/")]
    if not urls:
        print("no URLs to submit")
        return 0
    body = {"host": urllib.parse.urlparse(base).netloc, "key": key, "keyLocation": "%s/%s.txt" % (base, key), "urlList": urls}
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "espn-of-venture/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            print("IndexNow: HTTP %s for %d URLs" % (resp.status, len(urls)))
    except urllib.error.HTTPError as exc:
        print("IndexNow: HTTP %s (%s)" % (exc.code, exc.read()[:200]))
    except Exception as exc:
        print("IndexNow: failed (%s)" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist"),
                  sys.argv[2] if len(sys.argv) > 2 else os.environ.get("SB_BASE_URL", DEFAULT_BASE)))
