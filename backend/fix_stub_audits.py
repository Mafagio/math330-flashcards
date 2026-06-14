"""
fix_stub_audits.py — répare les audits notés par le correcteur « stub » (mots-clés) au lieu
du vrai correcteur LLM (justification contenant « stub »), et SUPPRIME les notifications
« raté » erronées du fil d'activité.

Pour chaque audit concerné (source='audit') :
  - on RE-CORRIGE la réponse stockée avec le correcteur (réparé) ; s'il répond pour de vrai,
    on ajuste l'XP du score stub vers le vrai score et on met à jour l'audit ;
  - s'il n'y a pas de vrai correcteur (encore stub), on retire la pénalité injuste et on
    remet l'audit en attente.
  - dans les deux cas, on efface l'évènement « raté … XP » correspondant du fil.

Idempotent : après traitement la justification ne contient plus « stub » -> plus re-traité.
"""
import json
import db as DB
import scoring as S
from grader import grade


def _adjust_xp(con, uid, course, delta):
    sc = con.execute("SELECT xp, xp_milestone, tokens FROM scores WHERE user_id=? AND course=?",
                     (uid, course)).fetchone()
    if sc:
        new_xp = round(sc["xp"] + delta, 2)
        granted, new_ms = S.tokens_for_xp(sc["xp_milestone"], new_xp)
        con.execute("UPDATE scores SET xp=?, xp_milestone=?, tokens=? WHERE user_id=? AND course=?",
                    (new_xp, new_ms, sc["tokens"] + granted, uid, course))
    elif delta:
        con.execute("INSERT INTO scores(user_id, course, xp) VALUES (?,?,?)", (uid, course, delta))


def main():
    DB.init_db()
    con = DB.get_db()
    rows = con.execute("""
        SELECT a.id, a.user_id, a.q, a.mastery, a.answer, c.course, c.category,
               c.front, c.back, c.bareme_json
        FROM audits a JOIN cards c ON c.id = a.card_id
        WHERE a.justification LIKE '%stub%'
              AND a.status IN ('passed','failed') AND a.source='audit'
        LIMIT 50
    """).fetchall()

    # 1) re-correction (appels API HORS verrou)
    graded = []
    for a in rows:
        if not (a["answer"] or "").strip():
            graded.append((a, {"stub": True})); continue
        try:
            res = grade(a["front"], a["back"], json.loads(a["bareme_json"]), a["answer"])
        except Exception:
            res = {"stub": True}
        graded.append((a, res))

    # 2) application en base (sous verrou) + nettoyage du fil
    regraded = refunded = events_del = 0
    pairs = set()
    with DB.LOCK:
        for a, res in graded:
            old_gain = round((a["mastery"] or 0) + S.AUDIT_BONUS, 2)   # XP nette qu'avait appliquée le stub
            if res.get("stub"):
                # pas de vrai correcteur -> on enlève la pénalité injuste et on remet en attente
                _adjust_xp(con, a["user_id"], a["course"], -old_gain)
                con.execute("UPDATE audits SET status='pending', score=NULL, justification=NULL, "
                            "mastery=0, graded_at=NULL WHERE id=?", (a["id"],))
                refunded += 1
            else:
                outcome = S.outcome_from_score(res["score"])
                new_mastery = round(S.mastery_points(a["q"], outcome), 2)
                new_gain = round(new_mastery + S.AUDIT_BONUS, 2)
                _adjust_xp(con, a["user_id"], a["course"], round(new_gain - old_gain, 2))
                con.execute("UPDATE audits SET status=?, score=?, justification=?, mastery=? WHERE id=?",
                            ("passed" if outcome else "failed", res["score"],
                             str(res.get("justification", "")), new_mastery, a["id"]))
                regraded += 1
            pairs.add((a["user_id"], a["category"]))

        # 3) supprime les notifications « raté … XP » erronées (par utilisateur+catégorie)
        for uid, cat in pairs:
            cur = con.execute(
                "DELETE FROM events WHERE user_id=? AND type='graded' "
                "AND text LIKE ? AND text LIKE '%raté%'", (uid, f"%— {cat} :%"))
            events_del += cur.rowcount or 0
        con.commit()
    print(f"STUB_AUDIT_FIX: {regraded} re-corrigé(s), {refunded} pénalité(s) retirée(s), "
          f"{events_del} notification(s) erronée(s) supprimée(s).")


if __name__ == "__main__":
    main()
