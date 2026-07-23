"""
Regression guard for a recurring failure pattern in this project: a route
module gets added under app/api/, but its router is never registered on the
FastAPI app in main.py (or one registration masks another). This happened
with /settings going 404 across multiple rounds, and with backtest_router
being double-registered while settings_router was dropped entirely.

This discovers every `router = APIRouter(...)` defined under app/api/*.py
and actually calls each of its routes through TestClient, checking for a
404 specifically (which is what "never registered" looks like from the
outside). It deliberately does NOT introspect app.routes/app.router
internals - FastAPI wraps include_router() calls differently across
versions (e.g. an opaque _IncludedRouter object rather than flattened
APIRoute instances), which makes that approach fragile.
"""

import importlib
import pkgutil
import inspect

import pytest
from fastapi.testclient import TestClient

import app.api as api_package
from app.main import app

client = TestClient(app)


def _discover_api_routes():
    """
    Import every module directly under app/api/ and yield
    (module_name, method, path) for each route its `router` defines.
    """

    for module_info in pkgutil.iter_modules(api_package.__path__):

        if module_info.ispkg:
            continue

        module = importlib.import_module(
            f"app.api.{module_info.name}"
        )

        router = getattr(module, "router", None)

        if router is None:
            continue

        for route in router.routes:

            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None) or set()

            if path is None:
                continue

            for method in methods:
                yield module_info.name, method, path


# A path with {placeholders} needs a real value substituted in to be
# callable; these are just enough to make the request well-formed so we
# can tell "not registered" (404) apart from "registered but this specific
# resource doesn't exist" (also often 404, so we skip these paths rather
# than guess and risk a false positive/negative).
_PATHS_WITH_PARAMS = ("{",)


@pytest.mark.parametrize(
    "module_name,method,path",
    [
        (m, method, path)
        for m, method, path in _discover_api_routes()
        if not any(marker in path for marker in _PATHS_WITH_PARAMS)
    ],
)
def test_api_route_is_registered(module_name, method, path):

    try:
        response = client.request(method, path)
    except Exception:
        # The route matched and reached application code (it's
        # registered) - it just failed for some other reason, e.g. a
        # live network dependency being unreachable in this environment.
        # That's a separate concern from wiring; nothing to check here.
        return

    assert response.status_code != 404, (
        f"{method} {path} (defined in app/api/{module_name}.py) returned "
        f"404 - its router is likely missing an app.include_router(...) "
        f"call in main.py, or a duplicate include_router() elsewhere is "
        f"shadowing it."
    )


def test_settings_endpoint_specifically_is_reachable():
    """
    /settings went missing from main.py's registrations on three separate
    occasions in this project. A dedicated, impossible-to-miss check.
    """

    response = client.get("/settings")

    assert response.status_code == 200, (
        "GET /settings returned "
        f"{response.status_code} - settings_router is likely missing "
        "from main.py's app.include_router(...) calls again."
    )
