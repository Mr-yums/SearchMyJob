"""Resolve services from the current application, never from a module global."""

from fastapi import Request


def get_engine(request: Request):
    return request.app.state.engine
