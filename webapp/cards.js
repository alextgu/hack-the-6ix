/* Tinder-style hotel deck for the trippet Mini App.
 *
 * - Pointer-events drag (mouse + touch), buttons, and ←/→ keys all swipe.
 * - Every interaction is measured and shipped to /api/cards/:group/…:
 *     card_view   impression when a card becomes top of stack
 *     swipe       direction + dwell_ms + pickups + direction_changes +
 *                 max_drag_px + velocity + method (gesture|button|key)
 *     detail_open long-press/photo tap (address peek)
 *     link_out    booking link tap on the winner screen
 * - Polls the view every 2.5s to catch round advances / the group decision;
 *   never resyncs the stack mid-drag.
 */
(function () {
  "use strict";

  var POLL_MS = 2500;
  var SWIPE_MS = 320;

  // ── identity ──────────────────────────────────────────────────────────────
  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) { try { tg.ready(); tg.expand(); } catch (e) {} }

  var params = new URLSearchParams(location.search);
  var groupId = params.get("group") || decodeStartParam(
    tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param
  );
  var tgUser = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;

  function decodeStartParam(param) {
    // Mirrors bot.py's _encode_start_param ('n<n>' -> -n, 'p<n>' -> n),
    // tolerating the '-cards' suffix used by the hotel-deck deep link.
    if (!param) return null;
    param = param.replace(/-cards$/, "");
    if (param.charAt(0) === "n") return "-" + param.slice(1);
    if (param.charAt(0) === "p") return param.slice(1);
    return null;
  }
  var userId = tgUser ? String(tgUser.id) : localId();
  var userName = params.get("name") || (tgUser && tgUser.first_name) || ("guest-" + userId.slice(-4));

  function localId() {
    var id = localStorage.getItem("cards_uid");
    if (!id) { id = "web-" + Math.random().toString(36).slice(2, 10); localStorage.setItem("cards_uid", id); }
    return id;
  }

  // ── dom ───────────────────────────────────────────────────────────────────
  var $ = function (id) { return document.getElementById(id); };
  var stackEl = $("stack"), progressEl = $("progress"), peopleEl = $("people");
  var panels = { loading: $("panel-loading"), waiting: $("panel-waiting"),
                 winner: $("panel-winner"), error: $("panel-error") };

  if (!groupId) { showPanel("error"); $("error-title").textContent = "no group id";
    $("error-line").textContent = "open me from telegram, or add ?group=<chat id>"; return; }

  // ── state ─────────────────────────────────────────────────────────────────
  var queue = [];            // cards I still have to swipe this round
  var view = null;           // last server view
  var round = 0;
  var busy = false;          // swipe animation / post in flight
  var dragging = false;
  var deckOpenSent = false;

  // per-top-card analytics accumulators
  var cardStats = null;
  function resetStats(hotelId) {
    cardStats = { hotel_id: hotelId, top_since: Date.now(), pickups: 0,
                  direction_changes: 0, max_drag_px: 0, last_dx_sign: 0 };
  }

  // ── api ───────────────────────────────────────────────────────────────────
  function api(path) { return "/api/cards/" + encodeURIComponent(groupId) + path; }

  function fetchView() {
    return fetch(api("?user_id=" + encodeURIComponent(userId) +
                     "&name=" + encodeURIComponent(userName)), { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); });
  }

  function postSwipe(hotelId, dir, analytics) {
    return fetch(api("/swipe"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, name: userName, hotel_id: hotelId,
                             direction: dir, analytics: analytics })
    }).then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); });
  }

  function sendEvent(type, hotelId, meta) {
    try {
      var body = JSON.stringify({ user_id: userId, type: type, hotel_id: hotelId || null, meta: meta || {} });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(api("/event"), new Blob([body], { type: "application/json" }));
      } else {
        fetch(api("/event"), { method: "POST", headers: { "Content-Type": "application/json" }, body: body });
      }
    } catch (e) {}
  }

  // ── boot ──────────────────────────────────────────────────────────────────
  showPanel("loading");
  refresh();
  setInterval(function () { if (!dragging && !busy) refresh(); }, POLL_MS);

  function refresh() {
    fetchView().then(function (v) {
      hidePanel("error");
      applyView(v, false);
    }).catch(function () {
      if (!view) { /* still booting */ }
      showPanel("error");
      $("error-title").textContent = "can't reach the server";
      $("error-line").textContent = "retrying…";
    });
  }

  // ── view reconciliation ───────────────────────────────────────────────────
  function applyView(v, fromSwipe) {
    var prevRound = round;
    view = v; round = v.round;
    hidePanel("loading");

    $("basecamp").textContent = v.basecamp;
    $("dates").textContent = formatDateRange(v.checkin, v.checkout);
    $("round-label").textContent = v.status === "decided" ? "decided" :
      "round " + v.round + " · " + v.active_count + " left";
    renderPeople(v.participants);

    if (!deckOpenSent) {
      deckOpenSent = true;
      sendEvent("deck_open", null, { round: v.round, viewport: vp() });
    }

    if (v.status === "decided" && v.winner) { renderWinner(v); return; }

    if (v.you_done) {
      renderWaiting(v);
      return;
    }
    hidePanel("waiting");

    var serverIds = v.cards.map(function (c) { return c.id; });
    var localIds = queue.map(function (c) { return c.id; });
    var changed = serverIds.join("|") !== localIds.join("|");

    if (prevRound && v.round > prevRound) {
      toast("round " + v.round + " — " + v.active_count + " hotel" + (v.active_count > 1 ? "s" : "") + " left. swipe again!");
    }
    if (changed && !dragging) {
      queue = v.cards.slice();
      renderStack();
    }
    updateProgress();
  }

  // ── stack rendering ───────────────────────────────────────────────────────
  function renderStack() {
    stackEl.innerHTML = "";
    var show = queue.slice(0, 3);
    for (var i = show.length - 1; i >= 0; i--) {
      stackEl.appendChild(buildCard(show[i], i));
    }
    var top = stackEl.querySelector(".card.top");
    if (top) attachDrag(top);
    if (queue.length) {
      if (!cardStats || cardStats.hotel_id !== queue[0].id) {
        resetStats(queue[0].id);
        sendEvent("card_view", queue[0].id, { round: round, position: viewedCount() });
      }
    }
    setButtons(!!queue.length);
    updateProgress();
  }

  function viewedCount() { return view ? view.active_count - queue.length + 1 : 1; }

  function buildCard(c, depth) {
    var el = document.createElement("div");
    el.className = "card" + (depth === 0 ? " top" : " behind");
    el.style.transform = "translateY(" + depth * 10 + "px) scale(" + (1 - depth * 0.035) + ")";
    el.style.transition = "transform 250ms ease";
    el.dataset.id = c.id;

    var rating = c.rating != null
      ? String(c.rating) + (c.rating_count ? " (" + c.rating_count + ")" : "")
      : "";
    var perNight = c.price_per_night != null ? "$" + c.price_per_night + "/night" : "";
    var nights = c.nights ? c.nights + " nights" : "";
    el.innerHTML =
      '<div class="photo">' +
        '<img alt="" draggable="false" src="' + escAttr(c.thumbnail || "") + '">' +
        '<div class="noimg"><iconify-icon icon="heroicons:photo" width="64" height="64"></iconify-icon></div>' +
        '<div class="fade"></div>' +
        '<div class="stamp like">LIKE</div>' +
        '<div class="stamp nope">NOPE</div>' +
      '</div>' +
      '<div class="info">' +
        '<div class="name-row">' +
          '<div class="name">' + esc(c.name) + '</div>' +
          '<div class="price">' +
            '<div class="total">$' + c.price_total + '</div>' +
            (perNight
              ? '<div class="per"><iconify-icon icon="heroicons:moon" width="12" height="12"></iconify-icon>' +
                  esc(perNight + (nights ? " · " + nights : "")) + "</div>"
              : "") +
          "</div>" +
        "</div>" +
        '<div class="meta">' +
          (rating
            ? '<span class="tag rating"><iconify-icon icon="heroicons:star" width="12" height="12"></iconify-icon>' +
                esc(rating) + "</span>"
            : "") +
          '<span class="tag type"><iconify-icon icon="heroicons:building-office-2" width="12" height="12"></iconify-icon>' +
            esc(c.type || "Hotel") + "</span>" +
          (c.guests
            ? '<span class="tag guests"><iconify-icon icon="heroicons:user-group" width="12" height="12"></iconify-icon>sleeps ' +
                c.guests + "</span>"
            : "") +
          (c.free_cancellation
            ? '<span class="tag cancel"><iconify-icon icon="heroicons:shield-check" width="12" height="12"></iconify-icon>free cancel</span>'
            : "") +
        "</div>" +
        (c.address
          ? '<div class="addr"><iconify-icon icon="heroicons:map-pin" width="14" height="14"></iconify-icon><span>' +
              esc(c.address) + "</span></div>"
          : "") +
      "</div>";

    var img = el.querySelector("img");
    img.onerror = function () { img.style.display = "none"; el.querySelector(".noimg").style.display = "flex"; };
    if (!c.thumbnail) img.onerror();

    // photo tap = address/details peek (analytics)
    el.querySelector(".photo").addEventListener("click", function () {
      if (depth === 0 && !dragging) sendEvent("detail_open", c.id, { round: round });
    });
    return el;
  }

  // ── drag mechanics ────────────────────────────────────────────────────────
  function attachDrag(el) {
    var startX = 0, startY = 0, dx = 0, dy = 0, t0 = 0, lastX = 0, lastT = 0, vx = 0;
    var active = false;

    el.addEventListener("pointerdown", function (e) {
      if (busy) return;
      active = true; dragging = true;
      startX = lastX = e.clientX; startY = e.clientY;
      t0 = lastT = performance.now();
      dx = dy = vx = 0;
      cardStats.pickups += 1;
      el.setPointerCapture(e.pointerId);
      el.style.transition = "none";
    });

    el.addEventListener("pointermove", function (e) {
      if (!active) return;
      dx = e.clientX - startX; dy = e.clientY - startY;
      var now = performance.now();
      if (now - lastT > 0) vx = (e.clientX - lastX) / (now - lastT);
      lastX = e.clientX; lastT = now;

      var sign = dx > 6 ? 1 : dx < -6 ? -1 : 0;
      if (sign && cardStats.last_dx_sign && sign !== cardStats.last_dx_sign) {
        cardStats.direction_changes += 1;
      }
      if (sign) cardStats.last_dx_sign = sign;
      cardStats.max_drag_px = Math.max(cardStats.max_drag_px, Math.abs(dx));

      el.style.transform = "translate(" + dx + "px," + (dy * 0.4) + "px) rotate(" + (dx * 0.07) + "deg)";
      var p = Math.min(1, Math.abs(dx) / 90);
      el.querySelector(".stamp.like").style.opacity = dx > 0 ? p : 0;
      el.querySelector(".stamp.nope").style.opacity = dx < 0 ? p : 0;
    });

    function release(e) {
      if (!active) return;
      active = false; dragging = false;
      var threshold = Math.min(130, stackEl.clientWidth * 0.35);
      var fling = Math.abs(vx) > 0.65 && Math.abs(dx) > 40;
      if (Math.abs(dx) > threshold || fling) {
        doSwipe(dx > 0 ? "right" : "left", "gesture", Math.abs(vx));
      } else {
        el.style.transition = "transform 250ms ease";
        el.style.transform = "";
        el.querySelector(".stamp.like").style.opacity = 0;
        el.querySelector(".stamp.nope").style.opacity = 0;
      }
    }
    el.addEventListener("pointerup", release);
    el.addEventListener("pointercancel", release);
  }

  // ── swiping ───────────────────────────────────────────────────────────────
  function doSwipe(dir, method, velocity) {
    if (busy || !queue.length) return;
    busy = true;
    var card = queue[0];
    var el = stackEl.querySelector(".card.top");
    var analytics = {
      dwell_ms: Date.now() - cardStats.top_since,
      pickups: cardStats.pickups,
      direction_changes: cardStats.direction_changes,
      max_drag_px: Math.round(cardStats.max_drag_px),
      velocity: velocity ? Math.round(velocity * 100) / 100 : 0,
      method: method,
      round: round,
      viewport: vp()
    };

    if (el) {
      var off = (stackEl.clientWidth || 320) * 1.4 * (dir === "right" ? 1 : -1);
      el.style.transition = "transform " + SWIPE_MS + "ms ease-out, opacity " + SWIPE_MS + "ms";
      el.style.transform = "translate(" + off + "px, -30px) rotate(" + (dir === "right" ? 24 : -24) + "deg)";
      el.style.opacity = "0";
      el.querySelector(".stamp." + (dir === "right" ? "like" : "nope")).style.opacity = 1;
    }

    setTimeout(function () {
      queue.shift();
      renderStack();
    }, SWIPE_MS - 60);

    postSwipe(card.id, dir, analytics).then(function (v) {
      busy = false;
      applyView(v, true);
    }).catch(function () {
      busy = false;
      refresh(); // resync from server truth
    });
  }

  $("btn-like").addEventListener("click", function () { doSwipe("right", "button", 0); });
  $("btn-nope").addEventListener("click", function () { doSwipe("left", "button", 0); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") doSwipe("right", "key", 0);
    if (e.key === "ArrowLeft") doSwipe("left", "key", 0);
  });

  // ── panels ────────────────────────────────────────────────────────────────
  function renderPeople(people) {
    peopleEl.innerHTML = "";
    (people || []).forEach(function (p) {
      var c = document.createElement("span");
      c.className = "chip" + (p.done ? " done" : "");
      c.innerHTML =
        '<iconify-icon icon="heroicons:' + (p.done ? "check-circle" : "user") +
        '" width="12" height="12"></iconify-icon>' + esc(p.name);
      peopleEl.appendChild(c);
    });
  }

  function renderWaiting(v) {
    showPanel("waiting");
    var waitingOn = (v.participants || []).filter(function (p) { return !p.done; })
      .map(function (p) { return p.name; });
    $("waiting-line").textContent = waitingOn.length
      ? "still swiping: " + waitingOn.join(", ")
      : "tallying the round…";
    var tallyEl = $("tally");
    tallyEl.innerHTML = "";
    var maxLikes = Math.max(1, (v.participants || []).length);
    (v.active_cards || []).forEach(function (c) {
      var t = (v.tally || {})[c.id] || { likes: 0 };
      var row = document.createElement("div");
      row.className = "tally-row";
      row.innerHTML =
        '<div class="tally-name">' +
          '<iconify-icon icon="heroicons:heart" width="12" height="12"></iconify-icon>' +
          esc(c.name) + " · " + t.likes + " likes" +
        "</div>" +
        '<div class="tally-bar-outer"><div class="tally-bar" style="width:' +
        Math.round((t.likes / maxLikes) * 100) + '%"></div></div>';
      tallyEl.appendChild(row);
    });
    setButtons(false);
  }

  function renderWinner(v) {
    hidePanel("waiting");
    showPanel("winner");
    var w = v.winner;
    var wc = $("winner-card");
    wc.innerHTML =
      (w.thumbnail ? '<img alt="" src="' + escAttr(w.thumbnail) + '">' : "") +
      '<div class="wbody">' +
        '<div class="wname">' + esc(w.name) + "</div>" +
        '<div class="wmeta">' +
          '<span class="ds-stat"><iconify-icon icon="heroicons:star" width="14" height="14"></iconify-icon>' +
            (w.rating || "–") + "</span>" +
          '<span class="ds-stat"><iconify-icon icon="heroicons:currency-dollar" width="14" height="14"></iconify-icon>' +
            w.price_total + " total</span>" +
          '<span class="ds-stat"><iconify-icon icon="heroicons:calendar-days" width="14" height="14"></iconify-icon>' +
            esc(formatDateRange(v.checkin, v.checkout)) + "</span>" +
        "</div>" +
        (w.address
          ? '<div class="ds-stat"><iconify-icon icon="heroicons:map-pin" width="14" height="14"></iconify-icon>' +
              esc(w.address) + "</div>"
          : "") +
      "</div>";
    var link = $("winner-link");
    link.href = w.url || "#";
    link.onclick = function () { sendEvent("link_out", w.id, { from: "winner_screen" }); };
    $("winner-reason").textContent = v.history && v.history.length
      ? "settled in " + v.history.length + " round" + (v.history.length > 1 ? "s" : "") + " of swiping"
      : "";
  }

  function showPanel(name) { for (var k in panels) panels[k].classList.toggle("on", k === name); }
  function hidePanel(name) { panels[name].classList.remove("on"); }

  var toastTimer = null;
  function toast(msg) {
    var el = $("round-toast");
    el.textContent = msg;
    el.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove("on"); }, 2800);
  }

  function updateProgress() {
    if (!view) return;
    var done = view.active_count - queue.length;
    var label = $("progress-label") || progressEl;
    label.textContent = queue.length
      ? "card " + (done + 1) + " of " + view.active_count + " · swipe → to like, ← to pass"
      : "";
  }

  function setButtons(on) {
    $("btn-like").disabled = !on;
    $("btn-nope").disabled = !on;
  }

  // ── utils ─────────────────────────────────────────────────────────────────
  function vp() { return { w: window.innerWidth, h: window.innerHeight }; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }
  function escAttr(s) { return esc(s); }

  /** "2026-07-18" → "July 18, 2026" (matches Mini App app.js). */
  function formatDate(iso) {
    if (!iso) return "";
    var d = new Date(String(iso).slice(0, 10) + "T12:00:00");
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  }

  function formatDateRange(start, end) {
    if (!start && !end) return "";
    var a = start ? new Date(String(start).slice(0, 10) + "T12:00:00") : null;
    var b = end ? new Date(String(end).slice(0, 10) + "T12:00:00") : null;
    if (a && isNaN(a.getTime())) a = null;
    if (b && isNaN(b.getTime())) b = null;
    if (!a && !b) return "";
    if (a && !b) return formatDate(start);
    if (!a && b) return formatDate(end);

    var sameYear = a.getFullYear() === b.getFullYear();
    var sameMonth = sameYear && a.getMonth() === b.getMonth();
    var months = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December",
    ];

    if (sameMonth) {
      return months[a.getMonth()] + " " + a.getDate() + "–" + b.getDate() + ", " + a.getFullYear();
    }
    if (sameYear) {
      return months[a.getMonth()] + " " + a.getDate() + " → " +
        months[b.getMonth()] + " " + b.getDate() + ", " + a.getFullYear();
    }
    return formatDate(start) + " → " + formatDate(end);
  }
})();
