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

/* ---------- utils ---------- */
function shuffle(a) { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function buildDeck() { const d = deckPool(); return shuffleOn ? shuffle(d) : d.slice(); }
function imgEl(src) { const w = document.createElement("div"); w.className = "imgwrap"; const im = new Image(); im.src = src; im.alt = ""; w.appendChild(im); return w; }
function backInto(container, card) {
  container.innerHTML = "";
  if (card.back) { const im = new Image(); im.src = card.back; im.alt = ""; container.appendChild(im); }
  else { const d = document.createElement("div"); d.className = "noback"; d.textContent = "Pas de preuve dans le cours pour ce résultat."; container.appendChild(d); }
}
function show(id) { $$(".screen").forEach(s => s.classList.remove("active")); $("#" + id).classList.add("active"); window.scrollTo(0, 0); }

/* ---------- HOME wiring ---------- */
buildChips($("#cours-cats"), COURS_CATS);
buildChips($("#exo-cats"), EXO_CATS);
refreshChips();
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
$("#go-learn").onclick = () => { if (guard()) startLearn(); };
$("#go-review").onclick = () => { if (guard()) startReview(); };
$("#go-test").onclick = () => { if (guard()) startTest(); };

/* ====================== LEARN ====================== */
let L = { deck: [], i: 0, rev: false };
function startLearn() { L = { deck: buildDeck(), i: 0, rev: false }; renderLearn(); show("learn"); }
function renderLearn() {
  const c = L.deck[L.i];
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
function startReview() { const d = buildDeck(); R = { queue: d, total: d.length, done: 0, rev: false }; $("#review-done").classList.add("hidden"); renderReview(); show("review"); }
function renderReview() {
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
  const max = deckPool().length;
  $("#test-max").textContent = max;
  const ni = $("#test-n"); ni.max = max; if (+ni.value > max || +ni.value < 1) ni.value = Math.min(5, max);
  $("#test-setup").classList.remove("hidden");
  $("#test-run").classList.add("hidden");
  show("test");
}
$("#test-start").onclick = () => {
  const max = deckPool().length;
  let n = Math.max(1, Math.min(max, parseInt($("#test-n").value || "1", 10)));
  T.cards = shuffle(deckPool()).slice(0, n);
  renderTestRun();
  $("#test-setup").classList.add("hidden");
  $("#test-run").classList.remove("hidden");
};
$("#test-again").onclick = startTest;
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
