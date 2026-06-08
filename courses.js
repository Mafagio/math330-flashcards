// Liste des cours affichés sur la page de garde.
// Pour AJOUTER un cours : crée le dossier courses/<id>/ (copie d'un cours existant,
// avec ses propres cards.js + cards/), puis ajoute une entrée ici.
window.COURSES = [
  { id: "math330",  code: "MATH-330", name: "Martingales & Brownian motion", dir: "courses/math330/",  count: 124, available: true },
  { id: "bayesian", code: "",         name: "Bayesian Statistics",          dir: "courses/bayesian/", count: 112, available: true },

  // Placeholder à remplacer par ton prochain cours (mets available:true quand courses/<id>/ est prêt) :
  { id: "cours3", code: "", name: "Cours 3 — à ajouter", dir: "courses/cours3/", count: 0, available: false },
];
