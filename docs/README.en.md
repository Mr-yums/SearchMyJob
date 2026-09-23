# SearchMyJob · Docker edition

A personal workspace to find jobs or freelance projects, manage leads, build your
profile and prepare applications. Created by **Mr.yums**.

## Install

You need Docker Engine with Compose v2, or Docker Desktop. Extract the package,
open a terminal in `searchmyjob-docker`, and run:

```sh
docker compose up -d --build
```

Open http://127.0.0.1:8936. The app is bound to the local computer. This edition is
for a personal installation, not a public multi-user service.

Select **English** at the top of the page. French and English are available
throughout the interface and guide. The choice is saved in your browser, and
switching languages keeps your unsaved forms and drafts. Existing messages,
profiles, listings and documents keep their original language. Ask your assistant
explicitly when you want content translated. An English browser starts in English;
other browser languages fall back to French until you choose a language.

## First launch

1. Choose DeepSeek, Kimi, Claude or OpenAI.
2. Enter your personal API key and load or enter a chat model ID.
3. Click **Test and save**. The test checks a response and a tool call. Your provider
   may charge for this short test. An unsuccessful test preserves any previous
   valid configuration. Chat app subscriptions do not replace an API key.
4. Configure France Travail (job listings API client ID and secret) and/or Bright
   Data (MCP and scraper access as required) separately. Your selected source must
   be configured before activation. France Travail only supports France. Testing
   a Bright Data collection may incur charges.
5. Describe your work and activate your workspace. Automatic monitoring starts disabled.

## Use

- Conversation: request searches, refine your offering and prepare applications.
- My profile: enter your experience or import a text PDF, DOCX, TXT or Markdown CV.
- Opportunities: filter and save leads, open sources and generate CVs/cover letters.
- Documents and Mail: review drafts; sending requires explicit approval.
- Monitoring: choose an agent and schedule; enable monitoring when ready.
- Connections: configure providers and sources independently and review usage.

AI requests use your provider account and may incur charges. Bright Data searches
may also incur charges. Local counters are not provider account balances.
France Travail remains a French source regardless of the interface language.

## Data, stop and update

The named Docker volume `searchmyjob-community_data` stores the workspace and API
keys. Keys stay on the server and are not encrypted on disk: protect your backups.
No host account or directory is mounted. Relevant context goes to your AI provider,
and search criteria go to configured sources; this is not an offline AI.

```sh
docker compose stop
docker compose up -d
docker compose up -d --build
```

These commands preserve the volume. Do not use `docker compose down -v` for updates:
it deletes the data. See the French [operations guide](EXPLOITATION.md) for private
backups, restoration and optional Gmail setup.

## Public release

Version 0.3.9. Designed and directed by Mr.yums with AI-assisted development.
This distribution is separate from the author’s personal workspace. Automated tests
use simulated external services; real paid AI/search calls and Gmail have not been
validated for this edition. No general open-source reuse license is granted.
See [release notes](CHANGELOG.md).
