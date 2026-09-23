# Validation de la distribution publique

Le 23 septembre 2026, la version 0.3.8 a passé 204 tests Python, les contrôles
Ruff, l’architecture UI, Prettier et le build Vite. GitHub Actions a également
construit Docker, vérifié une installation vide et exécuté les parcours navigateur.
[Exécution de référence](https://github.com/Mr-yums/SearchMyJob/actions/runs/35917195656).

Les parcours navigateur couvrent français/anglais, activation, erreurs de fournisseur,
brouillons, changements rapides de vues, listes de 100 documents/courriers et mobile.
Les réponses des fournisseurs sont simulées : aucun appel payant ou e-mail réel.
Deux avertissements de dépréciation des bibliothèques de test restent connus.

Le démarrage vérifie version, données vides, veille désactivée et filtrage Host.
Le conteneur utilise un utilisateur non-root et conserve ses données dans un volume
privé. Pytest et Ruff sont exclus de l’image d’exécution.

Les audits npm UI/MCP et pip-audit du 23 septembre ne signalaient aucune vulnérabilité
connue. Le contrôle des sources n’a détecté aucun secret connu ; quatre alertes
heuristiques ont été examinées et correspondent à des valeurs fictives de tests.
Ces contrôles ne constituent pas une garantie de sécurité exhaustive.

## Reproduire les contrôles

Le workflow `.github/workflows/quality.yml` contient les commandes exécutées sur
chaque changement. Installer `requirements-dev.txt`, les dépendances UI/MCP et
Chromium avec Playwright. Les scripts `tests/e2e/check-i18n.mjs`,
`tests/e2e/check-motion.mjs` et `tests/e2e/check-record-list.mjs` acceptent
`SEARCHMYJOB_TEST_URL` et simulent les routes API.

Le parcours historique `tests/e2e/check-ui.mjs` utilise le serveur
`tests/support/serve_fixture.py`, avec `SEARCHMYJOB_STATE` dirigé vers un nouveau
dossier temporaire et `SEARCHMYJOB_PORT` dédié. Ne jamais le lancer avec les données
d’une installation personnelle.

La version 0.3.9 nettoie la distribution : documentation fusionnée et chemins
corrigés, retrait de deux adaptateurs MCP natifs inutilisés dans cette édition,
et rejet des noms de fichiers ambigus entre Linux et Windows lors du packaging.
Les résultats de chaque version sont consultables dans GitHub Actions.
