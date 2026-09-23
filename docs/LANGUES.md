# Langues de l’interface

La version Docker propose `fr` et `en`. Le sélecteur est présent dans l’assistant
initial et dans l’en-tête. La préférence `smj-language` reste dans le navigateur ;
à défaut, un navigateur anglophone utilise l’anglais, les autres le français.
Changer de langue ne recharge pas l’application et ne modifie pas les données.

- `ui/src/shared/i18n/index.js` : état réactif partagé, traduction des libellés, formats régionaux.
- `ui/src/shared/i18n/locales/en.json` : textes anglais, indexés par les libellés français.
- `ui/src/shared/components/LanguageSwitcher.vue` : sélecteur accessible.
- `ui/public/guide.html` et `guide-en.html` : guides dans les deux langues.

Les appels `tr()` doivent porter sur les textes de l’application, pas sur les CV,
les messages, les titres saisis, les extraits collectés ou les documents générés.
Les valeurs des filtres, identifiants de fournisseurs et données envoyées à l’API
restent stables ; seul leur libellé d’affichage change. Un message inconnu d’un
service externe reste affiché tel quel plutôt que remplacé par un texte trompeur.
Le fuseau des horaires de veille reste Europe/Paris, indiqué dans les deux langues.

## Vérification navigateur

Avec l’interface démarrée sur un port de test et Playwright disponible :

```sh
SEARCHMYJOB_TEST_URL=http://127.0.0.1:18936 node tests/e2e/check-i18n.mjs
```

`PLAYWRIGHT_MODULE` peut désigner un module Playwright déjà installé et
`CHROMIUM_PATH` un navigateur. Toutes les routes API sont simulées : aucun appel
IA, envoi d’e-mail, enregistrement réel ou recherche payante. Le parcours couvre
l’activation, une erreur de clé, les vues de l’espace, la persistance de la langue,
les brouillons, les identifiants métier, le guide et le format mobile.
