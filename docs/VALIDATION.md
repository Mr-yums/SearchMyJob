# Vérifications de l’édition 0.1.0

180 tests réussis à l’intérieur du conteneur Docker sur Linux amd64, le 18 septembre 2026.
Le conteneur utilise Python 3.14 et Node 24, un utilisateur non-root et les scripts MCP embarqués.

Les API IA sont testées par simulation HTTP pour les quatre fournisseurs : authentification,
appel d’outil, aller-retour outil/réponse finale, suivi des tokens et erreurs sans exposition
de la clé. Un test d’intégration traverse le chat, l’adaptateur IA et l’enregistrement d’un
brouillon, sans envoi. L’activation est refusée avant validation du fournisseur.

Chromium : clé refusée, liste des modèles, validation, clé effacée du formulaire après
succès, état conservé après rechargement, changement de fournisseur, sources séparées,
activation, conversation et persistance. Mise en page testée à 1440 et 390 pixels.

Ces essais utilisent des réponses simulées, **pas les comptes réels des fournisseurs**.
La connexion facturée doit être testée par chaque installateur avec sa propre clé.
Aucun message, candidature ni e-mail externe n’a été envoyé pendant la préparation.

Dépendances JavaScript : SDK MCP fixé à 1.27.1, y compris la dépendance transitive de
Bright Data. `npm audit` sans vulnérabilité signalée lors de la préparation, côté UI et MCP.
Ce résultat est daté et ne remplace pas les mises à jour ultérieures.

Pour reproduire le test navigateur, dans un environnement de test sans données personnelles :
installer Playwright hors du runtime, compiler l’UI, lancer `tests/serve_fixture.py` avec
`SEARCHMYJOB_STATE` pointant vers un **nouveau dossier temporaire**, `SEARCHMYJOB_PORT=8965`,
puis exécuter `scripts/check-ui.mjs`. Ce serveur remplace uniquement les fournisseurs par
simulation et ne doit jamais être utilisé pour une instance personnelle.

Instance Docker de validation : démarrage vide, aucun compte IA hérité, refus d’un Host ou
d’une Origin étrangère. Après recréation du conteneur, profil et identifiants de test
conservés, veille désactivée et compteur Bright Data toujours à zéro.
