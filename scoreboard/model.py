"""Turn normalised Form D filings into a sports-style scoreboard: leagues, weeks, seasons, standings, box scores."""
import re
from collections import defaultdict
from datetime import date, timedelta

# Leagues group the SEC's Form D industry groups. Funds (Pooled Investment Fund) play in their own league.
LEAGUES = [
    ("tech", "Tech League", "Tech", ["Other Technology", "Computers", "Telecommunications"]),
    ("health", "Bio & Health League", "Bio & Health", ["Biotechnology", "Pharmaceuticals", "Other Health Care",
                                                       "Hospitals and Physicians", "Health Insurance"]),
    ("energy", "Energy League", "Energy", ["Oil and Gas", "Other Energy", "Coal Mining", "Electric Utilities",
                                           "Energy Conservation", "Environmental Services"]),
    ("real-estate", "Real Estate League", "Real Estate", ["Commercial", "Residential", "Other Real Estate",
                                                          "REITS and Finance", "Construction"]),
    ("finance", "Finance League", "Finance", ["Investing", "Other Banking and Financial Services", "Commercial Banking",
                                              "Insurance", "Investment Banking"]),
    ("main-street", "Main Street League", "Main Street", ["Retailing", "Restaurants", "Manufacturing", "Business Services",
                                                          "Agriculture", "Lodging and Conventions",
                                                          "Tourism and Travel Services", "Airlines and Airports", "Other Travel"]),
    ("open", "Open League", "Open", ["Other"]),
    ("funds", "Fund League", "Funds", ["Pooled Investment Fund"]),
]
LEAGUE_BY_SLUG = {s: (s, n, sh, inds) for s, n, sh, inds in LEAGUES}
INDUSTRY_LEAGUE = {ind: s for s, _, _, inds in LEAGUES for ind in inds}
COMPANY_LEAGUES = [s for s, _, _, _ in LEAGUES if s != "funds"]

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
    "GU": "Guam", "VI": "U.S. Virgin Islands",
}
INTL = "XX"  # every non-US state/country code is grouped as International
MAX_FIRST_SALE_AGE = 400  # days between first sale and filing for a filing to count as a new raise
ABBREV = {"LLC", "LP", "LLP", "LLLP", "II", "III", "IV", "VI", "VII", "VIII", "IX", "USA", "US", "NA", "REIT", "SPV",
          "BDC", "AI", "PBC", "DST", "GP", "QOF", "QOZ", "NYC", "LA", "SF", "MD", "PC", "PLLC", "ESOP", "FBO", "PTE",
          "ULC", "NV", "SA", "AG", "AB", "BV", "PLC", "GMBH", "SPC", "SAS", "IP", "HQ", "TV", "RV", "EV", "3D", "AR", "VR"}


def money(v):
    v = float(v or 0)
    a = abs(v)
    if a >= 1e9:
        s = "%.2fB" % (v / 1e9)
        s = s.replace(".00B", "B")
    elif a >= 1e6:
        s = ("%.1fM" % (v / 1e6)) if a < 1e8 else ("%.0fM" % (v / 1e6))
        s = s.replace(".0M", "M")
    elif a >= 1e3:
        s = "%.0fK" % (v / 1e3)
    else:
        s = "%.0f" % v
    return "$" + s


def display_name(name):
    """Readable casing for ALL-CAPS filer names; mixed-case names are kept exactly as filed."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name or re.search(r"[a-z]", name):
        return name
    out = []
    for w in name.split(" "):
        core = re.sub(r"[^A-Z0-9]", "", w)
        if core in ABBREV or re.fullmatch(r"[A-Z]\.?", w) or re.fullmatch(r"([A-Z]\.){2,}", w):
            out.append(w)
        elif re.search(r"\d", w) and not re.fullmatch(r"\d+(ST|ND|RD|TH)", w):
            out.append(w)
        else:
            out.append(w[:1] + w[1:].lower())
    s = " ".join(out)
    return re.sub(r"\b(Mc|Mac)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s)


def state_key(code):
    return code if code in US_STATES else INTL


def state_name(code):
    return US_STATES.get(code, "International")


def state_slug(code):
    return "international" if code == INTL else code.lower()


def league_of(industry):
    return INDUSTRY_LEAGUE.get(industry or "", "open")


def iso_week(d):
    y, w, _ = d.isocalendar()
    return y, w


def week_id(y, w):
    return "%d-w%02d" % (y, w)


def week_bounds(y, w):
    monday = date.fromisocalendar(y, w, 1) if hasattr(date, "fromisocalendar") else _fromiso(y, w)
    return monday, monday + timedelta(days=6)


def _fromiso(y, w):
    jan4 = date(y, 1, 4)
    return jan4 - timedelta(days=jan4.isoweekday() - 1) + timedelta(weeks=w - 1)


def week_label(y, w):
    a, b = week_bounds(y, w)
    if a.month == b.month:
        span = "%s %d–%d" % (a.strftime("%b"), a.day, b.day)
    else:
        span = "%s %d – %s %d" % (a.strftime("%b"), a.day, b.strftime("%b"), b.day)
    return "Week %d, %d (%s)" % (w, y, span)


class Raise:
    __slots__ = ("accession", "date", "cik", "name", "league", "industry", "state", "city", "amount", "offering",
                 "offering_indefinite", "first_sale", "securities", "exemptions", "investors", "min_investment",
                 "entity_type", "year_of_inc", "fund_type", "revenue_range", "url", "confirmed", "rookie", "week",
                 "form_type", "eligible", "business_combination", "source")


def to_raise(r, first_seen):
    x = Raise()
    x.accession = r["accession"]
    x.date = date.fromisoformat(r["filing_date"])
    x.cik = r["cik"]
    x.name = display_name(r["name"])
    x.industry = r["industry"]
    x.league = league_of(r["industry"])
    x.state = state_key(r["state"])
    x.city = (r.get("city") or "").title()
    x.amount = int(r["amount_sold"] or 0)
    x.offering = int(r["offering_amount"]) if r.get("offering_amount") else None
    x.offering_indefinite = r.get("offering_indefinite") == "true"
    x.first_sale = r.get("first_sale") or ""
    x.securities = r.get("securities") or ""
    x.exemptions = r.get("exemptions") or ""
    x.investors = int(r["investors"]) if r.get("investors") else None
    x.min_investment = int(r["min_investment"]) if r.get("min_investment") else None
    x.entity_type = r.get("entity_type") or ""
    x.year_of_inc = r.get("year_of_inc") or ""
    x.fund_type = r.get("fund_type") or ""
    x.revenue_range = r.get("revenue_range") or ""
    x.url = r.get("filing_url") or ""
    x.confirmed = r.get("confirmed") == "true"
    x.form_type = r["form_type"]
    x.business_combination = r.get("business_combination") == "true"
    x.source = r.get("source", "")
    x.week = iso_week(x.date)
    fs = first_seen.get(x.cik)
    x.rookie = bool(fs) and fs >= x.date.isoformat() and x.form_type == "D"
    x.eligible = is_new_raise(r, x)
    return x


def is_new_raise(r, x):
    """A new raise: a new (not amended) notice, not an acquisition exchange, with money already sold and a first sale
    within about a year of the filing. Amendments and stale offerings stay in each company's box score."""
    if x.form_type != "D" or x.business_combination or x.amount <= 0 or not x.first_sale:
        return False
    try:
        fs = date.fromisoformat(x.first_sale)
    except ValueError:
        return False
    return (x.date - fs).days <= MAX_FIRST_SALE_AGE and fs <= x.date + timedelta(days=31)


class Board:
    """Everything the site renders, computed once."""

    def __init__(self, rows, first_seen, meta, today=None):
        self.meta = meta
        self.complete_through = date.fromisoformat(meta["complete_through"])
        self.today = today or date.today()
        self.all = [to_raise(r, first_seen) for r in rows]
        self.raises = [x for x in self.all if x.eligible]
        self.by_week = defaultdict(list)
        for x in self.raises:
            self.by_week[x.week].append(x)
        for v in self.by_week.values():
            v.sort(key=lambda x: (-x.amount, x.name))
        ct = self.complete_through
        cw = iso_week(ct)
        # A filing week is complete once Friday's filings are in (EDGAR accepts no Form D filings at weekends).
        if ct.isoweekday() >= 5:
            self.latest_week, self.current_week = cw, None
        else:
            prev = ct - timedelta(days=7)
            self.latest_week, self.current_week = iso_week(prev), cw
        self.weeks = sorted(w for w in self.by_week if w <= self.latest_week and w[0] >= ct.year - 1)
        self.season = ct.year
        self.companies = self._companies()

    # ---- weeks
    def week_raises(self, wk, league=None, state=None, funds=False):
        xs = self.by_week.get(wk, [])
        return [x for x in xs if (x.league == "funds") == funds and (league is None or x.league == league)
                and (state is None or x.state == state)]

    def week_summary(self, wk):
        ops = self.week_raises(wk)
        funds = self.week_raises(wk, funds=True)
        leagues = defaultdict(lambda: [0, 0])
        states = defaultdict(lambda: [0, 0])
        for x in ops:
            leagues[x.league][0] += x.amount
            leagues[x.league][1] += 1
            states[x.state][0] += x.amount
            states[x.state][1] += 1
        return {"week": wk, "total": sum(x.amount for x in ops), "count": len(ops), "top": ops[:25],
                "leagues": sorted(leagues.items(), key=lambda kv: -kv[1][0]),
                "states": sorted(states.items(), key=lambda kv: -kv[1][0]),
                "rookies": [x for x in ops if x.rookie][:15], "funds": funds[:10],
                "funds_total": sum(x.amount for x in funds), "funds_count": len(funds),
                "median": sorted(x.amount for x in ops)[len(ops) // 2] if ops else 0}

    def week_series(self, league=None, state=None, n=26, funds=False):
        weeks = self.weeks[-n:]
        return [(wk, sum(x.amount for x in self.week_raises(wk, league=league, state=state, funds=funds))) for wk in weeks]

    # ---- seasons (memoised: these lists are reused by thousands of pages)
    def season_raises(self, year=None, league=None, state=None, funds=False, through=None):
        year = year or self.season
        key = (year, league, state, funds, through)
        cache = self.__dict__.setdefault("_season_cache", {})
        if key not in cache:
            if league is not None or state is not None or through is not None:
                base = self.season_raises(year, funds=funds)
                out = [x for x in base if (league is None or x.league == league) and (state is None or x.state == state)
                       and (through is None or x.date <= through)]
            else:
                out = [x for x in self.raises if x.date.year == year and (x.league == "funds") == funds]
                out.sort(key=lambda x: (-x.amount, x.name))
            cache[key] = out
        return cache[key]

    def standings(self, key, year=None, through=None, league=None):
        """Season standings grouped by 'league' or 'state': [(group, total, count)] sorted by total."""
        tot = defaultdict(lambda: [0, 0])
        for x in self.season_raises(year, league=league, through=through):
            g = x.league if key == "league" else x.state
            tot[g][0] += x.amount
            tot[g][1] += 1
        return sorted(((g, t, c) for g, (t, c) in tot.items()), key=lambda r: -r[1])

    def power_rankings(self, key, league=None):
        """Standings with each group's rank one week earlier, for movement arrows."""
        now = self.standings(key, league=league)
        prev_end = week_bounds(*self.latest_week)[0] - timedelta(days=1)
        before = {g: i for i, (g, _, _) in enumerate(self.standings(key, through=prev_end, league=league))}
        return [(i, g, t, c, before.get(g)) for i, (g, t, c) in enumerate(now)]

    # ---- companies
    def _companies(self):
        by_cik = defaultdict(list)
        for x in self.all:
            by_cik[x.cik].append(x)
        out = {}
        for cik, xs in by_cik.items():
            xs.sort(key=lambda x: (x.date, x.accession))
            best = max((x for x in xs if x.eligible), key=lambda x: x.amount, default=None)
            if best is None:
                continue
            threshold = 50_000_000 if best.league == "funds" else 1_000_000
            if best.amount < threshold:
                continue
            latest = xs[-1]
            out[cik] = {"cik": cik, "name": latest.name, "filings": xs, "best": best, "league": best.league,
                        "state": latest.state, "city": next((x.city for x in reversed(xs) if x.city), ""),
                        "industry": latest.industry, "entity_type": latest.entity_type,
                        "year_of_inc": next((x.year_of_inc for x in reversed(xs) if x.year_of_inc), ""),
                        "first": xs[0].date, "last": latest.date}
        return out

    def season_rank(self, raise_, scope="league"):
        """1-based rank of a raise among the season's raises in its league (or overall)."""
        year, funds = raise_.date.year, raise_.league == "funds"
        league = raise_.league if scope == "league" else None
        key = (year, league, funds)
        idx = self.__dict__.setdefault("_rank_cache", {})
        if key not in idx:
            pool = self.season_raises(year, league=league, funds=funds)
            idx[key] = ({x.accession: i + 1 for i, x in enumerate(pool)}, len(pool))
        ranks, n = idx[key]
        return ranks.get(raise_.accession), n

    def peers(self, raise_, n=6):
        """Other raises in the same league (and state, when possible) in the same season, nearest in size."""
        year, funds = raise_.date.year, raise_.league == "funds"
        groups = self.__dict__.setdefault("_peer_cache", {})
        key = (year, raise_.league)
        if key not in groups:
            by_state = defaultdict(list)
            for x in self.season_raises(year, league=raise_.league, funds=funds):
                by_state[x.state].append(x)
            groups[key] = by_state
        by_state = groups[key]
        pool = [x for x in by_state.get(raise_.state, []) if x.cik != raise_.cik]
        if len(pool) < n:
            pool = [x for xs in by_state.values() for x in xs if x.cik != raise_.cik]
        pool = sorted(pool, key=lambda x: abs(x.amount - raise_.amount))[:n]
        return sorted(pool, key=lambda x: -x.amount)
