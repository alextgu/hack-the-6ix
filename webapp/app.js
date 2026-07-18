(function () {
  "use strict";

  var POLL_MS = 3000;
  var MOODS = ["happy", "worried", "sick", "dying", "graduated"];

  var tg = (typeof window !== "undefined" && window.Telegram && window.Telegram.WebApp) || null;
  if (tg) {
    try { tg.ready(); tg.expand(); } catch (e) { /* ignore */ }
  }

  var params = new URLSearchParams(window.location.search);
  var startParam = tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param;
  if (startParam && /-cards$/.test(startParam)) {
    location.replace("/cards?group=" +
      encodeURIComponent(decodeStartParam(startParam.replace(/-cards$/, "")) || ""));
    return;
  }
  var groupId = params.get("group") || decodeStartParam(startParam);
  var previewMood = params.get("mood");
  var previewPhys = params.get("physical");
  var previewMent = params.get("mental");

  var captionEl = document.getElementById("caption");
  var weekLabelEl = document.getElementById("week-label");
  var badgeEl = document.getElementById("status-badge");
  var tripStatsEl = document.getElementById("trip-stats");
  var physRow = document.getElementById("bar-physical");
  var mentRow = document.getElementById("bar-mental");

  if (!groupId && !previewMood) {
    captionEl.textContent = "no group id in url — open me from telegram, or add ?group=12345";
    return;
  }

  var lottieContainer = document.getElementById("lottie");
  var stageEl = document.getElementById("stage");
  var currentMood = null;
  var currentAnim = null;
  var reconnecting = false;
  var currentCaption = "";
  var isSpeaking = false; // guards against overlapping playback on rapid clicks

  stageEl.addEventListener("click", function () {
    if (isSpeaking || !currentCaption) return;
    speak(currentCaption);
  });

  loadMood("happy");

  if (previewMood || previewPhys != null || previewMent != null) {
    render({
      pet: {
        mood: previewMood || "happy",
        physical: previewPhys != null ? Number(previewPhys) : 100,
        mental: previewMent != null ? Number(previewMent) : 100,
      },
      sim_week: Number(params.get("week") || 0),
      trip: {
        city: params.get("city") || "Tokyo",
        dates: { start: "2026-04-12", end: "2026-04-19" },
        budget_per_person: 1200,
        group_size: 4,
      },
    });
  } else {
    fetchState();
    setInterval(fetchState, POLL_MS);
  }

  function fetchState() {
    fetch("/api/state/" + encodeURIComponent(groupId), { cache: "no-store" })
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
    currentCaption = deriveCaption(phys, ment, mood);
    captionEl.textContent = currentCaption;
    if (weekLabelEl) weekLabelEl.textContent = "week " + num(state.sim_week, 0);
    renderTripStats(state.trip);

    if (mood !== currentMood) {
      currentMood = mood;
      loadMood(mood);
    }
  }

  function healthColor(val) {
    if (val >= 70) return "#3d9a5f"; // green
    if (val >= 40) return "#e08a2e"; // orange
    return "#d13b2e";               // red
  }

  function setBar(row, val) {
    var inner = row.querySelector(".bar-inner");
    var label = row.querySelector(".bar-val");
    inner.style.width = val + "%";
    inner.style.background = healthColor(val);
    label.textContent = Math.round(val);
  }

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

  function renderTripStats(trip) {
    if (!tripStatsEl) return;
    var bits = [];
    if (trip && trip.city) {
      bits.push(stat("heroicons:map-pin", String(trip.city)));
    }
    if (trip && trip.dates && (trip.dates.start || trip.dates.end)) {
      bits.push(stat(
        "heroicons:calendar-days",
        formatDateRange(trip.dates.start, trip.dates.end)
      ));
    }
    if (trip && trip.budget_per_person != null) {
      bits.push(stat("heroicons:currency-dollar", trip.budget_per_person + "/pp"));
    }
    if (trip && trip.group_size != null) {
      bits.push(stat("heroicons:users", trip.group_size + " people"));
    }
    tripStatsEl.innerHTML = bits.join("");
  }

  function stat(icon, text) {
    return (
      '<span class="ds-stat">' +
        '<iconify-icon icon="' + icon + '" width="14" height="14"></iconify-icon>' +
        '<span>' + esc(text) + "</span>" +
      "</span>"
    );
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
      path: "/webapp/animations/" + mood + ".json",
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

  function speak(text) {
    isSpeaking = true;
    var audio = new Audio("/api/speak?text=" + encodeURIComponent(text));
    audio.addEventListener("ended", function () { isSpeaking = false; });
    audio.addEventListener("error", function () { isSpeaking = false; });
    audio.play().catch(function () { isSpeaking = false; /* autoplay/network failure */ });
  }

  function setReconnecting(on) {
    if (on === reconnecting) return;
    reconnecting = on;
    if (on) badgeEl.classList.add("on");
    else badgeEl.classList.remove("on");
  }

  function decodeStartParam(param) {
    if (!param) return null;
    if (param.charAt(0) === "n") return "-" + param.slice(1);
    if (param.charAt(0) === "p") return param.slice(1);
    return null;
  }

  function num(v, dflt) {
    var n = Number(v);
    return isFinite(n) ? n : dflt;
  }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }
})();
