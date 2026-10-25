import json
import os
import tempfile
import unittest
from datetime import date

from scoreboard import model, sources
from tests import fixtures


def board():
    tmp = tempfile.mkdtemp()
    meta = fixtures.write_work(tmp)
    rows = sources.read_rows(os.path.join(tmp, "filings.csv.gz"))
    with open(os.path.join(tmp, "first_seen.json")) as fh:
        first = json.load(fh)
    return model.Board(rows, first, meta, today=date(2026, 10, 25))


class HelperTests(unittest.TestCase):
    def test_money(self):
        self.assertEqual(model.money(602_000_000), "$602M")
        self.assertEqual(model.money(1_585_000_000), "$1.58B")
        self.assertEqual(model.money(16_600_000_000), "$16.60B")
        self.assertEqual(model.money(5_000_000_000), "$5B")
        self.assertEqual(model.money(97_400_000), "$97.4M")
        self.assertEqual(model.money(850_000), "$850K")

    def test_display_name(self):
        self.assertEqual(model.display_name("COBIZ FINANCIAL INC"), "Cobiz Financial Inc")
        self.assertEqual(model.display_name("ACME FUND II LP"), "Acme Fund II LP")
        self.assertEqual(model.display_name("X.AI Holdings Corp."), "X.AI Holdings Corp.")
        self.assertEqual(model.display_name("MCDONALD HOLDINGS LLC"), "McDonald Holdings LLC")

    def test_weeks(self):
        self.assertEqual(model.iso_week(date(2026, 10, 23)), (2026, 43))
        self.assertEqual(model.week_bounds(2026, 43), (date(2026, 10, 19), date(2026, 10, 25)))
        self.assertEqual(model.week_label(2026, 43), "Week 43, 2026 (Oct 19–25)")
        self.assertEqual(model.week_bounds(2026, 1)[0], date(2025, 12, 29))

    def test_states(self):
        self.assertEqual(model.state_key("CA"), "CA")
        self.assertEqual(model.state_key("A1"), model.INTL)
        self.assertEqual(model.state_slug(model.INTL), "international")
        self.assertEqual(model.league_of("Biotechnology"), "health")
        self.assertEqual(model.league_of("Something new"), "open")


class BoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = board()

    def test_friday_completes_the_week(self):
        self.assertEqual(self.b.latest_week, (2026, 43))
        self.assertIsNone(self.b.current_week)

    def test_midweek_data_keeps_last_week_as_latest(self):
        tmp = tempfile.mkdtemp()
        meta = fixtures.write_work(tmp, complete_through="2026-10-21")
        rows = [r for r in sources.read_rows(os.path.join(tmp, "filings.csv.gz")) if r["filing_date"] <= "2026-10-21"]
        b = model.Board(rows, {}, meta)
        self.assertEqual(b.latest_week, (2026, 42))
        self.assertEqual(b.current_week, (2026, 43))

    def test_only_new_raises_are_ranked(self):
        names = {x.name for x in self.b.raises}
        self.assertNotIn("Kappa Merger Sub", names)        # business combination
        self.assertNotIn("Lambda Annuity Co", names)       # first sale years before filing
        self.assertNotIn("Mu Seed Inc", names)             # nothing sold
        self.assertEqual(sum(1 for x in self.b.raises if x.name == "Alpha Robotics Inc"), 1)  # amendment not re-ranked

    def test_week_summary(self):
        s = self.b.week_summary((2026, 43))
        self.assertEqual(s["count"], 6)
        self.assertEqual(s["top"][0].name, "Epsilon AI Corp")
        self.assertEqual(s["total"], 184_000_000)
        self.assertEqual(dict(s["leagues"])["tech"][0], 135_000_000)

    def test_funds_play_in_their_own_league(self):
        s = self.b.week_summary((2026, 42))
        self.assertEqual(s["funds_count"], 1)
        self.assertNotIn("Venture Fund IV, L.P.", [x.name for x in s["top"]])

    def test_rookies(self):
        rookies = {x.name for x in self.b.raises if x.rookie and x.date.year == 2026}
        self.assertIn("Epsilon AI Corp", rookies)
        self.assertNotIn("Alpha Robotics Inc", rookies)   # filed in 2019
        self.assertNotIn("Beta Bio, Inc.", rookies)       # first filed in 2025
        self.assertTrue([x for x in self.b.raises if x.name == "Beta Bio, Inc." and x.date.year == 2025][0].rookie)

    def test_provisional_flag_and_international(self):
        theta = [x for x in self.b.raises if x.name == "Theta Labs"][0]
        self.assertFalse(theta.confirmed)
        iota = [x for x in self.b.raises if x.name == "Iota Holdings Ltd"][0]
        self.assertEqual(iota.state, model.INTL)

    def test_standings_and_power_rankings(self):
        st = self.b.standings("league")
        self.assertEqual(st[0][0], "tech")
        pr = self.b.power_rankings("league")
        tech = [r for r in pr if r[1] == "tech"][0]
        self.assertEqual(tech[0], 0)

    def test_company_pages_need_a_million_dollar_raise(self):
        self.assertIn("105", self.b.companies)
        self.assertNotIn("112", self.b.companies)
        alpha = self.b.companies["101"]
        self.assertEqual(len(alpha["filings"]), 2)   # the notice and its amendment both show on the box score
        rank, n = self.b.season_rank(alpha["best"])
        self.assertTrue(rank and n)


if __name__ == "__main__":
    unittest.main()
