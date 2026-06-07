# MATH-330 — Flashcards (Martingales & Brownian motion)

Petit site statique (fond blanc, sans dépendance) pour réviser le cours et les exercices
sous forme de cartes (énoncé → réponse).

## Contenu
- **124 cartes** : 52 du cours (théorèmes / lemmes / propositions / corollaires / claims, énoncé + preuve)
  et 72 exercices (énoncé + solution, sans les exercices « additional »).
- Images dans `cards/` ; manifeste dans `cards.js` (généré).

## Trois modes
1. **Apprendre** — parcourir les cartes, afficher la réponse, naviguer.
2. **Réviser** — pour chaque carte : *« je connaissais / pas »*. Les cartes ratées reviennent
   jusqu'à ce que **tout soit réussi une fois**. Case **Mélanger** pour l'ordre aléatoire.
3. **Test** — tire **N cartes au hasard** (N de 1 au total sélectionné). Tu écris tes réponses,
   tu cliques **« Copier pour Claude »**, tu m'envoies le tout → je corrige **sur 6 (barème fédéral)**.

La sélection des catégories (Ch. 1–9 du cours et/ou Séries 1–12 d'exercices, multi-sélection)
s'applique aux trois modes. Le choix est mémorisé dans le navigateur.

## Utiliser en local
Ouvre simplement `index.html` dans un navigateur (le manifeste est en `.js`, donc pas besoin de serveur).

## Mettre sur GitHub Pages
1. Crée un dépôt et pousse le contenu de ce dossier `site/` (y compris `cards/`).
   ```bash
   git init
   git add .
   git commit -m "MATH-330 flashcards"
   git branch -M main
   git remote add origin <URL-de-ton-repo>
   git push -u origin main
   ```
2. Sur GitHub : **Settings → Pages → Build and deployment → Source: Deploy from a branch**,
   branche `main`, dossier `/ (root)`. Le site sera servi sur `https://<user>.github.io/<repo>/`.

> Si tu pousses tout le dossier parent (Cours/, Exercices/, …), configure Pages pour servir
> depuis `/site` plutôt que la racine, ou déplace le contenu de `site/` à la racine du dépôt.

## Raccourcis clavier
- `Espace` : afficher / masquer la réponse
- `←` / `→` : carte précédente / suivante (Apprendre)
- En révision : `1` = pas connue, `2` = connue
