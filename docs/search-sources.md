# Recherche par pays et métier / Search by country and profession

Version 0.3.0. Chaque installation demande un pays ISO, un métier libre, les plateformes,
les préférences freelance/télétravail et la langue de l’aide (FR/EN). Aucun métier ni
contrat freelance n’est imposé. Ces critères restent modifiables dans Opportunités.
La langue de l’interface et celle de l’aide sont indépendantes. Le profil libre permet
à l’assistant de tenir compte de l’expérience, des compétences et des contraintes.

## Connexion Bright Data

La clé Bright Data est distincte de la clé IA. Elle est demandée dans l’étape Sources,
enregistrée dans le coffre SQLite privé et n’est jamais renvoyée au navigateur.
Le compte doit disposer des collecteurs **LinkedIn Jobs** et **Indeed Jobs**. Une clé
valide ne garantit pas l’accès à tous les produits ni à tous les pays. Le bouton de
test utilise les plateformes, le pays et le métier choisis et peut être facturé.
France Travail reste une source complémentaire réservée aux recherches en France.

## Collecte et limites

- LinkedIn et Indeed : découverte d’annonces publiques via Web Scraper API,
  `POST /datasets/v3/trigger`, `type=discover_new`, `discover_by=keyword`.
  Pays ISO explicite, ville/région facultative, sinon nom du pays ; domaine Indeed
  local (FR, DE, BE, IT, etc. ; Royaume-Uni : uk.indeed.com).
- Dataset LinkedIn : `gd_lpfll7v5hcqtkxl6l`. Dataset Indeed : `gd_l4dx9j9sscpvs7no2`.
- Maximum 20 résultats par plateforme et métier, transmis avec `limit_per_input`.
  Les axes sont libres, maximum quatre. Les mots-clés séparés par des virgules,
  points-virgules ou retours à la ligne forment aussi des recherches distinctes.
- Autres sites / Upwork / Freelancer : résultats de recherche web Bright Data, avec
  le pays transmis au moteur. Ces extraits restent distincts des données structurées.
- Les annonces conservent leur provenance, URL, entreprise, lieu, contrat, description
  et date lorsqu’ils sont fournis. Un champ absent n’est pas inventé. Une annonce
  collectée ne garantit ni sa disponibilité actuelle ni l’éligibilité du candidat.
- Ce n’est pas une session LinkedIn/Indeed connectée : pas de recommandations privées,
  de messagerie ou de candidature automatique. Les envois restent confirmés séparément.
- Les critères complets et la plateforme font partie de la clé de cache. Changer de
  pays n’affiche donc pas silencieusement une collecte du pays précédent.

## Coûts et erreurs

Le compteur local partage le même SQLite que le garde MCP : réservation atomique
avant chaque déclenchement, même si l’appel échoue. Le polling et le téléchargement
d’une collecte déjà déclenchée n’ajoutent pas un appel. Le plafond porte sur les
**appels**, pas sur les euros ou les résultats facturés par Bright Data.
Une collecte en attente est enregistrée et reprise lors du prochain essai identique.
Le service attend au maximum 150 secondes pour le suivi ; aucun nouveau déclenchement
automatique en cas d’échec. Les requêtes déjà déclenchées chez Bright Data peuvent
continuer même si l’utilisateur annule localement. Une erreur ne devient jamais
« aucune offre ». Une erreur arrête les collectes supplémentaires de ce passage.

## Vérification

Contrats, erreurs HTTP, absence de clé, plafonds, reprise des snapshots, cache et
qualification testés avec réponses simulées. Tests navigateur en français/anglais
et démo sans réseau. **Aucune collecte payante réelle n’a été effectuée pour cette
version.** La couverture et l’autorisation effective des collecteurs doivent être
vérifiées avec le test de connexion de l’installateur. Le schéma Indeed a moins de
documentation publique détaillée que LinkedIn : une évolution du fournisseur peut
nécessiter une adaptation de l’entrée `keyword_search/location/country/domain`.

## Références officielles consultées

- [LinkedIn : découverte par mot-clé](https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-jobs-discover-by-keyword)
- [Indeed : collecteur et découverte par métier/lieu](https://brightdata.com/products/web-scraper/indeed)
- [API asynchrone et limit_per_input](https://docs.brightdata.com/api-reference/rest-api/scraper/asynchronous-requests)
- [Dataset Indeed dans le SDK officiel](https://github.com/brightdata/sdk-python/blob/main/src/brightdata/datasets/indeed/jobs.py)

## English

Choose your search country, profession, platforms, work preferences and advice language
in onboarding. Save your own Bright Data key separately from your AI key. LinkedIn
and Indeed use public job discovery scrapers, not logged-in accounts. Other websites
use web-search snippets. Up to 20 platform listings per profession; up to four
professions. Availability depends on the platform, country and account permissions.
Calls and returned records may incur provider charges; the local counter is not a
currency budget. Pending collections resume without a second trigger. Real paid
collections have not been run for this release; the included tests use simulated
responses. Use the connection test with your own credentials to verify actual access.
