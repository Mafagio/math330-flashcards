"use strict";
const CARDS = window.CARDS || [];
const COURS_CATS = window.COURS_CATS || [];
const EXO_CATS = window.EXO_CATS || [];
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------- selection (persisted) ---------- */
const ALL_KEYS = [...COURS_CATS, ...EXO_CATS].map(c => c.key);
let selected = new Set();
try {
  const saved = JSON.parse(localStorage.getItem("m330sel") || "null");
  if (Array.isArray(saved) && saved.length) selected = new Set(saved.filter(k => ALL_KEYS.includes(k)));
} catch (e) {}
if (!selected.size) selected = new Set(ALL_KEYS); // default: everything
let shuffleOn = true;

function saveSel() { localStorage.setItem("m330sel", JSON.stringify([...selected])); }

function buildChips(container, cats) {
  container.innerHTML = "";
  cats.forEach(c => {
    const el = document.createElement("div");
    el.className = "chip" + (selected.has(c.key) ? " on" : "");
    el.dataset.key = c.key;
    el.innerHTML = `<span>${c.label}</span><span class="cnt">${c.count}</span>`;
    el.title = c.title || "";
    el.onclick = () => { selected.has(c.key) ? selected.delete(c.key) : selected.add(c.key); refreshChips(); };
    container.appendChild(el);
  });
}
function refreshChips() {
  $$(".chip").forEach(el => el.classList.toggle("on", selected.has(el.dataset.key)));
  const n = deckPool().length;
  $("#selinfo").textContent = `${selected.size} catégorie(s) — ${n} carte(s) sélectionnée(s).`;
  saveSel();
}
function deckPool() { return CARDS.filter(c => selected.has(c.cat)); }
function deckLabel(keys) {
  const k = [...keys];
  const coursKeys = COURS_CATS.map(c => c.key), exoKeys = EXO_CATS.map(c => c.key);
  const hasCours = k.some(x => coursKeys.includes(x)), hasExo = k.some(x => exoKeys.includes(x));
  const allCours = coursKeys.every(x => k.includes(x)), allExo = exoKeys.every(x => k.includes(x));
  if (allCours && allExo) return "Tout";
  if (allCours && !hasExo) return "Tout le cours";
  if (allExo && !hasCours) return "Tous les exercices";
  const labels = [...COURS_CATS, ...EXO_CATS].filter(c => k.includes(c.key)).map(c => c.label);
  if (!labels.length) return "—";
  return labels.length <= 4 ? labels.join(", ") : labels.slice(0, 4).join(", ") + ` +${labels.length - 4}`;
}

/* ---------- utils ---------- */
function shuffle(a) { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function buildDeck() { const d = deckPool(); return shuffleOn ? shuffle(d) : d.slice(); }
function imgEl(src) { const w = document.createElement("div"); w.className = "imgwrap"; const im = new Image(); im.src = src; im.alt = ""; w.appendChild(im); return w; }
function backInto(container, card) {
  container.innerHTML = "";
  if (card.back) { const im = new Image(); im.src = card.back; im.alt = ""; container.appendChild(im); }
  else { const d = document.createElement("div"); d.className = "noback"; d.textContent = "Pas de preuve dans le cours pour ce résultat."; container.appendChild(d); }
}
function show(id) { $$(".screen").forEach(s => s.classList.remove("active")); $("#" + id).classList.add("active"); window.scrollTo(0, 0); if (id === "home") renderHomeResume(); }

/* ---------- session persistence (reprendre plus tard) ---------- */
const CARD_BY_ID = Object.fromEntries(CARDS.map(c => [c.id, c]));
const idsOf = a => (a || []).map(c => c.id);
const fromIds = a => (a || []).map(id => CARD_BY_ID[id]).filter(Boolean);
const LS = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  del(k) { localStorage.removeItem(k); }
};
const KEY = { learn: "m330_learn", review: "m330_review", test: "m330_test" };
function showBanner(mode, text, btnLabel, onReset) {
  const el = $("#" + mode + "-banner"); el.innerHTML = "";
  const span = document.createElement("span"); span.textContent = text;
  const btn = document.createElement("button"); btn.className = "ghost"; btn.textContent = btnLabel; btn.onclick = onReset;
  el.appendChild(span); el.appendChild(btn); el.classList.remove("hidden");
}
function hideBanner(mode) { $("#" + mode + "-banner").classList.add("hidden"); }
function renderHomeResume() {
  const s = LS.get(KEY.review);
  const el = $("#home-resume");
  if (!el) return;
  if (s && s.queue && s.queue.length) {
    const remaining = s.queue.length, total = s.total || remaining;
    $("#home-resume-info").textContent = `Deck : ${s.label || "—"} · il te reste ${remaining} carte(s) sur ${total}.`;
    $("#home-resume-btn").textContent = `Continuer (${remaining}/${total})`;
    el.classList.remove("hidden");
  } else { el.classList.add("hidden"); }
}

/* ---------- HOME wiring ---------- */
buildChips($("#cours-cats"), COURS_CATS);
buildChips($("#exo-cats"), EXO_CATS);
refreshChips();
renderHomeResume();
$("#home-resume-btn").onclick = () => enterReview();
$("#home-resume-drop").onclick = () => { LS.del(KEY.review); renderHomeResume(); };
$$("[data-pick]").forEach(a => a.onclick = e => { e.preventDefault(); const g = a.dataset.pick; (g === "cours" ? COURS_CATS : EXO_CATS).forEach(c => selected.add(c.key)); refreshChips(); });
$$("[data-clear]").forEach(a => a.onclick = e => { e.preventDefault(); const g = a.dataset.clear; (g === "cours" ? COURS_CATS : EXO_CATS).forEach(c => selected.delete(c.key)); refreshChips(); });
$("#pick-all").onclick = () => { selected = new Set(ALL_KEYS); refreshChips(); };
$("#pick-none").onclick = () => { selected.clear(); refreshChips(); };
$("#shuffle").onchange = e => shuffleOn = e.target.checked;
$$(".back").forEach(b => b.onclick = () => show("home"));

function guard() {
  if (!deckPool().length) { alert("Sélectionne au moins une catégorie de cartes."); return false; }
  shuffleOn = $("#shuffle").checked;
  return true;
}
$("#go-learn").onclick = () => { if (guard()) enterLearn(); };
$("#go-review").onclick = () => { if (guard()) enterReview(); };
$("#go-test").onclick = () => { if (guard()) enterTest(); };

/* ====================== LEARN ====================== */
let L = { deck: [], i: 0, rev: false };
function saveLearn() { if (L.deck && L.deck.length) LS.set(KEY.learn, { order: idsOf(L.deck), i: L.i }); }
function startLearn() { hideBanner("learn"); L = { deck: buildDeck(), i: 0, rev: false }; renderLearn(); show("learn"); }
function enterLearn() {
  const s = LS.get(KEY.learn);
  if (s && s.order && s.order.length && fromIds(s.order).length) {
    L = { deck: fromIds(s.order), i: Math.min(s.i || 0, s.order.length - 1), rev: false };
    renderLearn(); show("learn");
    showBanner("learn", "Reprise de ta session d'apprentissage (position mémorisée).", "Recommencer",
      () => { LS.del(KEY.learn); startLearn(); });
  } else { startLearn(); }
}
function renderLearn() {
  const c = L.deck[L.i];
  saveLearn();
  $("#learn-counter").textContent = `${L.i + 1} / ${L.deck.length}`;
  $("#learn-label").textContent = c.label;
  $("#learn-front").replaceWith(Object.assign(imgEl(c.front), { id: "learn-front" }));
  const bw = $("#learn-backwrap");
  if (L.rev) {
    bw.classList.remove("hidden");
    backInto($("#learn-back"), c);
    $("#learn-reveal").textContent = "Masquer la réponse";
  } else {
    bw.classList.add("hidden");
    $("#learn-reveal").textContent = "Afficher la réponse";
  }
}
$("#learn-reveal").onclick = () => { L.rev = !L.rev; renderLearn(); };
$("#learn-prev").onclick = () => { L.i = (L.i - 1 + L.deck.length) % L.deck.length; L.rev = false; renderLearn(); };
$("#learn-next").onclick = () => { L.i = (L.i + 1) % L.deck.length; L.rev = false; renderLearn(); };

/* ====================== REVIEW ====================== */
let R = { queue: [], total: 0, done: 0, rev: false };
function saveReview() { if (R.queue && R.queue.length) LS.set(KEY.review, { queue: idsOf(R.queue), done: R.done, total: R.total, label: R.label }); else LS.del(KEY.review); }
function startReview() { hideBanner("review"); const d = buildDeck(); R = { queue: d, total: d.length, done: 0, label: deckLabel(selected), rev: false }; $("#review-done").classList.add("hidden"); saveReview(); renderReview(); show("review"); }
function enterReview() {
  const s = LS.get(KEY.review);
  if (s && s.queue && fromIds(s.queue).length) {
    R = { queue: fromIds(s.queue), total: s.total || s.queue.length, done: s.done || 0, label: s.label || "", rev: false };
    $("#review-done").classList.add("hidden"); renderReview(); show("review");
    showBanner("review", "Reprise de ta session de révision (progression mémorisée).", "Recommencer",
      () => { LS.del(KEY.review); startReview(); });
  } else { startReview(); }
}
function renderReview() {
  saveReview();
  if (!R.queue.length) {
    $("#review-done").classList.remove("hidden");
    $("#review-reveal-ctrl").classList.add("hidden");
    $("#review-grade-ctrl").classList.add("hidden");
    $(".cardbox", $("#review")).classList.add("hidden");
    $("#review-bar").style.width = "100%";
    $("#review-progress").textContent = `${R.total} / ${R.total}`;
    return;
  }
  $(".cardbox", $("#review")).classList.remove("hidden");
  const c = R.queue[0];
  R.rev = false;
  $("#review-label").textContent = c.label;
  $("#review-front").replaceWith(Object.assign(imgEl(c.front), { id: "review-front" }));
  $("#review-backwrap").classList.add("hidden");
  $("#review-reveal-ctrl").classList.remove("hidden");
  $("#review-grade-ctrl").classList.add("hidden");
  $("#review-progress").textContent = `Réussies ${R.done}/${R.total} · restantes ${R.queue.length}`;
  $("#review-bar").style.width = (R.total ? (R.done / R.total * 100) : 0) + "%";
}
function revealReview() {
  if (!R.queue.length || R.rev) return;
  R.rev = true;
  backInto($("#review-back"), R.queue[0]);
  $("#review-backwrap").classList.remove("hidden");
  $("#review-reveal-ctrl").classList.add("hidden");
  $("#review-grade-ctrl").classList.remove("hidden");
}
$("#review-reveal").onclick = revealReview;
$("#review-yes").onclick = () => { if (!R.rev) return; R.queue.shift(); R.done++; renderReview(); };
$("#review-no").onclick = () => { if (!R.rev) return; const c = R.queue.shift(); R.queue.push(c); renderReview(); };
$("#review-restart").onclick = startReview;

/* ====================== TEST ====================== */
let T = { cards: [] };
function startTest() {
  hideBanner("test");
  const max = deckPool().length;
  $("#test-max").textContent = max;
  const ni = $("#test-n"); ni.max = max; if (+ni.value > max || +ni.value < 1) ni.value = Math.min(5, max);
  $("#test-setup").classList.remove("hidden");
  $("#test-run").classList.add("hidden");
  show("test");
}
function enterTest() {
  const s = LS.get(KEY.test);
  if (s && s.ids && fromIds(s.ids).length) {
    T = { cards: fromIds(s.ids) };
    $("#test-max").textContent = deckPool().length;
    renderTestRun();
    $("#test-setup").classList.add("hidden");
    $("#test-run").classList.remove("hidden");
    show("test");
    showBanner("test", `Reprise — test de ${T.cards.length} carte(s) en cours.`, "Nouveau test",
      () => { LS.del(KEY.test); startTest(); });
  } else { startTest(); }
}
$("#test-start").onclick = () => {
  const max = deckPool().length;
  let n = Math.max(1, Math.min(max, parseInt($("#test-n").value || "1", 10)));
  T.cards = shuffle(deckPool()).slice(0, n);
  LS.set(KEY.test, { ids: idsOf(T.cards) });
  renderTestRun();
  $("#test-setup").classList.add("hidden");
  $("#test-run").classList.remove("hidden");
};
$("#test-again").onclick = () => { LS.del(KEY.test); startTest(); };
function renderTestRun() {
  const wrap = $("#test-cards"); wrap.innerHTML = "";
  $("#test-showsol").checked = false;
  T.cards.forEach((c, k) => {
    const div = document.createElement("div");
    div.className = "testcard";
    div.innerHTML = `<div><span class="qnum">Q${k + 1}</span> — <span class="qlabel">${c.label}</span> <span class="muted small">(${c.sub})</span></div>`;
    div.appendChild(imgEl(c.front));
    const sol = document.createElement("div");
    sol.className = "sol hidden";
    sol.dataset.sol = "1";
    sol.innerHTML = `<div class="side-head answer">Solution</div>`;
    if (c.back) sol.appendChild(imgEl(c.back));
    else { const d = document.createElement("div"); d.className = "noback"; d.textContent = "Pas de corrigé/preuve dans le document."; sol.appendChild(d); }
    div.appendChild(sol);
    wrap.appendChild(div);
  });
}
$("#test-showsol").onchange = e => { $$(".sol", $("#test-cards")).forEach(s => s.classList.toggle("hidden", !e.target.checked)); };
$("#test-copy").onclick = async () => {
  const lines = T.cards.map((c, k) => `Q${k + 1} — [${c.sub}] ${c.label}\nMa réponse : \n`);
  const txt =
`Corrige mon test (barème fédéral, note sur 6). Voici les ${T.cards.length} carte(s) tirées et mes réponses :

${lines.join("\n")}
Donne-moi la note /6 et un retour court par question.`;
  try { await navigator.clipboard.writeText(txt); $("#copyok").textContent = "Copié ! Colle-le dans le chat avec Claude."; }
  catch (e) {
    const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); $("#copyok").textContent = "Copié ! Colle-le dans le chat."; } catch (_) { $("#copyok").textContent = "Copie auto impossible — sélectionne le texte manuellement."; }
    ta.remove();
  }
};

/* ====================== keyboard ====================== */
document.addEventListener("keydown", e => {
  const active = $(".screen.active").id;
  if (active === "learn") {
    if (e.code === "Space") { e.preventDefault(); L.rev = !L.rev; renderLearn(); }
    else if (e.key === "ArrowRight") $("#learn-next").click();
    else if (e.key === "ArrowLeft") $("#learn-prev").click();
  } else if (active === "review") {
    if (e.code === "Space") { e.preventDefault(); revealReview(); }
    else if (R.rev && (e.key === "2")) $("#review-yes").click();
    else if (R.rev && (e.key === "1")) $("#review-no").click();
  }
});
