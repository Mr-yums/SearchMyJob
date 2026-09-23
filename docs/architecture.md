# Architecture SearchMyJob

Les deux éditions suivent la même structure. `next` utilise les agents locaux ; `docker` utilise les API des fournisseurs. Leurs espaces de données sont indépendants.

```text
backend/searchmyjob/
  domain/                    contrats, règles métier, objets valeur et erreurs
  application/               recherche, assistant, veille, courrier, onboarding
  infrastructure/            connexion SQLite, migrations, coffre et dépôts
  integrations/              fournisseurs IA, recherche externe, Gmail/IMAP
  api/                       fabrique FastAPI, sécurité, injection et routes
  runtime.py                 assemblage des services et contexte de travail
ui/src/
  app/                       coque, navigation et assemblage de l’état
  features/<fonctionnalité>/  vue, contrôleur et composants du domaine
  shared/                    icônes, styles, utilitaires et traductions Docker
tests/
  architecture/              frontières de dépendances exécutables
  unit/                      règles pures
  integration/               API, persistance et adaptateurs simulés
  e2e/                       parcours navigateur
  support/                   doubles, serveur de test et attente des tâches
mcp/                         adaptateurs Node pour les outils des agents
scripts/                     maintenance, diagnostics explicites et distribution
```

## Règles de dépendances

Le domaine ne connaît ni HTTP, ni SQLite, ni les fournisseurs. Les intégrations et la persistance ne dépendent pas des services applicatifs. Les services ne dépendent pas de FastAPI. Le point d’assemblage est `runtime.py`. Les routes utilisent l’instance injectée par la requête. Ni les routes ni les services applicatifs ne contiennent de SQL ; les dépôts portent les requêtes et transactions. Chaque application créée par `create_app` possède son propre moteur, sa file de travail, son jeton et son cycle de fermeture.

Les dépôts conservent le schéma et les migrations existants ; la révision d’un document est atomique. Le contexte de travail sert de port partagé aux services. Une seule tâche active est admise par espace. Le planificateur et la tâche sont annulés et attendus avant fermeture de SQLite.

## Interface

`App.vue` assemble la navigation et les vues. Les contrôleurs par fonctionnalité enregistrent leurs actions et effets sur le magasin de l’espace ; celui-ci centralise les refs persistantes pour préserver les brouillons lors du changement de vue. Une vue reçoit un modèle explicite limité aux champs et actions qu’elle utilise. Les identifiants métier et le contenu de l’utilisateur ne sont pas traduits. Les styles sont chargés dans l’ordre indiqué par `shared/styles/index.css`, afin de conserver la cascade existante.

## Ajouter une fonctionnalité

1. Définir les contrats/règles dans `domain`.
2. Ajouter les opérations de persistance dans un dépôt et le parcours dans `application`.
3. Brancher le service dans `runtime`, puis exposer une route fine.
4. Ajouter la vue et son contrôleur dans `ui/src/features` ; passer les champs nécessaires dans `app/useWorkspace.js`.
5. Tester le comportement dans la couche concernée, puis exécuter les règles d’architecture et les parcours impactés.

## Validation et limites

Les tests Python utilisent un coffre simulé et des dossiers temporaires. Les appels fournisseurs et les envois de mails sont simulés ; ils ne prouvent pas la disponibilité d’une API distante. Les diagnostics réels restent des commandes explicites et peuvent consommer des quotas.

```sh
PYTHONPATH=backend python -m pytest
ruff check backend tests scripts
ruff format --check backend tests scripts
cd ui && npm ci && npm run build
```

Les tests navigateur acceptent `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH` et `SEARCHMYJOB_TEST_URL`. Le serveur de fixture Docker se lance avec `PYTHONPATH=backend`, `SEARCHMYJOB_STATE` et `SEARCHMYJOB_PORT` dédiés : `python tests/support/serve_fixture.py`. Ne pas utiliser les données personnelles pour un test.
