# Architecture

Navigateur → FastAPI → SQLite dans le volume Docker.
FastAPI → adaptateur IA → API HTTPS du fournisseur choisi.
L’adaptateur traduit les outils applicatifs en function calling (OpenAI, DeepSeek, Kimi)
ou tool use (Claude). Les appels d’outils restent validés par Pydantic et liés à la tâche
active ; aucun outil ne peut envoyer de courrier. Résultats et provenance sont persistés.
France Travail utilise OAuth client credentials ; Bright Data utilise son MCP officiel
via Node, avec compteur transactionnel SQLite avant l’opération facturable.

La distribution ne dépend pas du coffre de bureau, de D-Bus ni de clients CLI IA.
Le conteneur tourne sans root, sans capacités Linux ajoutées, avec système de fichiers
principal en lecture seule et un volume privé pour les données.
Les requêtes d’écriture exigent l’origine locale et le jeton de session ; le Host est filtré.
