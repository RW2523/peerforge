"""Which OpenRouter key a request is billed to.

Setting OPENROUTER_API_KEY on the server used to do almost nothing: only
materials and a couple of other routes consulted it, while ai_assist, personas,
turns, defense, assessment and the autonomous engine refused outright with
"OpenRouter API key required". The same deployment answered some requests and
rejected others, which reads as a broken install rather than a config choice.
"""
import ast
import glob
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import resolve_openrouter_key, settings

ROUTES_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'routes')


def test_a_callers_own_key_wins(server_openrouter_key):
    """BYOK must keep working: a user's own credits pay for their own work."""
    assert resolve_openrouter_key('sk-or-v1-caller-key') == 'sk-or-v1-caller-key'


def test_falls_back_to_the_server_key(server_openrouter_key):
    assert resolve_openrouter_key(None) == server_openrouter_key
    assert resolve_openrouter_key('') == server_openrouter_key
    assert resolve_openrouter_key('   ') == server_openrouter_key


def test_returns_none_when_there_is_no_key_anywhere():
    """The autouse fixture blanks the server key, so this is the bare case."""
    assert resolve_openrouter_key(None) is None
    assert resolve_openrouter_key('') is None


def test_whitespace_around_a_caller_key_is_stripped(server_openrouter_key):
    assert resolve_openrouter_key('  sk-or-v1-padded  ') == 'sk-or-v1-padded'


def _handlers_taking_the_header():
    for path in sorted(glob.glob(os.path.join(ROUTES_DIR, '*.py'))):
        src = open(path).read()
        if 'x_openrouter_key' not in src:
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            args = list(node.args.args) + list(node.args.kwonlyargs)
            if not any(a.arg == 'x_openrouter_key' for a in args):
                continue
            yield os.path.basename(path), node.name, node, src


def test_no_route_makes_the_key_header_mandatory():
    """
    `Header(...)` rejects the request with a 422 before the handler runs, so a
    server-side key could never apply to that route.
    """
    mandatory = []
    for fname, name, node, src in _handlers_taking_the_header():
        seg = ast.get_source_segment(src, node) or ''
        if re.search(r'x_openrouter_key:[^=\n]*=\s*Header\(\s*\.\.\.', seg):
            mandatory.append(f'{fname}:{name}')
    assert not mandatory, (
        'These routes require the header outright, so OPENROUTER_API_KEY on the '
        'server cannot reach them:\n  ' + '\n  '.join(mandatory)
    )


# Endpoints that must NOT fall back, with the reason. An endpoint that reports
# on a key rather than working with one would otherwise disclose the deployment
# owner's balance and usage to whoever asked.
NO_FALLBACK = {'openrouter.py:get_openrouter_account'}


def test_every_route_taking_the_header_resolves_it():
    """
    Each handler accepting the header must run it through resolve_openrouter_key
    (or a helper that does). Otherwise that one route silently ignores the
    server key while its neighbours honour it.
    """
    RESOLVERS = ('resolve_openrouter_key', '_require_key')
    unresolved = []
    for fname, name, node, src in _handlers_taking_the_header():
        if f'{fname}:{name}' in NO_FALLBACK:
            continue
        seg = ast.get_source_segment(src, node) or ''
        if not any(r in seg for r in RESOLVERS):
            unresolved.append(f'{fname}:{name}')
    assert not unresolved, (
        'Handlers take X-OpenRouter-Key but never resolve it against the server '
        'key:\n  ' + '\n  '.join(unresolved)
    )


def test_the_account_endpoint_never_reports_on_the_server_key():
    """
    /openrouter/account answers "whose key is this and what credit remains".
    Falling back to the server key would answer that about the deployment
    owner, to any caller. On a REQUIRE_AUTH=false deployment, to anyone at all.
    """
    for fname, name, node, src in _handlers_taking_the_header():
        if f'{fname}:{name}' != 'openrouter.py:get_openrouter_account':
            continue
        seg = ast.get_source_segment(src, node) or ''
        assert 'resolve_openrouter_key' not in seg, (
            'the account endpoint must not fall back to the server key'
        )
        return
    pytest.fail('openrouter.py:get_openrouter_account not found')


def test_no_route_logs_a_key_prefix():
    """
    A logged prefix is enough to correlate a key across log sinks, and these
    lines ran at INFO/WARNING so they reached every aggregator.
    """
    offenders = []
    for path in sorted(glob.glob(os.path.join(ROUTES_DIR, '*.py'))):
        for i, line in enumerate(open(path), 1):
            if not re.search(r'log(ger)?\.\w+', line):
                continue
            if re.search(r'\w*key\w*\[\s*:\s*\d+\s*\]', line, re.I):
                offenders.append(f'{os.path.basename(path)}:{i}')
    assert not offenders, 'key prefixes written to logs:\n  ' + '\n  '.join(offenders)


def test_the_suite_cannot_bill_the_developers_account():
    """
    The autouse fixture must leave no server key visible to tests.

    Without it, "no key supplied" tests fell through to a real key in
    .env.local and made live, billed calls.
    """
    assert not (settings.openrouter_api_key or '').strip()
