/* Shared by host.html (big screen) and index.html (players). Plain JavaScript, no build step. */
var WD = (function () {
  "use strict";

  /* ---------- small DOM helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k.slice(0, 2) === "on") e[k] = v;
      else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null || c === false) return;
      e.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
    });
    return e;
  }
  function pick(a) { return a[Math.floor(Math.random() * a.length)]; }
  function shuffle(a) { a = a.slice(); for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /* ---------- defaults, matching the single-iPad game ---------- */
  var DEF_BEHAVIORS = ["Feeding/foraging", "Social", "Travel", "Grooming", "Resting", "Curiosity towards camera", "Fearful towards camera"];
  var DEF_SPECIES = ["Western lowland gorilla", "Chimpanzee", "Forest elephant", "Leopard", "Red river hog", "Duiker", "Monkey", "Bird", "Human", "Other / unsure"];
  var NO_ANIMAL = "No animal visible";

  /* ---------- random player names (players can't type names, so nothing rude reaches the big screen) ---------- */
  var ADJ = ["Swift", "Clever", "Brave", "Quiet", "Curious", "Mighty", "Gentle", "Sneaky", "Bold", "Speedy", "Wise", "Jolly", "Lucky", "Nimble", "Keen", "Calm", "Bright", "Sharp-eyed", "Happy", "Daring"];
  var ANI = ["Leopard", "Gorilla", "Chimpanzee", "Elephant", "Duiker", "Bongo", "Sitatunga", "Pangolin", "Hornbill", "Parrot", "Mongoose", "Genet", "Colobus", "Mangabey", "Red River Hog", "Forest Buffalo", "Golden Cat", "Civet", "Tortoise", "Kingfisher"];
  function randomName(taken) {
    var n;
    for (var i = 0; i < 60; i++) { n = pick(ADJ) + " " + pick(ANI); if (!taken || taken.indexOf(n) < 0) return n; }
    return n + " " + (2 + Math.floor(Math.random() * 98));
  }

  /* ---------- answer tiles: colour + shape, so they're easy to match between the big screen and the phones ---------- */
  var TILES = [
    { color: "#c0473a", shape: "▲", label: "red triangle" },
    { color: "#2f6fb0", shape: "◆", label: "blue diamond" },
    { color: "#c98a00", shape: "●", label: "yellow circle" },
    { color: "#2f7d4f", shape: "■", label: "green square" }
  ];

  /* ---------- scoring (correctness only, user decision 2026-10-16) ---------- */
  var ANIMAL_POINTS = 100, BEHAVIOR_POINTS = 100;
  function inn(a, x) { return a.indexOf(x) > -1; }
  /* Behaviors are scored like the single-iPad game: points × correct picks ÷ (correct picks + wrong picks + missed ones). */
  function scoreBehaviors(chosen, official) {
    chosen = chosen || []; official = official || [];
    var hits = chosen.filter(function (b) { return inn(official, b); });
    var wrong = chosen.filter(function (b) { return !inn(official, b); });
    var missed = official.filter(function (b) { return !inn(chosen, b); });
    var un = hits.length + wrong.length + missed.length;
    var exact = !wrong.length && !missed.length;
    return { pts: exact ? BEHAVIOR_POINTS : Math.round(BEHAVIOR_POINTS * (un ? hits.length / un : 0)), exact: exact, hits: hits, wrong: wrong, missed: missed };
  }

  /* ---------- room codes: 4 letters without look-alikes (no I, O, 0, 1) ---------- */
  var CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  function newRoomCode() { var s = ""; for (var i = 0; i < 4; i++) s += pick(CODE_CHARS.split("")); return s; }
  function cleanCode(s) { return String(s || "").toUpperCase().replace(/[^A-Z]/g, "").slice(0, 4); }

  /* ---------- Firebase ---------- */
  function configured() {
    var c = window.WD_FIREBASE_CONFIG;
    return !!(c && c.apiKey && c.databaseURL && !/PASTE_/.test(c.apiKey + c.databaseURL));
  }
  /* Tests run against the Firebase Local Emulator: only from localhost, and only when the address has ?emu=1. */
  function emulator() {
    var q = new URLSearchParams(location.search);
    if (q.get("emu") !== "1" || !/^(localhost|127\.0\.0\.1)$/.test(location.hostname)) return null;
    var uid = q.get("uid") || sessionStorage.getItem("wd_emu_uid");
    if (!uid) { uid = "u" + Math.random().toString(36).slice(2, 10); }
    sessionStorage.setItem("wd_emu_uid", uid);
    return { host: q.get("emuhost") || "127.0.0.1", port: +(q.get("emuport") || 9000), ns: q.get("ns") || "demo-wd", uid: uid };
  }
  var conn = null;
  function connect() {
    if (conn) return conn;
    var emu = emulator();
    if (!emu && !configured()) return Promise.reject({ code: "not_configured" });
    conn = (async function () {
      if (emu) {
        firebase.initializeApp({ apiKey: "demo-key", projectId: emu.ns, databaseURL: "https://" + emu.ns + ".firebaseio.com" });
        var d = firebase.database();
        d.useEmulator(emu.host, emu.port, { mockUserToken: { sub: emu.uid, user_id: emu.uid } });
        return { db: d, uid: emu.uid };
      }
      firebase.initializeApp(window.WD_FIREBASE_CONFIG);
      var cred = await firebase.auth().signInAnonymously();
      return { db: firebase.database(), uid: cred.user.uid };
    })();
    conn.catch(function () { conn = null; });
    return conn;
  }
  function serverTs() { return firebase.database.ServerValue.TIMESTAMP; }
  /* Watches the connection (green/red dot) and the difference between this device's clock and the server's. */
  function watchConnection(db, onChange) {
    var state = { online: false, offset: 0 };
    db.ref(".info/connected").on("value", function (s) { state.online = !!s.val(); onChange(state); });
    db.ref(".info/serverTimeOffset").on("value", function (s) { state.offset = s.val() || 0; onChange(state); });
    return state;
  }
  function errText(e) {
    if (!e) return "unknown problem";
    if (e.code === "not_configured") return "Firebase isn't set up yet (see README.md, \"Set up Firebase\").";
    if (/PERMISSION_DENIED|permission/i.test(e.code + " " + e.message)) return "the database refused this (check the database rules in README.md)";
    if (/admin-restricted|operation-not-allowed/.test(e.code || "")) return "anonymous sign-in is turned off in Firebase (see README.md, step 4)";
    if (/network/i.test(e.code + " " + e.message)) return "no internet connection";
    return e.message || e.code || String(e);
  }

  /* ---------- the address players open ---------- */
  var DEFAULT_PLAYER_URL = "https://jhzeiglertowey.github.io/wildlife-detectives-live/";
  function playerUrl(base, room, booth) {
    var u = new URL(base || DEFAULT_PLAYER_URL, location.href);
    u.searchParams.set("room", room);
    if (booth) u.searchParams.set("booth", "1");
    var emu = new URLSearchParams(location.search);
    if (emu.get("emu") === "1") { u.searchParams.set("emu", "1"); ["emuhost", "emuport", "ns"].forEach(function (k) { if (emu.get(k)) u.searchParams.set(k, emu.get(k)); }); }
    return u.toString();
  }
  /* QR code as an SVG element (qrcode-generator, error level M). */
  function qrSvg(text, px) {
    var q = qrcode(0, "M"); q.addData(text); q.make();
    var n = q.getModuleCount(), m = 2, size = n + m * 2, d = "";
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) if (q.isDark(r, c)) d += "M" + (c + m) + "," + (r + m) + "h1v1h-1z";
    var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + size + " " + size); svg.setAttribute("width", px); svg.setAttribute("height", px);
    svg.setAttribute("shape-rendering", "crispEdges"); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "QR code for " + text);
    var bg = document.createElementNS(ns, "rect"); bg.setAttribute("width", size); bg.setAttribute("height", size); bg.setAttribute("fill", "#fff");
    var p = document.createElementNS(ns, "path"); p.setAttribute("d", d); p.setAttribute("fill", "#1d2a1f");
    svg.appendChild(bg); svg.appendChild(p);
    return svg;
  }

  var RESEARCH_URL = "https://congo-apes.org/";

  /* ---------- jungle decor: shown on the start and finished screens, like the single-iPad game ---------- */
  function setHdr() { var h = document.querySelector("header"); if (h) document.documentElement.style.setProperty("--hdr", h.offsetHeight + "px"); }
  window.addEventListener("resize", setHdr);
  function decor(on) {
    var j = $("jungle"), m = $("main");
    if (j) j.classList.toggle("hide", !on);
    if (m) m.classList.toggle("decor", !!on);
    setHdr();
  }

  /* ---------- button feedback: press = shrink (CSS), tap = a quick "pop" ----------
     Many taps redraw the screen. If the redraw shows the same screen, the pop is re-applied to the button in the same
     position, so it isn't lost (same approach as the single-iPad game's Settings panel). */
  var popIdx = null, popT = 0;
  var TAPPABLE = "button, .tile, .chip";
  function pop(b) { if (!b) return; b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop"); }
  document.addEventListener("animationend", function (e) { if (e.target.classList && e.animationName === "savedPop") e.target.classList.remove("pop"); });
  document.addEventListener("touchstart", function () {}, { passive: true }); /* lets iPad Safari show the :active press effect */
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(TAPPABLE); if (!b || b.disabled) return;
    var m = $("main");
    popIdx = m && m.contains(b) ? [].indexOf.call(m.querySelectorAll(TAPPABLE), b) : null; popT = Date.now();
    pop(b);
  }, true);
  /* Call at the end of every redraw. sameScreen: the redraw shows the same screen as before. */
  function afterRender(sameScreen) {
    var m = $("main");
    if (sameScreen && popIdx != null && popIdx >= 0 && Date.now() - popT < 1500 && m) pop(m.querySelectorAll(TAPPABLE)[popIdx]);
    popIdx = null;
  }
  function reducedMotion() { return !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches); }

  /* A one-time shower of falling leaves and confetti in jungle colours (finished screens), removed after ~5.5 s. */
  function confetti() {
    if (reducedMotion()) return;
    var c = el("div", { class: "confetti", "aria-hidden": "true" }), cols = ["#2f7d4f", "#4caf68", "#e0a526", "#8bc34a", "#c0473a", "#1f5a36"];
    for (var i = 0; i < 46; i++) {
      var d = el("i", {});
      d.style.left = (Math.random() * 100) + "vw"; d.style.background = pick(cols);
      d.style.animationDuration = (2.6 + Math.random() * 2.2) + "s"; d.style.animationDelay = (Math.random() * .9) + "s";
      d.style.setProperty("--r", (Math.random() < .5 ? "-" : "") + (360 + Math.floor(Math.random() * 360)) + "deg");
      var sz = 8 + Math.random() * 10; d.style.width = sz + "px"; d.style.height = (sz * 1.5) + "px";
      c.appendChild(d);
    }
    document.body.appendChild(c); setTimeout(function () { c.remove(); }, 5500);
  }

  return {
    $: $, el: el, pick: pick, shuffle: shuffle, sleep: sleep, inn: inn,
    DEF_BEHAVIORS: DEF_BEHAVIORS, DEF_SPECIES: DEF_SPECIES, NO_ANIMAL: NO_ANIMAL,
    randomName: randomName, TILES: TILES, ANIMAL_POINTS: ANIMAL_POINTS, BEHAVIOR_POINTS: BEHAVIOR_POINTS, scoreBehaviors: scoreBehaviors,
    newRoomCode: newRoomCode, cleanCode: cleanCode,
    configured: configured, connect: connect, serverTs: serverTs, watchConnection: watchConnection, errText: errText, isEmulator: function () { return !!emulator(); },
    DEFAULT_PLAYER_URL: DEFAULT_PLAYER_URL, playerUrl: playerUrl, qrSvg: qrSvg, RESEARCH_URL: RESEARCH_URL,
    decor: decor, setHdr: setHdr, pop: pop, afterRender: afterRender, confetti: confetti, reducedMotion: reducedMotion
  };
})();
