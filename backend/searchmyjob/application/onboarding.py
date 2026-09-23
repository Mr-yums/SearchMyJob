"""One-time workspace activation, independent of browser storage."""

import time

from searchmyjob.domain.models import Activation, Criteria, Settings, UIPreferences


class OnboardingService:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        if self.engine.get("activation") is not None:
            return
        existing = bool((self.engine.get("profile") or "").strip()) or any(
            self.engine.configuration.has_records(table)
            for table in ("offers", "messages", "documents", "runs")
        )
        self.engine.set(
            "activation",
            {
                "completed": existing,
                "existing_workspace": existing,
                "completed_at": None,
                "version": 1,
            },
        )

    def complete(self, body: Activation):
        if self.engine.get("activation")["completed"]:
            return self.engine.get("activation")
        from searchmyjob.integrations.ai.provider import saved

        if not saved(body.provider).get("tested_at"):
            from searchmyjob.domain.errors import WorkspaceError as HTTPException

            raise HTTPException(422, "Teste la connexion IA avant d’activer ton espace.")
        from searchmyjob.domain.errors import WorkspaceError
        from searchmyjob.infrastructure.vault import read

        if body.country != "fr" and body.source in ("france", "both"):
            raise WorkspaceError(
                422, "France Travail couvre la France : choisis Bright Data pour ce pays."
            )
        keys = read()
        if body.source in ("bright", "both") and not keys.get("bright_key"):
            raise WorkspaceError(422, "Enregistre ta clé Bright Data avant de continuer.")
        if body.source in ("france", "both") and not (
            keys.get("ft_client_id") and keys.get("ft_client_secret")
        ):
            raise WorkspaceError(
                422, "Enregistre les identifiants France Travail avant de continuer."
            )
        preferences = (
            self.engine.get("preferences")
            or UIPreferences(
                panels=["conversation", "offers", "documents", "heartbeat"], tabs=["conversation"]
            ).model_dump()
        )
        criteria = {
            **self.engine.get("criteria"),
            **body.model_dump(include=set(Criteria.model_fields)),
        }
        if body.free_applications:
            criteria["exclude"] = ", ".join(
                filter(
                    None,
                    [
                        criteria.get("exclude", ""),
                        "paiement pour candidater, achat de crédits, abonnement obligatoire pour postuler",
                    ],
                )
            )
        criteria = Criteria.model_validate(criteria).model_dump()
        settings = Settings.model_validate(
            {**self.engine.get("settings"), "provider": body.provider}
        ).model_dump()
        activation = {
            "completed": True,
            "existing_workspace": False,
            "completed_at": time.time(),
            "version": 1,
        }
        with self.engine.configuration.transaction("activation"):
            self.engine.set("preferences", {**preferences, "provider": body.provider})
            self.engine.set("settings", settings)
            self.engine.set("criteria", criteria)
            if body.profile.strip():
                self.engine.set("profile", body.profile.strip())
            self.engine.set("activation", activation)
        return activation
