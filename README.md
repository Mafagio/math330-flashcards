# Mes flashcards — hub multi-cours

Site statique (fond blanc, sans dépendance, sans build) regroupant plusieurs cours de
flashcards. La **page de garde** (`index.html`) liste les cours ; chaque cours est une
appli de flashcards autonome dans `courses/<id>/`.

## Structure
```
index.html        ← page de garde (choix du cours)
landing.css
courses.js        ← liste des cours affichés sur la garde
courses/
  math330/        ← un cours = appli complète + ses images
    index.html  style.css  app.js
    cards.js      ← manifeste (window.COURSE + window.CARDS + catégories)
    cards/        ← images (énoncés / preuves / exos / solutions)
```

## Un cours = 3 modes
1. **Apprendre** — parcourir les cartes, afficher la réponse, naviguer.
2. **Réviser** — *« je connaissais / pas »* ; les ratées reviennent jusqu'à tout réussir une
   fois ; case **Mélanger** ; barre de progression.
3. **Test** — N cartes au hasard (1 → total), énoncés seuls ; bouton **« Copier pour Claude »**
   → tu m'envoies tes réponses, je corrige **sur 6 (barème fédéral)**.

Sélection des cartes en **multi-sélection** (chapitres du cours + séries d'exercices),
mémorisée par cours. **Reprise plus tard** : chaque mode sauvegarde sa session ; pour la
révision, un bouton **« Continuer (X/total) »** apparaît sur l'accueil du cours.

> La progression est **isolée par cours** (clés localStorage préfixées par l'`id` du cours,
> ex. `math330_review`), donc les cours ne mélangent pas leurs sauvegardes.

## Ajouter un cours
1. Crée `courses/<nouvel-id>/` (copie d'un cours existant, ou via le pipeline d'extraction).
2. Mets-y son `cards.js` — la 1re ligne doit définir le cours :
   ```js
   window.COURSE = { id: "<nouvel-id>", code: "MATH-XXX", name: "Nom du cours" };
   ```
   (l'`id` sert au préfixe localStorage et au dossier ; le titre s'affiche tout seul).
3. Ajoute une entrée dans `courses.js` :
   ```js
   { id: "<nouvel-id>", code: "MATH-XXX", name: "Nom du cours", dir: "courses/<nouvel-id>/", count: N, available: true },
   ```

## Utiliser en local
Ouvre `index.html` dans un navigateur (manifeste en `.js`, pas besoin de serveur).

## GitHub Pages
Pousse le contenu de `site/` sur le dépôt, puis **Settings → Pages → Deploy from a branch →
`main` / `/ (root)`**. Mises à jour : `git add -A && git commit -m "..." && git push`.

## Raccourcis clavier (dans un cours)
- `Espace` : afficher / masquer la réponse · `←`/`→` : naviguer (Apprendre)
- En révision : `1` = pas connue, `2` = connue
