"""Build the static scoreboard site into dist/.

    python3 -m scoreboard.site [work_dir]

Environment (all optional):
    SB_BASE_URL      canonical origin + path (default: the GitHub Pages URL)
    SB_REPO          owner/name for correction links (default theguysaccount/espn-of-venture)
    SB_GOATCOUNTER   https://<code>.goatcounter.com/count (cookieless analytics; off when empty)
    SB_SPONSOR_URL   the money slot: a sponsor link shown in a clearly marked box (off when empty)
    SB_OUT           output directory (default dist/)
"""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import quote

from . import charts, model, sources
from .model import money, week_id, week_label, state_name, state_slug

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "Raise Scoreboard"
DEFAULT_BASE = "https://theguysaccount.github.io/espn-of-venture"
DEFAULT_REPO = "theguysaccount/espn-of-venture"
DISCLAIMER = ("Form D is a notice of an exempt securities offering filed with the SEC. It is not an offer to sell or a "
              "solicitation to buy securities, and this site is not investment advice. Amounts are as reported by "
              "issuers and may include debt, convertible notes, options or securities issued in an acquisition.")
LEAGUE_NAMES = {s: n for s, n, _, _ in model.LEAGUES}
LEAGUE_SHORT = {s: sh for s, _, sh, _ in model.LEAGUES}


def esc(s):
    return escape(str(s), quote=True)


class Ctx:
    def __init__(self, board, out=None):
        self.board = board
        self.base = os.environ.get("SB_BASE_URL", DEFAULT_BASE).rstrip("/")
        self.repo = os.environ.get("SB_REPO", DEFAULT_REPO)
        self.goat = os.environ.get("SB_GOATCOUNTER", "").strip()
        self.sponsor = os.environ.get("SB_SPONSOR_URL", "").strip()
        self.out = out or os.environ.get("SB_OUT") or os.path.join(ROOT, "dist")
        self.built = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.urls = []          # (url, lastmod, priority_group)
        self.og = []            # (name, html) share cards to render
        self.asset_v = asset_version()


class Page:
    def __init__(self, ctx, path):
        self.ctx, self.path = ctx, path
        depth = 0 if path in ("", "404.html") else path.rstrip("/").count("/") + 1
        self.prefix = "../" * depth

    def u(self, target=""):
        return self.prefix + target

    @property
    def canonical(self):
        return self.ctx.base + "/" + self.path


def asset_version():
    import hashlib
    h = hashlib.sha256()
    folder = os.path.join(ROOT, "site", "assets")
    for name in sorted(os.listdir(folder)):
        with open(os.path.join(folder, name), "rb") as fh:
            h.update(name.encode() + fh.read())
    return h.hexdigest()[:10]


NAV = [("", "Scoreboard"), ("weeks/", "Weeks"), ("league/tech/", "Leagues"), ("states/", "States"),
       ("season/", "Season"), ("game/", "Game"), ("about/", "About")]


def layout(pg, title, description, body, og="og/home.png", jsonld=None, noindex=False, body_class=""):
    c = pg.ctx
    lds = jsonld if isinstance(jsonld, list) else ([jsonld] if jsonld else [])
    full = title if SITE in title else "%s | %s" % (title, SITE)
    head = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>%s</title>" % esc(full), '<meta name="description" content="%s">' % esc(description),
            '<link rel="canonical" href="%s">' % esc(pg.canonical),
            '<meta property="og:type" content="website"><meta property="og:site_name" content="%s">' % SITE,
            '<meta property="og:title" content="%s">' % esc(title), '<meta property="og:description" content="%s">' % esc(description),
            '<meta property="og:url" content="%s">' % esc(pg.canonical), '<meta property="og:image" content="%s/%s">' % (esc(c.base), esc(og)),
            '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
            '<meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#0b1220">',
            '<link rel="icon" href="%s" type="image/svg+xml">' % pg.u("assets/favicon.svg"),
            '<link rel="stylesheet" href="%s">' % pg.u("assets/style.css?v=" + c.asset_v)]
    if noindex:
        head.append('<meta name="robots" content="noindex">')
    if c.goat:
        head.append('<meta name="sb-goatcounter" content="%s">' % esc(c.goat))
    for ld in lds:
        head.append('<script type="application/ld+json">%s</script>' % json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
    head.append("</head>")
    nav = "".join('<a href="%s"%s>%s</a>' % (pg.u(p), ' aria-current="page"' if p == pg.path else "", n) for p, n in NAV)
    ticker = ticker_html(pg)
    header = ('<header class="site"><div class="wrap"><a class="brand" href="%s"><span class="logo">RS</span>%s</a><nav aria-label="Main">%s</nav></div>%s</header>'
              % (pg.u(""), SITE, nav, ticker))
    meta = c.board.meta
    sponsor = ""
    if c.sponsor:
        sponsor = ('<p class="sponsor">Sponsored: <a href="%s" rel="sponsored noopener">this week’s scoreboard sponsor</a></p>' % esc(c.sponsor))
    footer = ('<footer class="site"><div class="wrap">%s<p><strong>%s</strong> turns SEC Form D filings into a weekly scoreboard of '
              'private raises. Data through %s, rebuilt daily by automation. <a href="%s">How it works</a> · '
              '<a href="%s">Data</a> · <a href="https://github.com/%s">Source</a> · '
              '<a href="https://github.com/%s/issues/new?labels=correction&title=Correction">Report an error</a></p>'
              '<p class="fine">%s Data: SEC EDGAR via the weio-ops/sec-form-d dataset (CC BY 4.0), cross-checked against '
              'XOOMAR/sec-form-d-offerings. No personal data is published.</p></div></footer>'
              % (sponsor, SITE, esc(meta["complete_through"]), pg.u("about/"), pg.u("about/#data"), esc(c.repo), esc(c.repo), esc(DISCLAIMER)))
    scripts = '<script src="%s" defer></script>' % pg.u("assets/app.js?v=" + c.asset_v)
    return "".join(head) + '<body class="%s">%s<main class="wrap">%s</main>%s%s</body></html>' % (esc(body_class), header, body, footer, scripts)


def ticker_html(pg):
    b = pg.ctx.board
    top = b.week_raises(b.latest_week)[:8]
    if not top:
        return ""
    items = "".join('<a href="%s"><b>%s</b> %s</a>' % (pg.u("company/%s/" % x.cik), esc(x.name), money(x.amount)) for x in top)
    return ('<div class="ticker" aria-label="Biggest raises this week"><div class="wrap"><span class="tk-label">%s</span>%s</div></div>'
            % (esc("Week %d" % b.latest_week[1]), items))


def league_chip(pg, slug):
    return '<a class="chip lg-%s" href="%s">%s</a>' % (slug, pg.u("league/%s/" % slug), esc(LEAGUE_SHORT[slug]))


def company_link(pg, x):
    if x.cik in pg.ctx.board.companies:
        return '<a href="%s">%s</a>' % (pg.u("company/%s/" % x.cik), esc(x.name))
    return esc(x.name)


def raises_table(pg, xs, start=1, show_week=False, show_league=True, caption=None, show_state=True):
    if not xs:
        return '<p class="fine">No new raises reported.</p>'
    head = ('<th class="rk">#</th><th>Company</th>%s%s<th class="num">Raised</th><th class="num hide-s">Raising</th><th class="hide-s">Filed</th>'
            % ("<th>League</th>" if show_league else "", '<th class="hide-s">State</th>' if show_state else ""))
    rows = []
    for i, x in enumerate(xs):
        badges = ""
        if x.rookie:
            badges += ' <span class="tag rookie" title="First Form D ever filed by this company">rookie</span>'
        if not x.confirmed:
            badges += ' <span class="tag prov" title="Seen in one source so far; confirmed when a second source has it">provisional</span>'
        offering = "indefinite" if x.offering_indefinite else (money(x.offering) if x.offering else "—")
        rows.append('<tr><td class="rk">%d</td><td>%s%s</td>%s%s<td class="num"><b>%s</b></td><td class="num hide-s">%s</td><td class="hide-s">%s</td></tr>'
                    % (start + i, company_link(pg, x), badges, ("<td>%s</td>" % league_chip(pg, x.league)) if show_league else "",
                       ('<td class="hide-s"><a href="%s">%s</a></td>' % (pg.u("state/%s/" % state_slug(x.state)), esc(x.state if x.state != model.INTL else "Intl")))
                       if show_state else "", money(x.amount), offering, x.date.strftime("%b %-d") if not show_week else x.date.isoformat()))
    cap = ('<caption>%s</caption>' % esc(caption)) if caption else ""
    return '<div class="scroll"><table class="board">%s<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (cap, head, "".join(rows))


def standings_table(pg, rows, key, show_move=True):
    out = []
    for i, g, total, count, before in rows:
        if key == "league":
            name = '<a href="%s">%s</a>' % (pg.u("league/%s/" % g), esc(LEAGUE_NAMES[g]))
        else:
            name = '<a href="%s">%s</a>' % (pg.u("state/%s/" % state_slug(g)), esc(state_name(g)))
        move = ""
        if show_move:
            if before is None:
                move = '<span class="mv new">new</span>'
            elif before > i:
                move = '<span class="mv up" title="up from #%d last week">▲%d</span>' % (before + 1, before - i)
            elif before < i:
                move = '<span class="mv down" title="down from #%d last week">▼%d</span>' % (before + 1, i - before)
            else:
                move = '<span class="mv same">–</span>'
        out.append('<tr><td class="rk">%d</td><td>%s</td><td class="num"><b>%s</b></td><td class="num">%s</td><td>%s</td></tr>'
                   % (i + 1, name, money(total), "{:,}".format(count), move))
    return ('<div class="scroll"><table class="board standings"><thead><tr><th class="rk">#</th><th>%s</th><th class="num">Raised</th>'
            '<th class="num">Raises</th><th>Move</th></tr></thead><tbody>%s</tbody></table></div>' % ("League" if key == "league" else "State", "".join(out)))


def share_block(pg, text, slug, embed_path=None):
    url = pg.canonical
    embed = ""
    if embed_path:
        code = '<iframe src="%s/%s" width="100%%" height="420" style="border:0;max-width:520px" title="%s" loading="lazy"></iframe>' % (
            pg.ctx.base, embed_path, esc(text))
        embed = ('<label class="fine" for="embed-%s">Embed this leaderboard (updates daily)</label><textarea id="embed-%s" class="code" readonly rows="2">%s</textarea>'
                 % (slug, slug, esc(code)))
    return ('<section class="panel share"><div class="share-row" data-share-url="%s" data-share-text="%s" data-slug="%s">'
            '<button type="button" class="btn" data-share="native">Share</button>'
            '<a class="btn ghost" data-share="x" href="https://twitter.com/intent/tweet?text=%s&url=%s" target="_blank" rel="noopener">Post on X</a>'
            '<a class="btn ghost" data-share="linkedin" href="https://www.linkedin.com/sharing/share-offsite/?url=%s" target="_blank" rel="noopener">LinkedIn</a>'
            '<button type="button" class="btn ghost" data-copy="%s">Copy link</button></div>%s</section>'
            % (esc(url), esc(text), esc(slug), quote(text), quote(url), quote(url), esc(url), embed))


# ---------------------------------------------------------------- pages

def home(ctx):
    b = ctx.board
    pg = Page(ctx, "")
    wk = b.latest_week
    s = b.week_summary(wk)
    top1 = s["top"][0] if s["top"] else None
    lead = ""
    if top1:
        lead = ('<p class="lead-raise">Biggest raise: %s <b>%s</b> %s · %s</p>'
                % (company_link(pg, top1), money(top1.amount), league_chip(pg, top1.league), esc(state_name(top1.state))))
    current = ""
    if b.current_week:
        cs = b.week_raises(b.current_week)
        current = ('<section class="panel"><h2>This week so far <span class="count">%s</span></h2><p class="lede">%s: %s across %d new raises filed through %s. '
                   'Final standings when Friday’s filings are in.</p>%s</section>'
                   % (esc("Week %d" % b.current_week[1]), esc(week_label(*b.current_week)), money(sum(x.amount for x in cs)), len(cs),
                      esc(b.meta["complete_through"]), raises_table(pg, cs[:10])))
    pr_league = b.power_rankings("league")
    pr_state = b.power_rankings("state")[:10]
    league_bars = charts.hbars([(LEAGUE_SHORT[g], t, "%s · %s" % (money(t), "{:,}".format(c)), "lg-" + g)
                                for g, t, c in b.standings("league")], "Season totals by league")
    body = (
        '<section class="hero"><p class="kicker">%s · SEC Form D scoreboard</p><h1>%s raised in %d new private raises</h1>'
        '<p class="sub">Every startup and company that filed a new Form D with the SEC this week, ranked by money already raised, '
        'with league tables by sector and standings by state.</p>%s<p class="cta"><a class="btn" href="%s">Full week %d recap</a> '
        '<a class="btn ghost" href="%s">Play Higher or Lower</a></p></section>'
        '<section class="panel"><h2>Top 10 raises <span class="count">%s</span></h2>%s<p class="more"><a href="%s">All %d raises this week →</a></p></section>%s'
        '<div class="grid2"><section class="panel"><h2>League standings <span class="count">%d season</span></h2>%s%s</section>'
        '<section class="panel"><h2>State standings <span class="count">top 10</span></h2>%s<p class="more"><a href="%s">All states →</a></p></section></div>'
        '<div class="grid2"><section class="panel"><h2>Rookies of the week</h2><p class="lede">Companies filing their first Form D ever.</p>%s</section>'
        '<section class="panel"><h2>Fund League this week</h2><p class="lede">%s across %d venture, private equity, hedge and other funds.</p>%s'
        '<p class="more"><a href="%s">Fund League →</a></p></section></div>'
        '<section class="panel"><h2>Season leaders <span class="count">%d</span></h2>%s<p class="more"><a href="%s">Top 100 of %d →</a></p></section>%s'
        % (esc(week_label(*wk)), money(s["total"]), s["count"], lead, pg.u("week/%s/" % week_id(*wk)), wk[1], pg.u("game/"),
           esc(week_label(*wk)), raises_table(pg, s["top"][:10]), pg.u("week/%s/" % week_id(*wk)), s["count"], current,
           b.season, standings_table(pg, pr_league, "league"), league_bars, standings_table(pg, pr_state, "state"), pg.u("states/"),
           raises_table(pg, s["rookies"][:5], show_league=True), money(s["funds_total"]), s["funds_count"],
           raises_table(pg, s["funds"][:5], show_league=False), pg.u("league/funds/"), b.season,
           raises_table(pg, b.season_raises()[:10]), pg.u("season/"), b.season,
           share_block(pg, "%s: %s raised in new private rounds (SEC Form D)" % (week_label(*wk), money(s["total"])), "home", "embed/week/")))
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": ctx.base + "/"},
          {"@context": "https://schema.org", "@type": "Dataset", "name": "Weekly private raises from SEC Form D filings",
           "description": "New Form D filings ranked by amount sold, grouped by sector league and state, rebuilt daily.",
           "url": ctx.base + "/", "license": "https://creativecommons.org/licenses/by/4.0/", "isAccessibleForFree": True,
           "creator": {"@type": "Organization", "name": SITE}, "temporalCoverage": "2024-01-01/%s" % b.meta["complete_through"],
           "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": ctx.base + "/data/latest-week.json"},
                            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": ctx.base + "/data/season-%d.csv" % b.season}]}]
    ctx.og.append(("home", og_card("%s" % week_label(*wk), "%s raised in %d new private raises" % (money(s["total"]), s["count"]),
                                   [(x.name, money(x.amount)) for x in s["top"][:5]])))
    return pg, layout(pg, "This week's biggest startup raises from SEC Form D filings",
                      "%s: %s raised across %d new Form D filings. Top raise: %s. League tables by sector, standings by state, updated daily."
                      % (week_label(*wk), money(s["total"]), s["count"], ("%s (%s)" % (top1.name, money(top1.amount))) if top1 else "none"),
                      body, og="og/home.png", jsonld=ld, body_class="home")


def recap_text(b, wk, s):
    """The weekly 'highlight show': plain sentences generated from the numbers, no model involved."""
    if not s["count"]:
        return "No new raises were reported this week."
    parts = []
    t = s["top"]
    parts.append("%d companies reported %s in new private raises on Form D in %s." % (s["count"], money(s["total"]), week_label(*wk)))
    if t:
        x = t[0]
        parts.append("The biggest was %s, %s in the %s from %s." % (x.name, money(x.amount), LEAGUE_NAMES[x.league], state_name(x.state)))
    if len(t) > 2:
        parts.append("%s (%s) and %s (%s) rounded out the top three." % (t[1].name, money(t[1].amount), t[2].name, money(t[2].amount)))
    if s["leagues"]:
        g, (tot, cnt) = s["leagues"][0]
        parts.append("The %s led all leagues with %s across %d raises." % (LEAGUE_NAMES[g], money(tot), cnt))
    if s["states"]:
        g, (tot, cnt) = s["states"][0]
        parts.append("%s topped the state standings with %s." % (state_name(g), money(tot)))
    prev = b.weeks[b.weeks.index(wk) - 1] if wk in b.weeks and b.weeks.index(wk) > 0 else None
    if prev:
        ptot = sum(x.amount for x in b.week_raises(prev))
        if ptot:
            ch = (s["total"] - ptot) / float(ptot)
            parts.append("That is %s%.0f%% versus the week before (%s)." % ("up " if ch >= 0 else "down ", abs(ch) * 100, money(ptot)))
    if s["rookies"]:
        parts.append("%d of the %d were first-time Form D filers, led by %s (%s)." % (len([x for x in b.week_raises(wk) if x.rookie]), s["count"],
                                                                                     s["rookies"][0].name, money(s["rookies"][0].amount)))
    if s["funds_count"]:
        parts.append("In the Fund League, %d funds reported %s." % (s["funds_count"], money(s["funds_total"])))
    return " ".join(parts)


def week_page(ctx, wk):
    b = ctx.board
    pg = Page(ctx, "week/%s/" % week_id(*wk))
    s = b.week_summary(wk)
    idx = b.weeks.index(wk)
    prev = b.weeks[idx - 1] if idx > 0 else None
    nxt = b.weeks[idx + 1] if idx + 1 < len(b.weeks) else None
    nav = '<nav class="pager">%s%s</nav>' % (
        ('<a href="%s">← %s</a>' % (pg.u("week/%s/" % week_id(*prev)), esc(week_label(*prev)))) if prev else "<span></span>",
        ('<a href="%s">%s →</a>' % (pg.u("week/%s/" % week_id(*nxt)), esc(week_label(*nxt)))) if nxt else "<span></span>")
    league_rows = "".join('<tr><td>%s</td><td class="num"><b>%s</b></td><td class="num">%d</td></tr>' % (league_chip(pg, g), money(t), c)
                          for g, (t, c) in s["leagues"])
    state_rows = "".join('<tr><td><a href="%s">%s</a></td><td class="num"><b>%s</b></td><td class="num">%d</td></tr>'
                         % (pg.u("state/%s/" % state_slug(g)), esc(state_name(g)), money(t), c) for g, (t, c) in s["states"][:15])
    all_raises = b.week_raises(wk)
    body = (
        '<nav class="crumbs"><a href="%s">Scoreboard</a> › <a href="%s">Weeks</a> › %s</nav>'
        '<section class="hero"><p class="kicker">Weekly recap</p><h1>Biggest private raises: %s</h1><p class="sub recap">%s</p></section>%s'
        '<section class="panel"><h2>Top 25</h2>%s</section>'
        '<div class="grid2"><section class="panel"><h2>By league</h2><div class="scroll"><table class="board"><thead><tr><th>League</th><th class="num">Raised</th>'
        '<th class="num">Raises</th></tr></thead><tbody>%s</tbody></table></div></section>'
        '<section class="panel"><h2>By state</h2><div class="scroll"><table class="board"><thead><tr><th>State</th><th class="num">Raised</th>'
        '<th class="num">Raises</th></tr></thead><tbody>%s</tbody></table></div></section></div>'
        '<div class="grid2"><section class="panel"><h2>Rookies</h2><p class="lede">First Form D ever filed.</p>%s</section>'
        '<section class="panel"><h2>Fund League</h2><p class="lede">%s across %d funds.</p>%s</section></div>'
        '<details class="panel"><summary>All %d raises this week</summary>%s</details>%s%s'
        % (pg.u(""), pg.u("weeks/"), esc(week_label(*wk)), esc(week_label(*wk)), esc(recap_text(b, wk, s)), nav,
           raises_table(pg, s["top"]), league_rows, state_rows, raises_table(pg, s["rookies"][:10]), money(s["funds_total"]),
           s["funds_count"], raises_table(pg, s["funds"], show_league=False), len(all_raises), raises_table(pg, all_raises[25:], start=26),
           share_block(pg, "%s: %s in new private raises" % (week_label(*wk), money(s["total"])), "week-%s" % week_id(*wk)), nav))
    a, z = model.week_bounds(*wk)
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": "Biggest private raises: %s" % week_label(*wk),
          "datePublished": z.isoformat(), "dateModified": b.meta["complete_through"], "url": pg.canonical,
          "author": {"@type": "Organization", "name": SITE}, "publisher": {"@type": "Organization", "name": SITE},
          "image": "%s/og/week-%s.png" % (ctx.base, week_id(*wk))}
    ctx.og.append(("week-%s" % week_id(*wk), og_card(week_label(*wk), "%s in %d new private raises" % (money(s["total"]), s["count"]),
                                                     [(x.name, money(x.amount)) for x in s["top"][:5]])))
    top = s["top"][0] if s["top"] else None
    return pg, layout(pg, "Biggest startup raises, %s" % week_label(*wk),
                      "%s companies reported %s in new private raises on SEC Form D in %s.%s" % (
                          s["count"], money(s["total"]), week_label(*wk), (" Biggest: %s, %s." % (top.name, money(top.amount))) if top else ""),
                      body, og="og/week-%s.png" % week_id(*wk), jsonld=ld)


def weeks_index(ctx):
    b = ctx.board
    pg = Page(ctx, "weeks/")
    rows = []
    for wk in reversed(b.weeks):
        xs = b.week_raises(wk)
        top = xs[0] if xs else None
        rows.append('<tr><td><a href="%s">%s</a></td><td class="num"><b>%s</b></td><td class="num">%d</td><td>%s</td></tr>'
                    % (pg.u("week/%s/" % week_id(*wk)), esc(week_label(*wk)), money(sum(x.amount for x in xs)), len(xs),
                       ("%s (%s)" % (company_link(pg, top), money(top.amount))) if top else ""))
    series = [("W%d" % wk[1], v) for wk, v in b.week_series(n=52)]
    body = ('<h1>Every week’s scoreboard</h1><p class="sub">New private raises reported on SEC Form D, week by week.</p>'
            '<section class="panel"><h2>Weekly totals <span class="count">last 52 weeks</span></h2>%s</section>'
            '<section class="panel"><div class="scroll"><table class="board"><thead><tr><th>Week</th><th class="num">Raised</th><th class="num">Raises</th>'
            '<th>Biggest raise</th></tr></thead><tbody>%s</tbody></table></div></section>'
            % (charts.week_bars(series, "Weekly new private raises", highlight="W%d" % b.latest_week[1]), "".join(rows)))
    return pg, layout(pg, "Weekly startup funding scoreboard archive (SEC Form D)",
                      "Every week's total of new private raises reported on SEC Form D since %d, with the biggest raise each week." % (b.season - 1), body)


def league_page(ctx, slug):
    b = ctx.board
    pg = Page(ctx, "league/%s/" % slug)
    name = LEAGUE_NAMES[slug]
    funds = slug == "funds"
    season = b.season_raises(league=slug, funds=funds) if not funds else b.season_raises(funds=True)
    week = b.week_raises(b.latest_week, league=None if funds else slug, funds=funds)
    series = [("W%d" % wk[1], v) for wk, v in b.week_series(league=None if funds else slug, funds=funds, n=26)]
    inds = model.LEAGUE_BY_SLUG[slug][3]
    others = "".join('<a class="chip lg-%s%s" href="%s">%s</a> ' % (s, " on" if s == slug else "", pg.u("league/%s/" % s), esc(sh))
                     for s, _, sh, _ in model.LEAGUES)
    states = ""
    if not funds:
        tot = {}
        for x in season:
            t = tot.setdefault(x.state, [0, 0])
            t[0] += x.amount
            t[1] += 1
        srows = sorted(tot.items(), key=lambda kv: -kv[1][0])[:15]
        states = ('<section class="panel"><h2>Top states in the %s</h2><div class="scroll"><table class="board"><thead><tr><th>State</th><th class="num">Raised</th>'
                  '<th class="num">Raises</th></tr></thead><tbody>%s</tbody></table></div></section>'
                  % (esc(name), "".join('<tr><td><a href="%s">%s</a></td><td class="num"><b>%s</b></td><td class="num">%d</td></tr>'
                                        % (pg.u("state/%s/" % state_slug(g)), esc(state_name(g)), money(t), c) for g, (t, c) in srows)))
    fund_types = ""
    if funds:
        ft = {}
        for x in season:
            t = ft.setdefault(x.fund_type or "Unspecified", [0, 0])
            t[0] += x.amount
            t[1] += 1
        fund_types = ('<section class="panel"><h2>By fund type, %d</h2>%s</section>'
                      % (b.season, charts.hbars([(k, v[0], "%s · %d" % (money(v[0]), v[1]), "lg-funds") for k, v in sorted(ft.items(), key=lambda kv: -kv[1][0])],
                                                "Fund raises by type")))
    total = sum(x.amount for x in season)
    body = ('<nav class="crumbs"><a href="%s">Scoreboard</a> › Leagues</nav><p class="chips">%s</p>'
            '<section class="hero"><p class="kicker">%d season</p><h1>%s: biggest raises of %d</h1><p class="sub">%s across %s new raises so far this '
            'season. Industries: %s.</p></section>'
            '<section class="panel"><h2>This week <span class="count">%s</span></h2>%s</section>'
            '<section class="panel"><h2>Weekly totals <span class="count">last 26 weeks</span></h2>%s</section>'
            '<section class="panel"><h2>Season leaders <span class="count">top 50</span></h2>%s</section>%s%s%s'
            % (pg.u(""), others, b.season, esc(name), b.season, money(total), "{:,}".format(len(season)), esc(", ".join(inds)),
               esc(week_label(*b.latest_week)), raises_table(pg, week[:10], show_league=False),
               charts.week_bars(series, "%s weekly totals" % name, highlight="W%d" % b.latest_week[1]),
               raises_table(pg, season[:50], show_league=False), states, fund_types,
               share_block(pg, "%s: biggest raises of %d (SEC Form D)" % (name, b.season), "league-" + slug, "embed/league/%s/" % slug)))
    ctx.og.append(("league-%s" % slug, og_card("%s · %d season" % (name, b.season), "%s across %s raises" % (money(total), "{:,}".format(len(season))),
                                               [(x.name, money(x.amount)) for x in season[:5]], cls="lg-" + slug)))
    desc = ("Biggest %s raises of %d from SEC Form D filings: %s across %s raises. Leader: %s."
            % (name.replace(" League", "").lower() if not funds else "venture, private equity and hedge fund", b.season, money(total),
               "{:,}".format(len(season)), ("%s (%s)" % (season[0].name, money(season[0].amount))) if season else "none"))
    titles = {"tech": "Biggest tech startup funding rounds of %d", "health": "Biggest biotech and health startup raises of %d",
              "energy": "Biggest energy company raises of %d", "real-estate": "Biggest real estate raises of %d (Form D)",
              "finance": "Biggest fintech and financial company raises of %d",
              "main-street": "Biggest consumer, retail and industrial raises of %d",
              "open": "Biggest raises by companies filing as Other, %d", "funds": "Biggest venture and private fund raises of %d"}
    title = titles[slug] % b.season
    return pg, layout(pg, title, desc, body, og="og/league-%s.png" % slug)


def state_page(ctx, code):
    b = ctx.board
    pg = Page(ctx, "state/%s/" % state_slug(code))
    name = state_name(code)
    season = b.season_raises(state=code)
    week = b.week_raises(b.latest_week, state=code)
    last_season = b.season_raises(year=b.season - 1, state=code)
    series = [("W%d" % wk[1], v) for wk, v in b.week_series(state=code, n=26)]
    lg = {}
    for x in season:
        t = lg.setdefault(x.league, [0, 0])
        t[0] += x.amount
        t[1] += 1
    bars = charts.hbars([(LEAGUE_SHORT[g], v[0], "%s · %d" % (money(v[0]), v[1]), "lg-" + g) for g, v in sorted(lg.items(), key=lambda kv: -kv[1][0])],
                        "%s raises by league" % name)
    total = sum(x.amount for x in season)
    where = "outside the United States" if code == model.INTL else "in %s" % name
    body = ('<nav class="crumbs"><a href="%s">Scoreboard</a> › <a href="%s">States</a> › %s</nav>'
            '<section class="hero"><p class="kicker">%d season</p><h1>Biggest startup raises %s, %d</h1><p class="sub">%s across %s new raises reported on Form D '
            'by companies based %s this season. Last season: %s across %s.</p></section>'
            '<section class="panel"><h2>This week <span class="count">%s</span></h2>%s</section>'
            '<div class="grid2"><section class="panel"><h2>By league</h2>%s</section><section class="panel"><h2>Weekly totals</h2>%s</section></div>'
            '<section class="panel"><h2>Season leaders <span class="count">top 50</span></h2>%s</section>%s'
            % (pg.u(""), pg.u("states/"), esc(name), b.season, esc(where), b.season, money(total), "{:,}".format(len(season)), esc(where),
               money(sum(x.amount for x in last_season)), "{:,}".format(len(last_season)), esc(week_label(*b.latest_week)),
               raises_table(pg, week[:10], show_state=False), bars, charts.week_bars(series, "%s weekly totals" % name, highlight="W%d" % b.latest_week[1]),
               raises_table(pg, season[:50], show_state=False),
               share_block(pg, "Biggest startup raises %s, %d" % (where, b.season), "state-" + state_slug(code))))
    ctx.og.append(("state-%s" % state_slug(code), og_card("%s · %d season" % (name, b.season), "%s across %s raises" % (money(total), "{:,}".format(len(season))),
                                                          [(x.name, money(x.amount)) for x in season[:5]])))
    return pg, layout(pg, "Biggest startup raises %s, %d" % (where, b.season),
                      "Startup and company raises %s from SEC Form D filings, %d: %s across %s raises. Leader: %s."
                      % (where, b.season, money(total), "{:,}".format(len(season)), ("%s (%s)" % (season[0].name, money(season[0].amount))) if season else "none"),
                      body, og="og/state-%s.png" % state_slug(code))


def states_index(ctx):
    b = ctx.board
    pg = Page(ctx, "states/")
    body = ('<h1>State standings, %d season</h1><p class="sub">New private raises reported on Form D, by the state of the company’s principal place of '
            'business. Movement compares with the standings one week earlier.</p><section class="panel">%s</section>'
            % (b.season, standings_table(pg, b.power_rankings("state"), "state")))
    return pg, layout(pg, "Startup funding by state, %d season standings" % b.season,
                      "Which states raised the most private capital on SEC Form D in %d: totals, number of raises and week-over-week movement." % b.season, body)


def season_page(ctx):
    b = ctx.board
    pg = Page(ctx, "season/")
    s = b.season_raises()
    last = b.season_raises(year=b.season - 1)
    body = ('<h1>%d season leaders</h1><p class="sub">The 100 biggest new private raises reported on SEC Form D so far in %d (%s across %s raises), '
            'with last season’s top 25 below.</p><section class="panel">%s</section><section class="panel"><h2>%d season, top 25</h2>%s</section>%s'
            % (b.season, b.season, money(sum(x.amount for x in s)), "{:,}".format(len(s)), raises_table(pg, s[:100]), b.season - 1,
               raises_table(pg, last[:25]), share_block(pg, "Biggest private raises of %d (SEC Form D)" % b.season, "season")))
    return pg, layout(pg, "Biggest startup funding rounds of %d (SEC Form D)" % b.season,
                      "The 100 biggest new private raises of %d from SEC Form D filings, led by %s (%s)." % (b.season, s[0].name, money(s[0].amount)) if s else "Season leaders.", body)


def company_page(ctx, c):
    b = ctx.board
    pg = Page(ctx, "company/%s/" % c["cik"])
    best = c["best"]
    rank_l, n_l = b.season_rank(best, "league")
    rank_o, n_o = b.season_rank(best, "overall")
    loc = ", ".join(p for p in (c["city"], state_name(c["state"]) if c["state"] != model.INTL else "outside the US") if p)
    stats = [("Biggest raise", "%s <span class=\"fine\">filed %s</span>" % (money(best.amount), best.date.strftime("%b %-d, %Y"))),
             ("League", league_chip(pg, c["league"]) + ' <span class="fine">%s</span>' % esc(c["industry"])),
             ("Based in", esc(loc or "—")),
             ("Season rank", ("#%d of %s in the %s; #%d of %s overall (%d)" % (rank_l, "{:,}".format(n_l), LEAGUE_NAMES[c["league"]], rank_o,
                                                                                "{:,}".format(n_o), best.date.year)) if rank_l else "—")]
    if c["year_of_inc"]:
        stats.append(("Incorporated", esc(c["year_of_inc"])))
    if c["entity_type"]:
        stats.append(("Entity", esc(c["entity_type"])))
    grid = "".join('<div><dt>%s</dt><dd>%s</dd></div>' % (k, v) for k, v in stats)
    rows = []
    for x in reversed(c["filings"]):
        offering = "indefinite" if x.offering_indefinite else (money(x.offering) if x.offering else "—")
        kind = "New notice" if x.form_type == "D" else "Amendment"
        rows.append('<tr><td>%s</td><td>%s%s</td><td class="num"><b>%s</b></td><td class="num">%s</td><td class="num hide-s">%s</td><td class="hide-s">%s</td>'
                    '<td class="hide-s">%s</td><td><a href="%s" rel="nofollow noopener" target="_blank">SEC</a></td></tr>'
                    % (x.date.isoformat(), kind, "" if x.eligible or x.form_type != "D" else ' <span class="tag" title="Not counted as a new raise: first sale over a year earlier, an acquisition exchange, or nothing sold yet">not ranked</span>',
                       money(x.amount), offering, x.investors if x.investors is not None else "—",
                       esc(x.securities.replace(";", ", ") or "—"), esc(x.exemptions.replace(";", ", ") or "—"), esc(x.url)))
    table = ('<div class="scroll"><table class="board"><thead><tr><th>Filed</th><th>Form</th><th class="num">Sold</th><th class="num">Offering</th>'
             '<th class="num hide-s">Investors</th><th class="hide-s">Securities</th><th class="hide-s">Exemptions</th><th>Filing</th></tr></thead><tbody>%s</tbody></table></div>'
             % "".join(rows))
    peers = b.peers(best)
    body = ('<nav class="crumbs"><a href="%s">Scoreboard</a> › %s › %s</nav>'
            '<section class="hero box"><p class="kicker">Box score</p><h1>%s</h1><p class="sub">Reported %s sold in a new Form D filed %s%s.</p>'
            '<dl class="facts">%s</dl></section>'
            '<section class="panel"><h2>Form D filings since 2024 <span class="count">%d</span></h2>%s<p class="fine">Amounts are cumulative for each offering '
            'as of the filing date, so an amendment can repeat or update an earlier figure; filings are not added together. CIK %s.</p></section>'
            '<section class="panel"><h2>Similar raises, %d</h2>%s</section>%s'
            % (pg.u(""), league_chip(pg, c["league"]), esc(c["name"]), esc(c["name"]), money(best.amount), best.date.strftime("%B %-d, %Y"),
               (" (%s)" % esc(loc)) if loc else "", grid, len(c["filings"]), table, esc(c["cik"]), best.date.year,
               raises_table(pg, peers), share_block(pg, "%s raised %s (SEC Form D, %s)" % (c["name"], money(best.amount), best.date.strftime("%b %Y")), "co-" + c["cik"])))
    org = {"@context": "https://schema.org", "@type": "Organization", "name": c["name"], "url": pg.canonical}
    if c["city"] or c["state"] in model.US_STATES:
        org["address"] = {"@type": "PostalAddress", "addressLocality": c["city"] or None,
                          "addressRegion": c["state"] if c["state"] in model.US_STATES else None, "addressCountry": "US" if c["state"] in model.US_STATES else None}
        org["address"] = {k: v for k, v in org["address"].items() if v}
    if c["year_of_inc"]:
        org["foundingDate"] = c["year_of_inc"]
    title = "%s: %s raised (Form D, %s)" % (c["name"], money(best.amount), best.date.strftime("%B %Y"))
    if len(title) > 90:
        title = "%s: %s raised (Form D)" % (c["name"][:60], money(best.amount))
    desc = ("%s reported %s sold in a Form D filed with the SEC on %s%s. %d Form D filings since 2024, season rank #%s in the %s."
            % (c["name"], money(best.amount), best.date.strftime("%B %-d, %Y"), (" (%s)" % loc) if loc else "", len(c["filings"]),
               rank_l or "—", LEAGUE_NAMES[c["league"]]))
    return pg, layout(pg, title, desc, body, og="og/league-%s.png" % c["league"], jsonld=org)


def game_page(ctx):
    pg = Page(ctx, "game/")
    body = ('<section class="hero"><p class="kicker">Game</p><h1>Higher or Lower: which company raised more?</h1>'
            '<p class="sub">Two real raises from recent SEC Form D filings. Pick the one that raised more. Keep your streak going.</p></section>'
            '<section class="panel game" id="game" aria-live="polite"><p class="fine">Loading the deck…</p></section>'
            '<p class="fine">Amounts are the money already sold as reported on each company’s Form D. Your best streak is stored only in this browser.</p>'
            '<script src="%s" defer></script>' % pg.u("assets/game.js?v=" + ctx.asset_v))
    ctx.og.append(("game", og_card("Higher or Lower", "Which company raised more? A game built on real SEC Form D filings.", [])))
    return pg, layout(pg, "Higher or Lower: the startup funding guessing game",
                      "Which startup raised more? Guess between two real raises from recent SEC Form D filings and keep your streak going.",
                      body, og="og/game.png")


def about_page(ctx):
    pg = Page(ctx, "about/")
    with open(os.path.join(ROOT, "site", "pages", "about.html"), encoding="utf-8") as fh:
        html = fh.read()
    m = ctx.board.meta
    cc = m["cross_check"]
    html = (html.replace("{{u}}", pg.u("")).replace("{{repo}}", ctx.repo).replace("{{complete}}", esc(m["complete_through"]))
            .replace("{{overlap}}", "{:,}".format(cc["overlap"])).replace("{{agree}}", "%.2f%%" % (100 * (cc["agreement"] or 0)))
            .replace("{{since}}", esc(cc["since"])).replace("{{edgar}}", esc(m["edgar"])).replace("{{weio_asof}}", esc(m["weio"]["as_of"]))
            .replace("{{rows}}", "{:,}".format(m["rows"])).replace("{{disclaimer}}", esc(DISCLAIMER)))
    ctx.og.append(("about", og_card("How the scoreboard works", "Every new SEC Form D filing, ranked like a sports league.", [])))
    return pg, layout(pg, "How the Raise Scoreboard works", "How SEC Form D filings become a weekly raise scoreboard: data sources, cross-checks, "
                      "what counts as a new raise, and what Form D does not tell you.", html, og="og/about.png")


def embed_page(ctx, path, title, xs, link):
    pg = Page(ctx, path)
    rows = "".join('<li><span class="er">%d</span><span class="en">%s</span><span class="ea">%s</span></li>' % (i + 1, esc(x.name), money(x.amount))
                   for i, x in enumerate(xs[:10]))
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>%s</title><link rel="stylesheet" href="%s"></head><body class="embed">'
            '<a class="ewidget" href="%s" target="_blank" rel="noopener"><span class="eh">%s</span><ol>%s</ol><span class="ef">%s · SEC Form D · updated daily</span></a></body></html>'
            % (esc(title), pg.u("assets/style.css?v=" + ctx.asset_v), esc(link), esc(title), rows, SITE))
    return pg, html


def not_found(ctx):
    pg = Page(ctx, "404.html")
    pg.prefix = ctx.base + "/"
    body = '<h1>Off the board</h1><p class="sub">That page does not exist. <a href="%s/">Go to this week’s scoreboard</a>.</p>' % esc(ctx.base)
    return pg, layout(pg, "Page not found", "This page is not on the Raise Scoreboard.", body, noindex=True)


def og_card(kicker, headline, rows, cls=""):
    items = "".join("<li><span>%s</span><b>%s</b></li>" % (esc(n[:44]), esc(a)) for n, a in rows[:5])
    return ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="../assets/style.css"></head><body class="og %s">'
            '<div class="ogwrap"><div class="ogtop"><span class="logo">RS</span>%s</div><p class="ogk">%s</p><h1>%s</h1><ol>%s</ol></div></body></html>'
            % (esc(cls), SITE, esc(kicker), esc(headline), items))


# ---------------------------------------------------------------- exports and build

def game_json(b):
    weeks = b.weeks[-8:]
    pool = []
    for wk in weeks:
        pool += [x for x in b.week_raises(wk) if x.amount >= 2_000_000][:60]
    seen, deck = set(), []
    for x in sorted(pool, key=lambda x: -x.amount):
        if x.cik in seen:
            continue
        seen.add(x.cik)
        deck.append({"name": x.name, "league": LEAGUE_SHORT[x.league], "state": state_name(x.state), "amount": x.amount,
                     "date": x.date.isoformat(), "cik": x.cik if x.cik in b.companies else None})
    return {"generated": b.meta["complete_through"], "deck": deck}


def raise_dict(x):
    return {"accession": x.accession, "filed": x.date.isoformat(), "cik": x.cik, "company": x.name, "league": x.league,
            "industry": x.industry, "state": x.state, "amount_sold": x.amount, "offering_amount": x.offering,
            "first_sale": x.first_sale, "rookie": x.rookie, "confirmed": x.confirmed, "filing_url": x.url}


def write(ctx, path, text):
    full = os.path.join(ctx.out, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)


def emit(ctx, pg, html, lastmod=None, group="pages", sitemap=True):
    target = pg.path + "index.html" if (pg.path == "" or pg.path.endswith("/")) else pg.path
    write(ctx, target, html)
    if sitemap:
        ctx.urls.append((pg.canonical, lastmod or ctx.board.meta["complete_through"], group))


def build(work="work", out=None, quiet=False):
    rows = sources.read_rows(os.path.join(work, "filings.csv.gz"))
    with open(os.path.join(work, "first_seen.json")) as fh:
        first_seen = json.load(fh)
    with open(os.path.join(work, "source.json")) as fh:
        meta = json.load(fh)
    board = model.Board(rows, first_seen, meta)
    ctx = Ctx(board, out)
    if os.path.exists(ctx.out):
        shutil.rmtree(ctx.out)
    os.makedirs(ctx.out)
    shutil.copytree(os.path.join(ROOT, "site", "assets"), os.path.join(ctx.out, "assets"))
    emit(ctx, *home(ctx))
    for wk in board.weeks:
        pg, html = week_page(ctx, wk)
        emit(ctx, pg, html, lastmod=min(model.week_bounds(*wk)[1], board.complete_through).isoformat())
    emit(ctx, *weeks_index(ctx))
    for s, _, _, _ in model.LEAGUES:
        emit(ctx, *league_page(ctx, s))
    states = sorted({x.state for x in board.season_raises()} | {x.state for x in board.season_raises(year=board.season - 1)})
    for code in states:
        emit(ctx, *state_page(ctx, code))
    emit(ctx, *states_index(ctx))
    emit(ctx, *season_page(ctx))
    emit(ctx, *game_page(ctx))
    emit(ctx, *about_page(ctx))
    recent = board.complete_through - timedelta(days=14)
    for cik, c in board.companies.items():
        pg, html = company_page(ctx, c)
        emit(ctx, pg, html, lastmod=c["last"].isoformat(), group="recent" if c["last"] >= recent else "companies")
    lw = board.week_raises(board.latest_week)
    emit(ctx, *embed_page(ctx, "embed/week/", "Biggest raises, %s" % week_label(*board.latest_week), lw, ctx.base + "/"), sitemap=False)
    for s, name, _, _ in model.LEAGUES:
        xs = board.season_raises(league=s if s != "funds" else None, funds=s == "funds")
        emit(ctx, *embed_page(ctx, "embed/league/%s/" % s, "%s leaders, %d" % (name, board.season), xs, "%s/league/%s/" % (ctx.base, s)), sitemap=False)
    pg404, html404 = not_found(ctx)
    emit(ctx, pg404, html404, sitemap=False)
    for name, html in ctx.og:
        write(ctx, "_og/%s.html" % name, html)
    # data exports
    write(ctx, "data/latest-week.json", json.dumps({"week": week_id(*board.latest_week), "label": week_label(*board.latest_week),
                                                     "raises": [raise_dict(x) for x in lw]}, ensure_ascii=False))
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    wr = _csv.DictWriter(buf, fieldnames=list(raise_dict(lw[0]).keys()) if lw else ["accession"], lineterminator="\n")
    wr.writeheader()
    for x in board.season_raises():
        wr.writerow(raise_dict(x))
    write(ctx, "data/season-%d.csv" % board.season, buf.getvalue())
    write(ctx, "data/source.json", json.dumps(dict(meta, build=ctx.built, commit=os.environ.get("GITHUB_SHA", "")), indent=1))
    write(ctx, "data/game.json", json.dumps(game_json(board), ensure_ascii=False))
    # discovery
    key_path = os.path.join(ROOT, "site", "indexnow-key.txt")
    if os.path.exists(key_path):
        with open(key_path) as fh:
            key = fh.read().strip()
        write(ctx, "%s.txt" % key, key)
    groups = {"pages": [], "recent": [], "companies": []}
    for u, lm, g in ctx.urls:
        groups[g].append((u, lm))
    files = []
    chunks = [("pages", groups["pages"] + groups["recent"])]
    comp = groups["companies"]
    for i in range(0, len(comp), 40000):
        chunks.append(("companies-%d" % (i // 40000 + 1), comp[i:i + 40000]))
    for name, items in chunks:
        sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        sm += ["<url><loc>%s</loc><lastmod>%s</lastmod></url>" % (escape(u), lm[:10]) for u, lm in items]
        sm.append("</urlset>")
        write(ctx, "sitemap-%s.xml" % name, "\n".join(sm) + "\n")
        files.append("sitemap-%s.xml" % name)
    idx = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    idx += ["<sitemap><loc>%s/%s</loc><lastmod>%s</lastmod></sitemap>" % (ctx.base, f, meta["complete_through"]) for f in files]
    idx.append("</sitemapindex>")
    write(ctx, "sitemap.xml", "\n".join(idx) + "\n")
    write(ctx, "robots.txt", "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % ctx.base)
    write(ctx, "urls-priority.txt", "\n".join(u for u, _, g in ctx.urls if g in ("pages", "recent")) + "\n")
    write(ctx, "urls-all.txt", "\n".join(u for u, _, _ in ctx.urls) + "\n")
    write(ctx, ".nojekyll", "")
    if not quiet:
        print("built %d pages (%d weeks, %d companies) through %s into %s" % (len(ctx.urls), len(board.weeks), len(board.companies),
                                                                            meta["complete_through"], ctx.out))
    return ctx


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "work")
