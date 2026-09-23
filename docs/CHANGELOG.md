# Versions

## 0.3.9 — 23 septembre 2026

- Un seul guide d’architecture, sans collision de casse sous Windows.
- Chemins et bilan de validation actualisés.
- Deux adaptateurs MCP d’agents natifs inutilisés retirés de cette édition,
  avec le test spécifique de leur navigateur (203 tests conservés).
- Le packaging refuse les noms de fichiers qui ne diffèrent que par la casse.

## 0.3.8 — 23 septembre 2026

Première distribution publique sur GitHub, issue de l’édition Docker 0.3.7.

- Installation personnelle Docker, français/anglais, fournisseurs IA configurables.
- Recherche par pays et métier, profil, opportunités, documents et courriers.
- Listes paginées, vues complètes et conservation des brouillons.
- Instructions d’activation corrigées : source configurée requise.
- Dépendances de test sorties de l’image d’exécution.
- Tests navigateur compatibles avec Chromium fourni par Playwright.
- Contrôles CI et construction Docker depuis les sources distribuées.

Les appels externes des tests sont simulés. Aucun appel payant ni envoi réel
n’a été effectué pour préparer cette publication. Voir search-sources.md et
EXPLOITATION.md pour les limites.
