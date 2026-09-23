from searchmyjob.infrastructure.database import open_workspace
from searchmyjob.infrastructure.repositories.configuration import ConfigurationRepository
from searchmyjob.infrastructure.repositories.documents import DocumentsRepository
from searchmyjob.infrastructure.repositories.opportunities import OpportunitiesRepository
from searchmyjob.infrastructure.repositories.records import RecordsRepository
from searchmyjob.infrastructure.repositories.runs import RunsRepository
from searchmyjob.infrastructure.repositories.tool_calls import ToolCallsRepository
from searchmyjob.integrations.search import providers as source_providers

"""Runtime operations for the workspace."""
import contextvars
import secrets
import time

from searchmyjob.application.agent_tools import AgentToolService
from searchmyjob.application.assistant import AssistantService
from searchmyjob.application.jobs import JobsService
from searchmyjob.application.mail import MailService
from searchmyjob.application.onboarding import OnboardingService
from searchmyjob.application.search import SearchService
from searchmyjob.application.watch import WatchService
from searchmyjob.application.workspace import WorkspaceService
from searchmyjob.domain.models import Criteria, MailPrefs, Settings
from searchmyjob.infrastructure import bright_budget, vault
from searchmyjob.infrastructure.repositories.conversations import ConversationRepository
from searchmyjob.infrastructure.repositories.outbox import Outbox
from searchmyjob.infrastructure.repositories.usage import UsageLedger
from searchmyjob.infrastructure.repositories.workspace import WorkspaceStore
from searchmyjob.integrations.mail.transport import GmailTransport
from searchmyjob.integrations.search.monthly import MonthlyUsage


class Engine:
    def __init__(self, path):
        self.db = open_workspace(path)
        self.configuration = ConfigurationRepository(self.db)
        self.opportunities = OpportunitiesRepository(self.db, self.configuration)
        self.store = WorkspaceStore(self.db)
        self.records = RecordsRepository(self.db)
        self.document_store = DocumentsRepository(self.db)
        self.runs = RunsRepository(self.db)
        self.tool_calls = ToolCallsRepository(self.db)
        self.current_run = None
        self.conversations = ConversationRepository(self.db)
        self.conversation_scope = contextvars.ContextVar("conversation_id", default=None)
        for k, v in [
            ("criteria", Criteria().model_dump()),
            ("settings", Settings().model_dump()),
            ("profile", ""),
            ("next_heartbeat", 0),
            ("connections", {}),
            ("mail_prefs", MailPrefs().model_dump()),
        ]:
            if self.get(k) is None:
                self.set(k, v)
        self.set("criteria", Criteria.model_validate(self.get("criteria")).model_dump())
        self.set("settings", Settings.model_validate(self.get("settings")).model_dump())
        self.db.execute(
            "UPDATE runs SET status='interrupted',error='Service redémarré : exécution interrompue.',finished=? WHERE status='running'",
            (time.time(),),
        )
        self.usage = UsageLedger(self.db)
        self.bright_monthly = MonthlyUsage(vault.read)
        self.task = None
        self.token = secrets.token_urlsafe(32)
        self.workspace = WorkspaceService(self)
        self.outbox = Outbox(self.db)
        self.mail = MailService(GmailTransport())
        self.onboarding = OnboardingService(self)
        self.onboarding.initialize()
        # [OXIO] Sans cette base, le compteur est « indisponible » et le garde refuse tout appel.
        bright_budget.initialize()
        self.agent_tools = AgentToolService(
            self, source_providers.bright_web, source_providers.bright_page
        )

        self.jobs_service = JobsService(self)
        self.search_service = SearchService(self)
        self.assistant_service = AssistantService(self)
        self.watch_service = WatchService(self)

    def get(self, k):
        return self.configuration.get(k)

    def set(self, k, v):
        return self.configuration.set(k, v)

    def rows(self, sql, args=()):
        return self.records._rows(sql, args)

    def conversation_id(self):
        return self.conversation_scope.get() or self.conversations.default_id()

    def message(self, role, provider, text):
        self.conversations.append(self.conversation_id(), role, provider, text)

    def offers(self):
        return self.opportunities.offers()

    def start(self, kind, provider, fn, conversation_id=None):
        return self.jobs_service.start(kind, provider, fn, conversation_id)

    def phase(self, text):
        return self.jobs_service.phase(text)

    async def search(self, c, collected=None, force=False):
        return await self.search_service.search(c, collected, force)

    async def search_and_report(self, provider, c, request="", instructions="", force=False):
        return await self.search_service.search_and_report(
            provider, c, request, instructions, force
        )

    def objectif(self):
        return self.assistant_service.objectif()

    def context(self):
        return self.assistant_service.context()

    async def advise(self, provider, prompt, tools=False):
        return await self.assistant_service.advise(provider, prompt, tools)

    async def chat(self, body):
        return await self.assistant_service.chat(body)

    async def generate(self, body):
        return await self.assistant_service.generate(body)

    async def heartbeat(self, provider=None):
        return await self.watch_service.heartbeat(provider)

    def tick(self, now):
        return self.watch_service.tick(now)

    async def scheduler(self):
        return await self.watch_service.scheduler()
