# Références consultées pour les adaptateurs

- OpenAI : https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
- DeepSeek : https://api-docs.deepseek.com/guides/tool_calls/
- Kimi / Moonshot : https://moonshot-ai.gitbook.io/moonshot-ai/getting-started-guide/use-kimi-api-for-tool-calls
- Claude : https://platform.claude.com/docs/en/api/overview et https://platform.claude.com/docs/en/api/messages/create

Les endpoints sont fixes côté serveur. La clé est envoyée uniquement au fournisseur
sélectionné, sans suivre de redirection. La liste de modèles est lue auprès du fournisseur ;
un test de génération avec outil valide la combinaison clé / modèle avant enregistrement.
Les erreurs HTTP sont résumées sans exposer le corps brut du fournisseur ou les clés.
