import json
import os
import re
import tempfile
import unittest
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from scoreboard import site
from tests import fixtures

BASE = "https://example.test/scores"


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.meta, self.title, self.ld = [], {}, "", []
        self._t = self._ld = self._svg = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "svg":
            self._svg = True
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in ("link", "script", "iframe") and (a.get("href") or a.get("src")):
            self.links.append(a.get("href") or a.get("src"))
        if tag == "meta" and (a.get("name") or a.get("property")):
            self.meta[a.get("name") or a.get("property")] = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical":
            self.meta["canonical"] = a["href"]
        if tag == "title" and not self.title and not self._svg:
            self._t = True
        if tag == "script" and a.get("type") == "application/ld+json":
            self._ld, self._buf = True, []

    def handle_endtag(self, tag):
        if tag == "title":
            self._t = False
        if tag == "svg":
            self._svg = False
        if tag == "script" and self._ld:
            self.ld.append("".join(self._buf))
            self._ld = False

    def handle_data(self, d):
        if self._t:
            self.title += d
        if self._ld:
            self._buf.append(d)


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp()
        fixtures.write_work(cls.work)
        cls.out = tempfile.mkdtemp()
        os.environ["SB_BASE_URL"] = BASE
        cls.ctx = site.build(cls.work, out=cls.out, quiet=True)
        cls.pages = {}
        for root, _, files in os.walk(cls.out):
            for f in files:
                if f.endswith(".html") and "_og" not in root:
                    p = os.path.join(root, f)
                    with open(p, encoding="utf-8") as fh:
                        cls.pages[os.path.relpath(p, cls.out)] = fh.read()

    @classmethod
    def tearDownClass(cls):
        del os.environ["SB_BASE_URL"]

    def test_core_pages(self):
        for p in ("index.html", "week/2026-w43/index.html", "week/2026-w42/index.html", "weeks/index.html", "league/tech/index.html",
                  "league/funds/index.html", "state/ca/index.html", "state/international/index.html", "states/index.html",
                  "season/index.html", "game/index.html", "about/index.html", "company/105/index.html", "embed/week/index.html", "404.html"):
            self.assertIn(p, self.pages, p)
        for f in ("sitemap.xml", "sitemap-pages.xml", "robots.txt", "data/latest-week.json", "data/game.json", "data/source.json",
                  "urls-priority.txt", ".nojekyll"):
            self.assertTrue(os.path.exists(os.path.join(self.out, f)), f)

    def test_home_shows_the_latest_complete_week(self):
        html = self.pages["index.html"]
        self.assertIn("Week 43, 2026", html)
        self.assertIn("Epsilon AI Corp", html)
        self.assertIn("$184M raised in 6 new private raises", html)

    def test_rule_breakers_never_reach_a_leaderboard(self):
        for rel in ("index.html", "week/2026-w43/index.html", "season/index.html", "league/tech/index.html"):
            for name in ("Kappa Merger Sub", "Lambda Annuity Co", "Mu Seed Inc"):
                self.assertNotIn(name, self.pages[rel], "%s on %s" % (name, rel))

    def test_seo_on_indexable_pages(self):
        for rel, html in self.pages.items():
            p = P()
            p.feed(html)
            if p.meta.get("robots") == "noindex":
                continue
            self.assertTrue(p.title.strip(), rel)
            self.assertLessEqual(len(p.title), 110, rel)
            self.assertTrue(30 <= len(p.meta.get("description", "")) <= 320, rel)
            self.assertTrue(p.meta.get("canonical", "").startswith(BASE + "/"), rel)
            self.assertTrue(p.meta.get("og:image", "").startswith(BASE + "/og/"), rel)
            for block in p.ld:
                json.loads(block)

    def test_internal_links_resolve(self):
        missing = []
        for rel, html in self.pages.items():
            if rel == "404.html":
                continue
            p = P()
            p.feed(html)
            for href in p.links:
                if href.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = urlparse(urljoin("http://x/" + rel, href)).path.lstrip("/")
                if not target or target.endswith("/"):
                    target += "index.html"
                if target.startswith("og/"):
                    continue
                if not os.path.exists(os.path.join(self.out, target)):
                    missing.append("%s -> %s" % (rel, href))
        self.assertEqual(missing, [])

    def test_disclaimer_and_attribution_everywhere(self):
        for rel, html in self.pages.items():
            if rel.startswith("embed/"):
                continue
            self.assertIn("not investment advice", html, rel)
            self.assertIn("CC BY 4.0", html, rel)

    def test_sitemap_index_lists_company_pages(self):
        with open(os.path.join(self.out, "sitemap.xml")) as fh:
            idx = fh.read()
        files = re.findall(r"<loc>%s/(sitemap-[^<]+)</loc>" % re.escape(BASE), idx)
        self.assertIn("sitemap-pages.xml", files)
        allurls = ""
        for f in files:
            with open(os.path.join(self.out, f)) as fh:
                allurls += fh.read()
        self.assertIn("%s/company/105/" % BASE, allurls)
        self.assertNotIn("/embed/", allurls)

    def test_game_deck(self):
        with open(os.path.join(self.out, "data/game.json")) as fh:
            deck = json.load(fh)["deck"]
        self.assertTrue(deck)
        self.assertTrue(all(c["amount"] >= 2_000_000 for c in deck))
        self.assertEqual(len({c["name"] for c in deck}), len(deck))

    def test_provisional_rows_are_labelled(self):
        self.assertIn("provisional", self.pages["week/2026-w43/index.html"])

    def test_week_recap_is_generated_from_numbers(self):
        html = self.pages["week/2026-w43/index.html"]
        self.assertIn("6 companies reported $184M", html)
        self.assertIn("The biggest was Epsilon AI Corp", html)


if __name__ == "__main__":
    unittest.main()
