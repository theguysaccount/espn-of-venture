"""Decide whether a fetched data set may be deployed, and whether it needs to be.

    python3 scripts/guard_data.py <live data/source.json URL> work/source.json [--event schedule|push|workflow_dispatch]

Prints deploy=true|false and reason=... (also to $GITHUB_OUTPUT). Exit 1 when the data fails the guard
(scoreboard.sources.guard): fewer rows than live, a complete-through date that went backwards, or mirrors that disagree.
On a scheduled run with the same data and the same code as the live build, it prints deploy=false and exits 0.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scoreboard import sources  # noqa: E402


def live_meta(url):
    try:
        req = urllib.request.Request(url + "?nocache=1", headers={"User-Agent": sources.UA_BASE})
        with urllib.request.urlopen(req, timeout=40) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def out(**kv):
    lines = ["%s=%s" % (k, v) for k, v in kv.items()]
    print("\n".join(lines))
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as fh:
            fh.write("\n".join(lines) + "\n")


def main(argv):
    url, local = argv[0], argv[1]
    event = argv[argv.index("--event") + 1] if "--event" in argv else "manual"
    with open(local) as fh:
        new = json.load(fh)
    try:
        old = live_meta(url)
    except Exception as exc:
        print("could not read the live source.json (%s); refusing to deploy" % exc)
        return 1
    problems = sources.guard(new, old)
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems))
        out(deploy="false", reason="guard")
        return 1
    if old and event == "schedule":
        same_data = (old.get("weio", {}).get("sha256") == new["weio"]["sha256"]
                     and old.get("xoomar", {}).get("sha256") == new["xoomar"]["sha256"]
                     and old.get("complete_through") == new["complete_through"] and new.get("edgar", "").startswith("off"))
        same_code = old.get("commit") and old.get("commit") == os.environ.get("GITHUB_SHA")
        if same_data and same_code:
            out(deploy="false", reason="unchanged")
            return 0
    out(deploy="true", reason="first" if not old else "changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
