// Higher or Lower: pick the company that raised more. The deck is real raises from recent SEC Form D filings.
(function () {
  "use strict";
  var root = document.getElementById("game");
  var deck = [], order = [], pos = 0, streak = 0, best = 0, current = null, challenger = null;

  function money(v) {
    if (v >= 1e9) return "$" + (v / 1e9).toFixed(2).replace(/\.00$/, "") + "B";
    if (v >= 1e6) return "$" + (v >= 1e8 ? Math.round(v / 1e6) : (v / 1e6).toFixed(1).replace(/\.0$/, "")) + "M";
    return "$" + Math.round(v / 1e3) + "K";
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function readBest() { try { return parseInt(localStorage.getItem("sb-best") || "0", 10) || 0; } catch (e) { return 0; } }
  function saveBest(v) { try { localStorage.setItem("sb-best", String(v)); } catch (e) { /* private mode */ } }

  // Pairs with very different amounts make the game trivial; draw challengers within about 10x of the current card.
  function next() {
    for (var tries = 0; tries < 200; tries++) {
      pos = (pos + 1) % order.length;
      var c = deck[order[pos]];
      var r = c.amount / current.amount;
      if (c !== current && c.amount !== current.amount && r > 0.1 && r < 10) return c;
    }
    return deck[order[(pos + 1) % order.length]];
  }
  function shuffle(n) {
    var a = [];
    for (var i = 0; i < n; i++) a.push(i);
    for (var j = n - 1; j > 0; j--) { var k = Math.floor(Math.random() * (j + 1)); var t = a[j]; a[j] = a[k]; a[k] = t; }
    return a;
  }

  function card(c, side, reveal) {
    return '<button type="button" class="gcard" data-side="' + side + '"><span class="gn">' + esc(c.name) + '</span><span class="gm">' +
      esc(c.league) + " · " + esc(c.state) + " · filed " + esc(c.date) + '</span><span class="ga">' + (reveal ? money(c.amount) : "?") + "</span></button>";
  }

  function render(msg) {
    root.innerHTML = '<p class="gscore">Streak <b>' + streak + "</b> · best " + best + "</p>" +
      '<p>Which company raised more?</p><div class="cards2">' + card(current, "a", false) + card(challenger, "b", false) + "</div>" +
      (msg ? '<p class="fine">' + msg + "</p>" : "");
  }

  function pick(side) {
    var a = current, b = challenger;
    var chosen = side === "a" ? a : b, other = side === "a" ? b : a;
    var right = chosen.amount > other.amount;
    var cards = root.querySelectorAll(".gcard");
    cards[0].querySelector(".ga").textContent = money(a.amount);
    cards[1].querySelector(".ga").textContent = money(b.amount);
    cards.forEach(function (el) { el.disabled = true; });
    cards[side === "a" ? 0 : 1].classList.add(right ? "win" : "lose");
    if (window.sbTrack) window.sbTrack("game_pick", right ? "right" : "wrong");
    if (right) {
      streak++;
      if (streak > best) { best = streak; saveBest(best); }
      setTimeout(function () { current = chosen; challenger = next(); render("Right. Keep going."); }, 1100);
    } else {
      var text = "I got a streak of " + streak + " on Higher or Lower, the startup funding game built on SEC Form D filings.";
      var url = location.href.split("#")[0];
      root.insertAdjacentHTML("beforeend", '<p class="gscore">Game over. Streak <b>' + streak + '</b>.</p><p>' +
        '<button type="button" class="btn" id="again">Play again</button> ' +
        '<a class="btn ghost" target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?text=' + encodeURIComponent(text) +
        "&url=" + encodeURIComponent(url) + '">Share your streak</a></p>');
      document.getElementById("again").addEventListener("click", start);
      if (window.sbTrack) window.sbTrack("game_over", String(streak));
    }
  }

  function start() {
    streak = 0;
    order = shuffle(deck.length);
    pos = 0;
    current = deck[order[0]];
    challenger = next();
    render("");
  }

  root.addEventListener("click", function (ev) {
    var b = ev.target.closest ? ev.target.closest(".gcard") : null;
    if (b && !b.disabled) pick(b.getAttribute("data-side"));
  });

  best = readBest();
  fetch("../data/game.json").then(function (r) { return r.json(); }).then(function (d) {
    deck = d.deck || [];
    if (deck.length < 4) { root.innerHTML = '<p class="fine">Not enough raises to play this week.</p>'; return; }
    start();
  }).catch(function () { root.innerHTML = '<p class="fine">Could not load the deck. Try again in a moment.</p>'; });
})();
