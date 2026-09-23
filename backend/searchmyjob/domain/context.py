import contextvars

native_session = contextvars.ContextVar("searchmyjob_native_session", default=None)
