"""A1 — every Anthropic client must carry an explicit timeout.

The SDK default is a 600-second read timeout with 2 automatic retries: one
unresponsive call can occupy a worker for ~30 minutes. Worse, briefing_engine
called the SYNC client inside async methods, which blocks the event loop —
one hung briefing froze the entire API, not just that request.

These are source-scan guards, same pattern as the date.today() guard in
test_ledger_outcomes: the property is "no call site regresses", and a grep is
the cheapest thing that actually pins it.
"""

import pathlib
import re


def _py_files():
    root = pathlib.Path("ospra_os")
    return [p for p in root.rglob("*.py")
            if p.is_file() and "__pycache__" not in str(p)]


def test_every_anthropic_client_sets_an_explicit_timeout():
    """Timeout is set at CLIENT construction (one value covers every call made
    through that client), so the invariant is: no `Anthropic(...)` /
    `AsyncAnthropic(...)` construction without a `timeout` kwarg."""
    offenders = []
    for p in _py_files():
        src = p.read_text()
        for m in re.finditer(r"(?:Async)?Anthropic\s*\(", src):
            # Skip class definitions / imports; only constructions with args.
            tail = src[m.end(): m.end() + 400]
            # The construction's argument span, up to the closing paren at
            # depth 0 — crude but sufficient for these call sites.
            depth, span = 1, []
            for ch in tail:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                span.append(ch)
            args = "".join(span)
            if "api_key" in args and "timeout" not in args:
                offenders.append(f"{p}:{src[:m.start()].count(chr(10)) + 1}")
    assert not offenders, (
        "Anthropic client(s) constructed without an explicit timeout — the SDK "
        f"default is 600s x 2 retries (~30 min hung worker): {offenders}"
    )


def test_briefing_engine_never_calls_the_sync_client_on_the_event_loop():
    """The sync client called directly inside an async method blocks the event
    loop — the whole API — for the duration. Every messages.create in
    briefing_engine must go through asyncio.to_thread."""
    src = pathlib.Path("ospra_os/intelligence/briefing_engine.py").read_text()
    # A DIRECT call is `self.claude.messages.create(` — an open paren means it
    # is being invoked on the loop. Passed as a callable to to_thread it is
    # followed by a comma instead.
    direct = re.findall(r"self\.claude\.messages\.create\s*\(", src)
    threaded = re.findall(
        r"asyncio\.to_thread\(\s*self\.claude\.messages\.create", src)
    assert not direct, (
        f"{len(direct)} direct sync call(s) in briefing_engine block the "
        "event loop — wrap with asyncio.to_thread"
    )
    assert threaded, "expected at least one threaded call site"


def test_briefing_routes_do_not_generate_inline():
    """A1: the routes serve a cached briefing (or 'generating') and schedule
    the AI call via BackgroundTasks AFTER the response. An inline await of
    engine.generate_* in the handler puts the model call back on the request
    path."""
    src = pathlib.Path(
        "ospra_os/intelligence/intelligence_core_routes.py").read_text()
    # Handlers must not await generation directly...
    assert "return await engine.generate_morning_briefing" not in src
    assert "await engine.generate_on_demand_briefing(user_id" not in src.split(
        "_generate_and_cache_on_demand")[0].split("def get_on_demand_briefing")[-1]
    # ...and the background path must exist.
    assert "background_tasks.add_task" in src
    assert "_briefing_cache_get" in src
