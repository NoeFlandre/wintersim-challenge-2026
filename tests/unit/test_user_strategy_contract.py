"""Contract tests for the participant-owned UserStrategy adapter.

These tests pin the public surface that the organizer framework calls:

* The class is exactly named ``UserStrategy``.
* The four required static methods exist with the exact names and a compatible
  argument signature (the organizer's documented parameter names must be
  accepted positionally or by keyword).
* Each method is static and callable without instantiation.
* For this baseline milestone every method returns ``None`` (delegating to the
  organizer fallback) and never mutates any of its arguments, even sentinel
  mutable inputs.

The tests use only sentinel objects defined here; they never import organizer
source.
"""

from __future__ import annotations

import inspect

import pytest
from response_strategies.user_strategy import UserStrategy

REQUIRED_METHODS: dict[str, list[str]] = {
    "select_vessel_for_berth": [
        "maritime_data_context",
        "port",
        "waiting_vessels",
        "available_berths",
        "current_time",
        "waiting_since_by_vessel",
    ],
    "create_alternative_service_routes": ["context", "now", "vessel"],
    "assign_associated_bookings": ["context", "now", "shipment"],
    "adjust_bookings_before_cargo_handling": ["context", "now", "vessel"],
}


def test_class_is_named_user_strategy() -> None:
    assert UserStrategy.__name__ == "UserStrategy"


@pytest.mark.parametrize("method_name,expected_params", list(REQUIRED_METHODS.items()))
def test_required_static_methods_have_compatible_signature(
    method_name: str, expected_params: list[str]
) -> None:
    method = getattr(UserStrategy, method_name, None)
    assert method is not None, f"UserStrategy missing required method {method_name}"
    assert isinstance(inspect.getattr_static(UserStrategy, method_name), staticmethod), (
        f"UserStrategy.{method_name} must be a staticmethod"
    )

    sig = inspect.signature(method)
    params = list(sig.parameters)
    # The organizer call sites pass these positionally; the participant method
    # must accept at least the documented parameter names in order.
    assert params == expected_params, (
        f"UserStrategy.{method_name} signature {params} != expected {expected_params}"
    )


def test_select_vessel_for_berth_returns_none_and_does_not_mutate() -> None:
    waiting = ["vessel_a", "vessel_b"]
    berths = ["berth_1"]
    snapshot = list(waiting)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=berths,
        current_time=0,
        waiting_since_by_vessel={"vessel_a": 0},
    )
    assert result is None
    assert waiting == snapshot, "must not mutate waiting_vessels"
    assert berths == ["berth_1"], "must not mutate available_berths"


def test_create_alternative_service_routes_returns_none_and_leaves_context_unchanged() -> None:
    context = {"routes": [1, 2, 3], "vessels": ["x"]}
    snapshot = {"routes": list(context["routes"]), "vessels": list(context["vessels"])}
    result = UserStrategy.create_alternative_service_routes(context, now=5, vessel="x")
    assert result is None
    assert context == snapshot, "None result must leave context unchanged"


def test_assign_associated_bookings_returns_none() -> None:
    result = UserStrategy.assign_associated_bookings(context={"k": 1}, now=10, shipment=object())
    assert result is None


def test_adjust_bookings_before_cargo_handling_returns_none() -> None:
    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context={"k": 1}, now=10, vessel=object()
    )
    assert result is None


def test_all_methods_static_callable_via_class() -> None:
    # Every required method must be callable on the class without an instance.
    for name in REQUIRED_METHODS:
        method = getattr(UserStrategy, name)
        assert callable(method)
        # Binding check: a staticmethod accessed on the class must not require
        # a 'self' argument (it has no 'self' parameter).
        sig = inspect.signature(method)
        assert "self" not in sig.parameters, f"{name} must not be an instance method"


def test_module_does_not_import_development_tooling() -> None:
    # The submission must not depend on our dev CLI package.
    import response_strategies.user_strategy as mod

    src = inspect.getsource(mod)
    assert "wsc2026_tools" not in src
