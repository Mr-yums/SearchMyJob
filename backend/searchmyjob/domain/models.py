"""Validated input contracts shared by the application adapters."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from searchmyjob.domain.countries import country_code

Country = Annotated[str, AfterValidator(country_code)]
Topic = Annotated[str, Field(min_length=1, max_length=150)]


class Criteria(BaseModel):
    # [OXIO · Opus 4.8 · 16/09/2026] Deux objectifs sur le même outil : trouver un emploi, ou
    # prospecter des clients à qui vendre une prestation. Le mode oriente consignes, format et requêtes.
    objectif: Literal["emploi", "prospection"] = "emploi"
    # [Sol] Explicit independent topics, maximum four; empty means use keywords.
    axes: list[Topic] = Field(default_factory=list, max_length=4)
    platforms: list[Literal["linkedin", "indeed", "direct", "freelance"]] = Field(
        default_factory=lambda: ["linkedin", "indeed", "direct"], min_length=1, max_length=4
    )
    country: Country = "fr"
    response_language: Literal["fr", "en"] = "fr"
    international: bool = True
    keywords: str = Field("", max_length=150)
    department: str = Field("", max_length=20, pattern=r"^[0-9ABab,]*$")
    location: str = Field("", max_length=100)
    contract: str = Field("", max_length=20, pattern=r"^[A-Z,]*$")
    remote: bool = False
    freelance: bool = False
    min_tjm: int = Field(0, ge=0, le=5000)
    exclude: str = Field("", max_length=400)
    source: Literal["france", "bright", "both"] = "bright"


class Settings(BaseModel):
    enabled: bool = False
    interval_hours: int = Field(6, ge=1, le=168)
    start_hour: int = Field(8, ge=0, le=23)
    end_hour: int = Field(20, ge=1, le=24)
    max_daily: int = Field(4, ge=1, le=24)
    provider: Literal["deepseek", "kimi", "claude", "openai"] = "openai"
    cache_hours: int = Field(6, ge=0, le=168)
    instructions: str = Field(
        "Repère les nouvelles opportunités, explique les correspondances et les points à vérifier.",
        max_length=3000,
    )


class UIPreferences(BaseModel):
    page_width: Literal["centered", "full"] = "centered"
    agent_width: Literal["normal", "full"] = "full"
    theme: Literal["classique", "searchmyjob", "sombre"] = "classique"
    layout: int = Field(1, ge=1, le=4)
    panels: list[str] = Field(default_factory=list, max_length=4)
    tabs: list[str] = Field(default_factory=list, max_length=7)
    collapsed: bool = False
    provider: Literal["deepseek", "kimi", "claude", "openai"] = "openai"


class HeartbeatDraft(BaseModel):
    values: dict


class Chat(BaseModel):
    text: str = Field(min_length=1, max_length=15000)
    provider: Literal["deepseek", "kimi", "claude", "openai"] = "openai"
    conversation_id: str | None = Field(None, max_length=64)


class ConversationTitle(BaseModel):
    title: str = Field("Nouvelle conversation", min_length=1, max_length=100)


class Profile(BaseModel):
    text: str = Field("", max_length=60000)


class Status(BaseModel):
    status: Literal["new", "saved", "dismissed", "ready"]


class Generate(BaseModel):
    offer_id: str
    kind: Literal["cv", "letter", "email"] = "letter"
    provider: Literal["deepseek", "kimi", "claude", "openai"] = "openai"
    conversation_id: str | None = Field(None, max_length=64)


class AgentSearch(BaseModel):
    criteria: Criteria | None = None
    force: bool = False


class Activation(Criteria):
    country: Country
    provider: Literal["deepseek", "kimi", "claude", "openai"] = "openai"
    profile: str = Field("", max_length=60000)
    keywords: str = Field("", max_length=150)
    freelance: bool = False
    remote: bool = False
    free_applications: bool = True


class EditDoc(BaseModel):
    text: str = Field(min_length=1, max_length=60000)
    approved: bool = False


class EmailCreate(BaseModel):
    offer_id: str = Field("", max_length=64)
    document_id: str = Field("", max_length=64)


class EmailDraftIn(BaseModel):
    to: str = Field("", max_length=320)
    subject: str = Field("", max_length=300)
    body: str = Field("", max_length=30000)


class EmailSend(BaseModel):
    confirm: bool = False


class MailPrefs(BaseModel):
    sender_name: str = Field("", max_length=120)


class BrightBudget(BaseModel):
    # [OXIO] Plafond local d'appels facturants Bright Data ; la remise à zéro précède le réglage.
    limit: int | None = Field(None, ge=1, le=5000)
    reset: bool = False


class Credentials(BaseModel):
    ft_client_id: str = Field("", max_length=500)
    ft_client_secret: str = Field("", max_length=500)
    bright_key: str = Field("", max_length=500)
    bright_zone: str = Field("", max_length=100, pattern=r"^[\w-]*$")
