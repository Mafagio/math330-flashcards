"""
fix_no_audit.py — répare les audits sur les cartes « no_audit » (preuve hors chapitre).

Lancé au démarrage, APRÈS l'import des cartes (qui pose no_audit=1 sur les bonnes cartes).

- Audit RATÉ (source='audit') sur une carte no_audit -> converti en RÉUSSI (score 6) et
  l'XP est RENDUE : on applique le delta (maîtrise réussie - maîtrise ratée) dans la
  compétition du cours de la carte.
- Audit 'audit' EN ATTENTE sur une carte no_audit -> supprimé (on ne le demandera plus),
  et sa review repasse à 'cleared'.

Idempotent : ne touche que les status 'failed'/'pending' -> rejouable sans double effet
(pas besoin de marqueur ; gère aussi d'éventuelles futures cartes no_audit).
"""
import db as DB
import scoring as S


def main():
    DB.init_db()                       # garantit la colonne no_audit + le schéma
    con = DB.get_db()
    with DB.LOCK:
        failed = con.execute("""
            SELECT a.id, a.user_id, a.q, a.mastery, c.course
            FROM audits a JOIN cards c ON c.id = a.card_id
            WHERE a.status='failed' AND a.source='audit' AND c.no_audit=1
        """).fetchall()
        refunded = 0
        for a in failed:
            new_m = round(S.mastery_points(a["q"], 1), 2)          # maîtrise d'un audit réussi
            delta = round(new_m - (a["mastery"] or 0), 2)         # rend la pénalité + crédite la réussite
            sc = con.execute("SELECT xp, xp_milestone, tokens FROM scores WHERE user_id=? AND course=?",
                             (a["user_id"], a["course"])).fetchone()
            if sc:
                new_xp = round(sc["xp"] + delta, 2)
                granted, new_ms = S.tokens_for_xp(sc["xp_milestone"], new_xp)
                con.execute("UPDATE scores SET xp=?, xp_milestone=?, tokens=? WHERE user_id=? AND course=?",
                            (new_xp, new_ms, sc["tokens"] + granted, a["user_id"], a["course"]))
            else:
                con.execute("INSERT INTO scores(user_id, course, xp) VALUES (?,?,?)",
                            (a["user_id"], a["course"], delta))
            con.execute("UPDATE audits SET status='passed', score=6, mastery=? WHERE id=?", (new_m, a["id"]))
            refunded += 1

        pend = con.execute("""
            SELECT a.id, a.review_id FROM audits a JOIN cards c ON c.id = a.card_id
            WHERE a.status='pending' AND a.source='audit' AND c.no_audit=1
        """).fetchall()
        removed = 0
        for a in pend:
            if a["review_id"]:
                con.execute("UPDATE reviews SET status='cleared' WHERE id=?", (a["review_id"],))
            con.execute("DELETE FROM audits WHERE id=?", (a["id"],))
            removed += 1
        con.commit()
    print(f"NO_AUDIT_FIX: {refunded} audit(s) raté(s) remboursé(s), {removed} en attente supprimé(s).")


if __name__ == "__main__":
    main()
