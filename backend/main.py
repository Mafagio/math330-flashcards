"""
main.py — API Battle (FastAPI).

Démarrage local :  uvicorn main:app --reload
Auth : chaque requête envoie les en-têtes  X-User  et  X-Pass.
"""

from __future__ import annotations
import os, json, random
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db as DB
import scoring as S
from grader import grade

app = FastAPI(title="Flashcards Battle")

origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    DB.init_db()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def current_user(x_user: str = Header(None), x_pass: str = Header(None)):
    if not x_user or not x_pass:
        raise HTTPException(401, "Identifiants manquants (X-User / X-Pass).")
    row = DB.get_db().execute("SELECT * FROM users WHERE name=?", (x_user,)).fetchone()
    if not row or not DB.verify_pass(x_pass, row["pass_hash"]):
        raise HTTPException(401, "Identifiants invalides.")
    return row


def other_user(uid: int):
    return DB.get_db().execute("SELECT * FROM users WHERE id!=?", (uid,)).fetchone()


# ---------------------------------------------------------------------------
# XP / jetons (helper central)
# ---------------------------------------------------------------------------

def apply_xp(db, user_id: int, delta: float) -> tuple[float, int, int]:
    row = db.execute("SELECT id,name,xp,tokens,xp_milestone FROM users WHERE id=?", (user_id,)).fetchone()
    new_xp = round(row["xp"] + delta, 2)
    granted, new_ms = S.tokens_for_xp(row["xp_milestone"], new_xp)
    new_tokens = row["tokens"] + granted
    db.execute("UPDATE users SET xp=?, tokens=?, xp_milestone=? WHERE id=?",
               (new_xp, new_tokens, new_ms, user_id))
    if granted > 0:
        DB.log_event(db, user_id, "token",
                     f'🪙 {row["name"]} gagne {granted} jeton(s) challenge ({int(new_xp)} XP) !')
    return new_xp, new_tokens, granted


def weighted_sample(items, weights, k):
    items, weights, chosen = list(items), list(weights), []
    for _ in range(min(k, len(items))):
        total = sum(weights)
        r = random.uniform(0, total)
        upto = 0.0
        for i, w in enumerate(weights):
            upto += w
            if upto >= r:
                chosen.append(items.pop(i)); weights.pop(i); break
    return chosen


# ---------------------------------------------------------------------------
# Comptes
# ---------------------------------------------------------------------------

class Creds(BaseModel):
    name: str
    passphrase: str


@app.post("/signup")
def signup(c: Creds):
    db = DB.get_db()
    with DB.LOCK:
        if db.execute("SELECT 1 FROM users WHERE name=?", (c.name,)).fetchone():
            raise HTTPException(400, "Ce nom existe déjà.")
        db.execute("INSERT INTO users(name, pass_hash) VALUES (?,?)",
                   (c.name, DB.hash_pass(c.passphrase)))
        DB.log_event(db, None, "join", f"👋 {c.name} rejoint la Battle.")
        db.commit()
    return {"ok": True, "name": c.name}


@app.post("/login")
def login(c: Creds):
    row = DB.get_db().execute("SELECT * FROM users WHERE name=?", (c.name,)).fetchone()
    if not row or not DB.verify_pass(c.passphrase, row["pass_hash"]):
        raise HTTPException(401, "Identifiants invalides.")
    return {"ok": True, "name": row["name"], "xp": row["xp"], "tokens": row["tokens"]}


def pending_count(db, uid):
    return db.execute("SELECT COUNT(*) c FROM audits WHERE user_id=? AND status='pending'",
                      (uid,)).fetchone()["c"]


@app.get("/me")
def me(u=Depends(current_user)):
    db = DB.get_db()
    return {
        "name": u["name"], "xp": u["xp"], "tokens": u["tokens"],
        "pending_audits": pending_count(db, u["id"]),
        "next_token_in": round(S.TOKEN_EVERY - (u["xp_milestone"] % S.TOKEN_EVERY), 1),
    }


@app.get("/leaderboard")
def leaderboard(u=Depends(current_user)):
    rows = DB.get_db().execute(
        "SELECT name, xp, tokens FROM users ORDER BY xp DESC").fetchall()
    return [{"name": r["name"], "xp": r["xp"], "tokens": r["tokens"],
             "me": r["name"] == u["name"]} for r in rows]


@app.get("/feed")
def feed(u=Depends(current_user)):
    rows = DB.get_db().execute(
        "SELECT text, created_at FROM events ORDER BY id DESC LIMIT 30").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Cartes
# ---------------------------------------------------------------------------

@app.get("/cards")
def cards(course: Optional[str] = None, categories: Optional[str] = None,
          u=Depends(current_user)):
    db = DB.get_db()
    q = "SELECT id, course, category, kind, front, back, difficulty FROM cards"
    args, where = [], []
    if course:
        where.append("course=?"); args.append(course)
    if categories:
        cats = [c.strip() for c in categories.split(",") if c.strip()]
        if cats:
            where.append("category IN (%s)" % ",".join("?" * len(cats))); args += cats
    if where:
        q += " WHERE " + " AND ".join(where)
    return [dict(r) for r in db.execute(q, args).fetchall()]


@app.get("/courses")
def courses(u=Depends(current_user)):
    db = DB.get_db()
    out = {}
    for r in db.execute("SELECT course, category, COUNT(*) c FROM cards GROUP BY course, category"):
        out.setdefault(r["course"], []).append({"category": r["category"], "count": r["c"]})
    return out


# ---------------------------------------------------------------------------
# Progression — vue d'ensemble : niveau de connaissance par carte (rouge->vert)
# ---------------------------------------------------------------------------
# Niveau par carte, d'apres la DERNIERE action de l'utilisateur (review ou audit) :
#   -1 jamais vue (gris) | 0 pas connue / audit rate (rouge) | 1 connue 60% (orange)
#    2 connue 80% (ambre) | 3 connue 95% (vert) | 4 audit reussi (vert valide).
# "connue" (compteur X/total) = niveau >= 1.

@app.get("/progress")
def progress(u=Depends(current_user)):
    db = DB.get_db()
    uid = u["id"]
    # derniere review par carte (ORDER BY id -> la plus recente ecrase ; on garde son created_at)
    rev = {}
    for r in db.execute("SELECT card_id, known, q, created_at FROM reviews WHERE user_id=? ORDER BY id", (uid,)):
        rev[r["card_id"]] = r
    # dernier audit note par carte ; 't' = moment du resultat (graded_at, sinon created_at)
    aud = {}
    for a in db.execute("SELECT card_id, status, COALESCE(graded_at, created_at) AS t FROM audits "
                        "WHERE user_id=? AND status IN ('passed','failed') ORDER BY id", (uid,)):
        aud[a["card_id"]] = a

    def level(cid):
        r = rev.get(cid); a = aud.get(cid)
        # action la plus recente entre review et resultat d'audit, par HORODATAGE
        # (reviews.id et audits.id sont des compteurs separes -> non comparables entre tables).
        # En cas d'egalite a la seconde, la review (action deliberee) l'emporte -> '>' strict.
        if a and (not r or a["t"] > r["created_at"]):
            return 4 if a["status"] == "passed" else 0
        if not r:
            return -1
        if not r["known"]:
            return 0
        q = r["q"] if r["q"] is not None else 0.6   # repli prudent (ne surevalue pas une confiance inconnue)
        return 3 if q >= 0.95 else (2 if q >= 0.8 else 1)

    out = {}
    for c in db.execute("SELECT id, course, category, kind, front FROM cards ORDER BY course, category, id"):
        lv = level(c["id"])
        cat = out.setdefault(c["course"], {}).setdefault(
            c["category"], {"category": c["category"], "total": 0, "known": 0,
                            "levels": {str(k): 0 for k in (-1, 0, 1, 2, 3, 4)}, "cards": []})
        cat["total"] += 1
        if lv >= 1:
            cat["known"] += 1
        cat["levels"][str(lv)] += 1
        front = (c["front"] or "").strip().replace("\n", " ")
        cat["cards"].append({"id": c["id"], "kind": c["kind"], "level": lv,
                             "front": front[:160] + ("…" if len(front) > 160 else "")})
    return {course: list(cats.values()) for course, cats in out.items()}


# ---------------------------------------------------------------------------
# Révision -> déclenche les audits
# ---------------------------------------------------------------------------

class ReviewIn(BaseModel):
    card_id: str
    known: bool
    q: Optional[float] = None     # confiance si known (sinon ignorée)


@app.post("/review")
def review(r: ReviewIn, u=Depends(current_user)):
    db = DB.get_db()
    with DB.LOCK:
        card = db.execute("SELECT * FROM cards WHERE id=?", (r.card_id,)).fetchone()
        if not card:
            raise HTTPException(404, "Carte inconnue.")

        batched, new_audits = False, 0

        if not r.known:
            db.execute("""INSERT INTO reviews(user_id,card_id,known,q,base_points,status)
                          VALUES (?,?,0,NULL,?, 'cleared')""",
                       (u["id"], r.card_id, S.BASE_UNKNOWN))
            apply_xp(db, u["id"], S.BASE_UNKNOWN)
        else:
            q = r.q if r.q in S.CONF_LEVELS else 0.80
            cur = db.execute("INSERT INTO reviews(user_id,card_id,known,q,base_points,status) "
                             "VALUES (?,?,1,?,?, 'provisional')",
                             (u["id"], r.card_id, q, S.BASE_KNOWN))
            apply_xp(db, u["id"], S.BASE_KNOWN)
            db.execute("UPDATE users SET known_since_audit = known_since_audit + 1 WHERE id=?",
                       (u["id"],))

            counter = db.execute("SELECT known_since_audit FROM users WHERE id=?",
                                 (u["id"],)).fetchone()["known_since_audit"]
            if counter >= S.AUDIT_BATCH:
                batched = True
                new_audits = _form_audit_batch(db, u["id"])
                db.execute("UPDATE users SET known_since_audit=0 WHERE id=?", (u["id"],))

        db.commit()
        urow = db.execute("SELECT xp,tokens FROM users WHERE id=?", (u["id"],)).fetchone()
        return {"xp": urow["xp"], "tokens": urow["tokens"],
                "batched": batched, "new_audits": new_audits,
                "pending_audits": pending_count(db, u["id"])}


def _form_audit_batch(db, uid: int) -> int:
    """Tire AUDIT_SAMPLE cartes parmi les AUDIT_BATCH dernières 'provisional'."""
    batch = db.execute(
        "SELECT * FROM reviews WHERE user_id=? AND status='provisional' "
        "ORDER BY id DESC LIMIT ?", (uid, S.AUDIT_BATCH)).fetchall()
    if not batch:
        return 0

    opp = other_user(uid)
    opp_failed = set()
    if opp:
        opp_failed = {x["card_id"] for x in db.execute(
            "SELECT DISTINCT card_id FROM audits WHERE user_id=? AND status='failed'",
            (opp["id"],)).fetchall()}

    items, weights = [], []
    for rv in batch:
        c = db.execute("SELECT difficulty FROM cards WHERE id=?", (rv["card_id"],)).fetchone()
        never = db.execute("SELECT 1 FROM audits WHERE user_id=? AND card_id=? LIMIT 1",
                           (uid, rv["card_id"])).fetchone() is None
        items.append(rv)
        weights.append(S.audit_weight(c["difficulty"], never, rv["card_id"] in opp_failed))

    chosen = weighted_sample(items, weights, S.AUDIT_SAMPLE)
    chosen_ids = {rv["id"] for rv in chosen}

    for rv in batch:
        if rv["id"] in chosen_ids:
            db.execute("INSERT INTO audits(user_id,card_id,review_id,q,source,status) "
                       "VALUES (?,?,?,?, 'audit', 'pending')",
                       (uid, rv["card_id"], rv["id"], rv["q"]))
            db.execute("UPDATE reviews SET status='audit_pending' WHERE id=?", (rv["id"],))
        else:
            db.execute("UPDATE reviews SET status='cleared' WHERE id=?", (rv["id"],))

    name = db.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()["name"]
    DB.log_event(db, uid, "audit",
                 f"🎲 {name} : {len(chosen)} cartes tirées en audit (preuve à faire).")
    return len(chosen)


# ---------------------------------------------------------------------------
# Audits (test écrit + correction)
# ---------------------------------------------------------------------------

@app.get("/audits/pending")
def audits_pending(u=Depends(current_user)):
    db = DB.get_db()
    rows = db.execute("""
        SELECT a.id, a.source, a.q, a.challenger_id, a.duel_id,
               c.front, c.category, c.course, c.kind
        FROM audits a JOIN cards c ON c.id=a.card_id
        WHERE a.user_id=? AND a.status='pending' ORDER BY a.id""", (u["id"],)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if r["challenger_id"]:
            ch = db.execute("SELECT name FROM users WHERE id=?", (r["challenger_id"],)).fetchone()
            d["challenger"] = ch["name"] if ch else None
        out.append(d)
    return out


class AnswerIn(BaseModel):
    answer: str


@app.post("/audits/{audit_id}/answer")
def answer_audit(audit_id: int, a: AnswerIn, u=Depends(current_user)):
    db = DB.get_db()
    with DB.LOCK:
        au = db.execute("SELECT * FROM audits WHERE id=? AND user_id=?",
                        (audit_id, u["id"])).fetchone()
        if not au:
            raise HTTPException(404, "Audit introuvable.")
        if au["status"] != "pending":
            raise HTTPException(400, "Audit déjà corrigé.")
        card = db.execute("SELECT * FROM cards WHERE id=?", (au["card_id"],)).fetchone()
        bareme = json.loads(card["bareme_json"])

        res = grade(card["front"], card["back"], bareme, a.answer)
        outcome = S.outcome_from_score(res["score"])
        mastery = round(S.mastery_points(au["q"], outcome), 2)

        db.execute("""UPDATE audits SET status=?, score=?, justification=?, answer=?,
                      mastery=?, graded_at=datetime('now') WHERE id=?""",
                   ("passed" if outcome else "failed", res["score"], res["justification"],
                    a.answer, mastery, audit_id))
        if au["review_id"]:
            db.execute("UPDATE reviews SET status='cleared' WHERE id=?", (au["review_id"],))

        # Maîtrise (règle propre) appliquée à l'audité. (Duels : q=0.5 -> mastery 0.)
        apply_xp(db, u["id"], mastery)

        verdict = "réussi ✅" if outcome else "raté ❌"
        DB.log_event(db, u["id"], "graded",
                     f'📝 {u["name"]} — {card["category"]} : {res["score"]}/6 ({verdict}, {mastery:+.1f} XP).')

        # Conséquences spécifiques challenge
        if au["source"] == "challenge" and au["challenger_id"]:
            ch = db.execute("SELECT name FROM users WHERE id=?", (au["challenger_id"],)).fetchone()
            if outcome == 0:  # l'adversaire a bluffé : le challenger touche la prime
                apply_xp(db, au["challenger_id"], S.CHALLENGE_BOUNTY)
                DB.log_event(db, au["challenger_id"], "challenge",
                             f'🎯 {ch["name"]} avait raison : challenge gagné (+{S.CHALLENGE_BOUNTY:.0f} XP) !')
            else:             # défense réussie : bonus pour l'audité
                apply_xp(db, u["id"], S.CHALLENGE_DEFENSE)
                DB.log_event(db, u["id"], "challenge",
                             f'🛡️ {u["name"]} défend son point (+{S.CHALLENGE_DEFENSE:.0f} XP).')

        if au["source"] == "duel" and au["duel_id"]:
            _maybe_resolve_duel(db, au["duel_id"])

        db.commit()
        urow = db.execute("SELECT xp,tokens FROM users WHERE id=?", (u["id"],)).fetchone()
        return {
            "score": res["score"], "outcome": outcome, "mastery": mastery,
            "justification": res["justification"], "hits": res.get("hits", []),
            "back": card["back"], "bareme": bareme,
            "xp": urow["xp"], "tokens": urow["tokens"],
            "pending_audits": pending_count(db, u["id"]),
        }


# ---------------------------------------------------------------------------
# Challenge (dépense un jeton)
# ---------------------------------------------------------------------------

class ChallengeIn(BaseModel):
    opponent: str
    card_id: str


@app.post("/challenge")
def challenge(c: ChallengeIn, u=Depends(current_user)):
    db = DB.get_db()
    with DB.LOCK:
        if u["tokens"] < 1:
            raise HTTPException(400, "Pas assez de jetons.")
        opp = db.execute("SELECT * FROM users WHERE name=?", (c.opponent,)).fetchone()
        if not opp or opp["id"] == u["id"]:
            raise HTTPException(400, "Adversaire invalide.")
        rv = db.execute("""SELECT * FROM reviews WHERE user_id=? AND card_id=? AND known=1
                           ORDER BY id DESC LIMIT 1""", (opp["id"], c.card_id)).fetchone()
        if not rv:
            raise HTTPException(400, "Ton pote n'a jamais prétendu connaître cette carte.")
        already = db.execute("""SELECT 1 FROM audits WHERE user_id=? AND card_id=?
                                AND source='challenge' AND status='pending'""",
                             (opp["id"], c.card_id)).fetchone()
        if already:
            raise HTTPException(400, "Challenge déjà en cours sur cette carte.")

        db.execute("UPDATE users SET tokens=tokens-1 WHERE id=?", (u["id"],))
        db.execute("""INSERT INTO audits(user_id,card_id,review_id,q,source,challenger_id,status)
                      VALUES (?,?,?,?, 'challenge', ?, 'pending')""",
                   (opp["id"], c.card_id, rv["id"], rv["q"], u["id"]))
        cat = db.execute("SELECT category FROM cards WHERE id=?", (c.card_id,)).fetchone()["category"]
        DB.log_event(db, u["id"], "challenge",
                     f'⚔️ {u["name"]} défie {opp["name"]} sur {cat} — prouve-le !')
        db.commit()
    return {"ok": True}


@app.get("/opponent/claims")
def opponent_claims(u=Depends(current_user)):
    """Cartes que l'adversaire a marquées 'connue' (cibles de challenge)."""
    db = DB.get_db()
    opp = other_user(u["id"])
    if not opp:
        return []
    rows = db.execute("""
        SELECT c.id, c.category, c.course, c.kind, MAX(r.q) q,
               EXISTS(SELECT 1 FROM audits a WHERE a.user_id=r.user_id AND a.card_id=c.id
                      AND a.status='pending' AND a.source='challenge') AS challenged
        FROM reviews r JOIN cards c ON c.id=r.card_id
        WHERE r.user_id=? AND r.known=1
        GROUP BY c.id ORDER BY q DESC LIMIT 60""", (opp["id"],)).fetchall()
    return [dict(r) | {"opponent": opp["name"]} for r in rows]


# ---------------------------------------------------------------------------
# Duels
# ---------------------------------------------------------------------------

class DuelIn(BaseModel):
    opponent: str
    course: str
    categories: Optional[str] = None


@app.post("/duels")
def create_duel(d: DuelIn, u=Depends(current_user)):
    db = DB.get_db()
    with DB.LOCK:
        opp = db.execute("SELECT * FROM users WHERE name=?", (d.opponent,)).fetchone()
        if not opp or opp["id"] == u["id"]:
            raise HTTPException(400, "Adversaire invalide.")
        args, where = [d.course], ["course=?"]
        if d.categories:
            cats = [x.strip() for x in d.categories.split(",") if x.strip()]
            if cats:
                where.append("category IN (%s)" % ",".join("?" * len(cats))); args += cats
        pool = db.execute("SELECT id FROM cards WHERE " + " AND ".join(where), args).fetchall()
        if len(pool) < S.DUEL_N:
            raise HTTPException(400, f"Pas assez de cartes (il en faut {S.DUEL_N}).")
        chosen = random.sample([p["id"] for p in pool], S.DUEL_N)

        cur = db.execute("INSERT INTO duels(challenger_id,opponent_id,course,n,status) "
                         "VALUES (?,?,?,?, 'open')", (u["id"], opp["id"], d.course, S.DUEL_N))
        duel_id = cur.lastrowid
        for i, cid in enumerate(chosen):
            db.execute("INSERT INTO duel_cards(duel_id,card_id,idx) VALUES (?,?,?)", (duel_id, cid, i))
            for pid in (u["id"], opp["id"]):
                db.execute("""INSERT INTO audits(user_id,card_id,q,source,duel_id,status)
                              VALUES (?,?,0.5,'duel',?, 'pending')""", (pid, cid, duel_id))
        DB.log_event(db, u["id"], "duel",
                     f'🤺 {u["name"]} lance un duel ({S.DUEL_N} cartes, {d.course}) contre {opp["name"]} !')
        db.commit()
    return {"ok": True, "duel_id": duel_id}


def _maybe_resolve_duel(db, duel_id: int):
    duel = db.execute("SELECT * FROM duels WHERE id=?", (duel_id,)).fetchone()
    if not duel or duel["status"] == "done":
        return
    remaining = db.execute("SELECT COUNT(*) c FROM audits WHERE duel_id=? AND status='pending'",
                           (duel_id,)).fetchone()["c"]
    if remaining > 0:
        return
    scores = {}
    for pid in (duel["challenger_id"], duel["opponent_id"]):
        s = db.execute("SELECT COALESCE(SUM(score),0) s FROM audits WHERE duel_id=? AND user_id=?",
                       (duel_id, pid)).fetchone()["s"]
        scores[pid] = s
    a, b = duel["challenger_id"], duel["opponent_id"]
    if scores[a] == scores[b]:
        bonus = (S.DUEL_WIN + S.DUEL_PARTICIPATE) / 2
        apply_xp(db, a, bonus); apply_xp(db, b, bonus); winner = None
    else:
        winner = a if scores[a] > scores[b] else b
        loser = b if winner == a else a
        apply_xp(db, winner, S.DUEL_WIN); apply_xp(db, loser, S.DUEL_PARTICIPATE)
    db.execute("UPDATE duels SET status='done', winner_id=? WHERE id=?", (winner, duel_id))
    names = {r["id"]: r["name"] for r in db.execute("SELECT id,name FROM users")}
    txt = (f'🏆 Duel terminé : {names.get(winner)} gagne '
           f'({scores[a]}–{scores[b]}).' if winner else
           f'🤝 Duel nul ({scores[a]}–{scores[b]}).')
    DB.log_event(db, winner, "duel", txt)


@app.get("/duels")
def list_duels(u=Depends(current_user)):
    db = DB.get_db()
    rows = db.execute("""SELECT * FROM duels WHERE challenger_id=? OR opponent_id=?
                         ORDER BY id DESC LIMIT 20""", (u["id"], u["id"])).fetchall()
    names = {r["id"]: r["name"] for r in db.execute("SELECT id,name FROM users")}
    out = []
    for d in rows:
        my_remaining = db.execute(
            "SELECT COUNT(*) c FROM audits WHERE duel_id=? AND user_id=? AND status='pending'",
            (d["id"], u["id"])).fetchone()["c"]
        out.append(dict(d) | {
            "challenger": names.get(d["challenger_id"]),
            "opponent": names.get(d["opponent_id"]),
            "winner": names.get(d["winner_id"]),
            "my_remaining": my_remaining,
        })
    return out


# ---------------------------------------------------------------------------
# Calibration (dashboard) — surconfiance / sous-confiance par chapitre
# ---------------------------------------------------------------------------

@app.get("/calibration")
def calibration(u=Depends(current_user)):
    db = DB.get_db()
    rows = db.execute("""
        SELECT c.course, c.category, a.q, a.score
        FROM audits a JOIN cards c ON c.id=a.card_id
        WHERE a.user_id=? AND a.status IN ('passed','failed')""", (u["id"],)).fetchall()
    groups, overall = {}, {"n": 0, "sum_o": 0.0, "sum_q": 0.0, "brier": 0.0}
    for r in rows:
        o = S.outcome_from_score(r["score"])
        key = (r["course"], r["category"])
        g = groups.setdefault(key, {"n": 0, "sum_o": 0.0, "sum_q": 0.0, "brier": 0.0})
        for d in (g, overall):
            d["n"] += 1; d["sum_o"] += o; d["sum_q"] += r["q"]; d["brier"] += (r["q"] - o) ** 2
    out = []
    for (course, cat), g in sorted(groups.items()):
        out.append({
            "course": course, "category": cat, "n": g["n"],
            "accuracy": round(g["sum_o"] / g["n"], 2),
            "mean_confidence": round(g["sum_q"] / g["n"], 2),
            "brier": round(g["brier"] / g["n"], 3),
            "gap": round(g["sum_q"] / g["n"] - g["sum_o"] / g["n"], 2),  # >0 = surconfiant
        })
    ov = None
    if overall["n"]:
        ov = {"n": overall["n"], "accuracy": round(overall["sum_o"] / overall["n"], 2),
              "mean_confidence": round(overall["sum_q"] / overall["n"], 2),
              "brier": round(overall["brier"] / overall["n"], 3),
              "gap": round(overall["sum_q"] / overall["n"] - overall["sum_o"] / overall["n"], 2)}
    return {"by_category": out, "overall": ov}


@app.get("/")
def root():
    return {"ok": True, "service": "flashcards-battle"}
