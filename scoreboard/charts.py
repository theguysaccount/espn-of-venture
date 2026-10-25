"""Server-rendered SVG charts for the scoreboard (no JavaScript)."""
from html import escape


def _money_short(v):
    v = float(v)
    if v >= 1e9:
        return "$%.1fB" % (v / 1e9)
    if v >= 1e6:
        return "$%.0fM" % (v / 1e6)
    if v >= 1e3:
        return "$%.0fK" % (v / 1e3)
    return "$%.0f" % v


def week_bars(series, label, highlight=None, width=680, height=220):
    """Vertical bars, one per week: series = [(label, value)]. The highlighted label gets the accent colour."""
    if not series:
        return ""
    pad_l, pad_r, pad_t, pad_b = 52, 10, 14, 30
    W, H = width - pad_l - pad_r, height - pad_t - pad_b
    top = max(v for _, v in series) or 1
    n = len(series)
    bw = W / float(n)
    out = ['<svg class="bars" viewBox="0 0 %d %d" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg"><title>%s</title>'
           % (width, height, escape(label, quote=True), escape(label))]
    for frac in (0.5, 1.0):
        y = pad_t + H * (1 - frac)
        out.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/><text class="tick" x="%d" y="%.1f" text-anchor="end">%s</text>'
                   % (pad_l, width - pad_r, y, y, pad_l - 6, y + 4, _money_short(top * frac)))
    for i, (lab, v) in enumerate(series):
        h = H * (v / float(top))
        x = pad_l + i * bw + bw * 0.15
        cls = "bar hi" if lab == highlight else "bar"
        out.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f"><title>%s: %s</title></rect>'
                   % (cls, x, pad_t + H - h, bw * 0.7, max(h, 0.5), escape(lab), _money_short(v)))
        if i % max(1, n // 6) == 0 or i == n - 1:
            out.append('<text class="tick" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (x + bw * 0.35, height - 10, escape(lab)))
    out.append("</svg>")
    return "".join(out)


def hbars(rows, label, width=460, row_h=26):
    """Horizontal bars: rows = [(name, value, extra_text, css_class)]."""
    if not rows:
        return ""
    top = max(r[1] for r in rows) or 1
    pad_l, pad_r = 104, 112
    height = row_h * len(rows) + 6
    W = width - pad_l - pad_r
    out = ['<svg class="hbars" viewBox="0 0 %d %d" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg"><title>%s</title>'
           % (width, height, escape(label, quote=True), escape(label))]
    for i, (name, v, extra, cls) in enumerate(rows):
        y = 3 + i * row_h
        w = W * (v / float(top))
        out.append('<text class="hl" x="%d" y="%.1f" text-anchor="end">%s</text>' % (pad_l - 8, y + row_h * 0.62, escape(name)))
        out.append('<rect class="hb %s" x="%d" y="%.1f" width="%.1f" height="%.1f" rx="3"/>' % (cls, pad_l, y + 4, max(w, 1), row_h - 9))
        out.append('<text class="hv" x="%.1f" y="%.1f">%s</text>' % (pad_l + w + 6, y + row_h * 0.62, escape(extra)))
    out.append("</svg>")
    return "".join(out)
