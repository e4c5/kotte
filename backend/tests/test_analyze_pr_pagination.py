"""Tests for PR comment script pagination (fail-fast on inconsistent pageInfo)."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANALYZE_PR = _REPO_ROOT / ".agents/skills/respond-pr-review-comments/scripts/analyze_pr.py"


def _load_analyze_pr():
    spec = importlib.util.spec_from_file_location("analyze_pr", _ANALYZE_PR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_ANALYZE_PR}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not _ANALYZE_PR.is_file(), reason="analyze_pr.py not in tree")
def test_fetch_review_threads_raises_when_has_next_without_cursor():
    mod = _load_analyze_pr()

    bad_page = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": True, "endCursor": None},
                    }
                }
            }
        }
    }

    with patch.object(mod, "run_gh_graphql", return_value=bad_page):
        with pytest.raises(RuntimeError, match="fetch_review_threads"):
            mod.fetch_review_threads("o", "r", 1)
