"""
import_cards.py — charge un fichier JSON de cartes dans la base.

Usage :
    python import_cards.py cards.sample.json
    python import_cards.py mes_vraies_cartes.json

Le JSON est une liste d'objets :
{
  "id": "m330-ch5-01",        # identifiant STABLE et unique
  "course": "MATH-330",
  "category": "Ch. 5",
  "kind": "cours",            # "cours" | "exercice"
  "difficulty": 2,            # 1 | 2 | 3  (optionnel, défaut 2)
  "front": "<énoncé, LaTeX ok>",
  "back":  "<réponse de référence, LaTeX ok>",
  "bareme": { "total": 6, "points": [ {"label": "...", "weight": 2}, ... ] }
}
"""

import sys, json
import db as DB


def main(path: str):
    DB.init_db()
    with open(path, encoding="utf-8") as f:
        cards = json.load(f)
    conn = DB.get_db()
    n = 0
    with DB.LOCK:
        for c in cards:
            bareme_en = c.get("bareme_en")
            conn.execute("""
                INSERT INTO cards(id, course, category, kind, front, back, bareme_json, difficulty,
                                  front_en, back_en, bareme_json_en)
                VALUES (:id,:course,:category,:kind,:front,:back,:bareme,:difficulty,
                        :front_en,:back_en,:bareme_en)
                ON CONFLICT(id) DO UPDATE SET
                    course=excluded.course, category=excluded.category, kind=excluded.kind,
                    front=excluded.front, back=excluded.back,
                    bareme_json=excluded.bareme_json, difficulty=excluded.difficulty,
                    -- COALESCE : ne jamais écraser une traduction existante par un import sans _en
                    front_en=COALESCE(excluded.front_en, cards.front_en),
                    back_en=COALESCE(excluded.back_en, cards.back_en),
                    bareme_json_en=COALESCE(excluded.bareme_json_en, cards.bareme_json_en)
            """, {
                "id": c["id"], "course": c["course"], "category": c["category"],
                "kind": c.get("kind", "cours"), "front": c["front"], "back": c["back"],
                "bareme": json.dumps(c.get("bareme", {"total": 6, "points": []}), ensure_ascii=False),
                "difficulty": int(c.get("difficulty", 2)),
                "front_en": c.get("front_en"), "back_en": c.get("back_en"),
                "bareme_en": json.dumps(bareme_en, ensure_ascii=False) if bareme_en else None,
            })
            n += 1
        conn.commit()
    print(f"{n} cartes importées dans {DB.DB_PATH}.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cards.sample.json")
