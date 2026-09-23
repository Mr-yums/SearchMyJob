"""Dependency boundaries: failures must be fixed in the owning layer."""

import ast

import pytest
from searchmyjob.config import PROJECT_ROOT

PACKAGE = PROJECT_ROOT / "backend/searchmyjob"


@pytest.mark.parametrize(
    "layer, forbidden",
    [
        (
            "domain",
            (
                "fastapi",
                "sqlite3",
                "httpx",
                "searchmyjob.api",
                "searchmyjob.application",
                "searchmyjob.infrastructure",
                "searchmyjob.integrations",
            ),
        ),
        (
            "infrastructure",
            ("fastapi", "searchmyjob.api", "searchmyjob.application", "searchmyjob.runtime"),
        ),
        (
            "integrations",
            ("fastapi", "searchmyjob.api", "searchmyjob.application", "searchmyjob.runtime"),
        ),
        ("application", ("fastapi", "searchmyjob.api", "searchmyjob.runtime")),
    ],
)
def test_dependency_direction(layer, forbidden):
    for source in (PACKAGE / layer).rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            names = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for name in names:
                assert not any(
                    name == prefix or name.startswith(prefix + ".") for prefix in forbidden
                ), f"{source.relative_to(PACKAGE)} imports {name}"


def test_routes_do_not_execute_sql():
    for source in [*(PACKAGE / "api/routes").glob("*.py"), *(PACKAGE / "application").glob("*.py")]:
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("execute", "executemany", "executescript"), (
                    source.name
                )
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert (
                    not node.value.lstrip()
                    .upper()
                    .startswith(("SELECT ", "UPDATE ", "INSERT INTO ", "DELETE FROM "))
                ), source.name


def test_tests_do_not_import_other_test_modules():
    for source in (PROJECT_ROOT / "tests").rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").split(".")[-1].startswith("test_"), source.name
