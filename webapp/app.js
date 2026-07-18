(function () {
  "use strict";

  var POLL_MS = 3000;
  var MOODS = ["happy", "worried", "sick", "dying", "graduated"];

  var tg = (typeof window !== "undefined" && window.Telegram && window.Telegram.WebApp) || null;
  if (tg) {
    try { tg.ready(); tg.expand(); } catch (e) { /* ignore */ }
    applyTheme(tg.themeParams || {});
  }

  var params = new URLSearchParams(window.location.search);
  var groupId = params.get("group");
  var captionEl = document.getElementById("caption");
  var weekEl = document.getElementById("week");
  var badgeEl = document.getElementById("status-badge");
  var tripEl = document.getElementById("trip-line");
  var physRow = document.getElementById("bar-physical");
  var mentRow = document.getElementById("bar-mental");

  if (!groupId) {
    captionEl.textContent = "no group id in url — open me from telegram, or add ?group=demo-chat";
    return;
  }

  var lottieContainer = document.getElementById("lottie");
  var currentMood = null;
  var currentAnim = null;
  var reconnecting = false;

  loadMood("happy"); // preload a neutral animation so the stage isn't empty
  fetchState();
  setInterval(fetchState, POLL_MS);

  function fetchState() {
    var url = "/api/state/" + encodeURIComponent(groupId);
    fetch(url, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("http " + r.status);
        return r.json();
      })
      .then(function (data) {
        setReconnecting(false);
        render(data);
      })
      .catch(function () {
        setReconnecting(true);
      });
  }

  function render(state) {
    var pet = state && state.pet ? state.pet : {};
    var phys = clamp(num(pet.physical, 0), 0, 100);
    var ment = clamp(num(pet.mental, 0), 0, 100);
    var mood = MOODS.indexOf(pet.mood) >= 0 ? pet.mood : deriveMood(phys, ment);

    setBar(physRow, phys);
    setBar(mentRow, ment);
    captionEl.textContent = deriveCaption(phys, ment, mood);
    weekEl.textContent = "week " + num(state.sim_week, 0);
    tripEl.textContent = deriveTripLine(state.trip);

    if (mood !== currentMood) {
      currentMood = mood;
      loadMood(mood);
    }
  }

  function setBar(row, val) {
    var inner = row.querySelector(".bar-inner");
    var label = row.querySelector(".bar-val");
    inner.style.width = val + "%";
    label.textContent = Math.round(val);
    if (val < 25) inner.style.background = "#ff6b6b";
    else if (val < 50) inner.style.background = "#f0d47a";
    else inner.style.background = ""; // fall back to CSS default
  }

  function loadMood(mood) {
    if (!window.lottie) return;
    if (currentAnim) {
      try { currentAnim.destroy(); } catch (e) { /* ignore */ }
      currentAnim = null;
    }
    lottieContainer.innerHTML = "";
    currentAnim = window.lottie.loadAnimation({
      container: lottieContainer,
      renderer: "svg",
      loop: true,
      autoplay: true,
      path: "/webapp/animations/" + mood + ".json"
    });
  }

  function deriveMood(phys, ment) {
    var avg = (phys + ment) / 2;
    if (avg >= 75) return "happy";
    if (avg >= 50) return "worried";
    if (avg >= 25) return "sick";
    return "dying";
  }

  function deriveCaption(phys, ment, mood) {
    if (mood === "graduated") return "pet has graduated. touch grass, book the flight.";
    if (mood === "dying") return "it's over. the group chat has flatlined.";
    if (phys < 30 && ment < 30) return "prices are killing me AND chat's slowing down";
    if (phys < 30) return "prices are killing me — someone find a cheaper hotel";
    if (ment < 30) return "chat's slowing down… where did everyone go";
    if (phys < 55 && ment < 55) return "kinda vibing, kinda dying, hard to say";
    if (phys > 80 && ment > 80) return "pet is thriving. trip is on.";
    if (ment > 75) return "the group is locked in";
    if (phys > 75) return "wallet is happy today";
    return "just hanging out. keep talking, keep booking.";
  }

  function deriveTripLine(trip) {
    if (!trip) return "";
    var parts = [];
    if (trip.city) parts.push(String(trip.city));
    if (trip.dates && (trip.dates.start || trip.dates.end)) {
      parts.push([trip.dates.start, trip.dates.end].filter(Boolean).join(" → "));
    }
    if (trip.budget_per_person != null) parts.push("$" + trip.budget_per_person + "/pp");
    if (trip.group_size != null) parts.push(trip.group_size + " people");
    return parts.join("  ·  ");
  }

  function setReconnecting(on) {
    if (on === reconnecting) return;
    reconnecting = on;
    if (on) badgeEl.classList.add("on");
    else badgeEl.classList.remove("on");
  }

  function applyTheme(tp) {
    var root = document.documentElement.style;
    if (tp.bg_color) root.setProperty("--bg", tp.bg_color);
    if (tp.secondary_bg_color) root.setProperty("--bg2", tp.secondary_bg_color);
    if (tp.text_color) root.setProperty("--fg", tp.text_color);
    if (tp.hint_color) root.setProperty("--muted", tp.hint_color);
    if (tp.button_color) root.setProperty("--bar-fg-2", tp.button_color);
  }

  function num(v, dflt) {
    var n = Number(v);
    return isFinite(n) ? n : dflt;
  }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
})();
