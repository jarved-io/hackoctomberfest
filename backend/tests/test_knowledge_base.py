"""Tests for the knowledge-base loader (app.knowledge_base)."""

import json
import os
from pathlib import Path

import pytest

from app.knowledge_base import KnowledgeBase


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temp data directory with a valid requests snapshot."""
    lib_dir = tmp_path / "requests"
    lib_dir.mkdir()

    snapshot = {
        "library": "requests",
        "version": "2.31.0",
        "source": {
            "name": "Official docs",
            "url": "https://requests.readthedocs.io/en/v2.31.0/api/",
        },
        "snapshotCompleteness": "partial",
        "symbols": {
            "requests.get": {
                "kind": "function",
                "module": "requests",
                "parameters": ["url", "params", "timeout", "verify"],
                "parameterCompleteness": "verified",
                "positionalParameters": ["url", "params"],
                "minPositionalArguments": 1,
                "maxPositionalArguments": 2,
                "signatureCompleteness": "verified",
            }
        },
    }
    (lib_dir / "2.31.0.json").write_text(json.dumps(snapshot))
    return tmp_path


@pytest.fixture
def kb(data_dir: Path) -> KnowledgeBase:
    return KnowledgeBase(data_dir=data_dir)


# ── 1. Loading a valid snapshot ───────────────────────────────────────────

def test_load_existing_snapshot(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    assert snap.library == "requests"
    assert snap.version == "2.31.0"


def test_snapshot_contains_symbols(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    assert snap.has_symbol("requests.get")


def test_symbol_parameters(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    info = snap.lookup_symbol("requests.get")
    assert info is not None
    assert "timeout" in info.parameters


def test_snapshot_source_provenance(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    assert "readthedocs" in snap.source_url


# ── 2. Missing snapshot ──────────────────────────────────────────────────

def test_missing_version_returns_none(kb: KnowledgeBase):
    assert kb.get_snapshot("requests", "9.99.99") is None


def test_missing_library_returns_none(kb: KnowledgeBase):
    assert kb.get_snapshot("nonexistent", "1.0.0") is None


# ── 3. Malformed JSON ────────────────────────────────────────────────────

def test_malformed_json_returns_none(data_dir: Path):
    lib_dir = data_dir / "broken"
    lib_dir.mkdir()
    (lib_dir / "1.0.0.json").write_text("NOT VALID JSON {{{")
    kb = KnowledgeBase(data_dir=data_dir)
    assert kb.get_snapshot("broken", "1.0.0") is None


def test_invalid_structure_returns_none(data_dir: Path):
    """A valid JSON file missing required keys should not crash."""
    lib_dir = data_dir / "badstruct"
    lib_dir.mkdir()
    (lib_dir / "1.0.0.json").write_text(json.dumps({"foo": "bar"}))
    kb = KnowledgeBase(data_dir=data_dir)
    assert kb.get_snapshot("badstruct", "1.0.0") is None


# ── 4. Unsupported version ───────────────────────────────────────────────

def test_list_available_versions(kb: KnowledgeBase):
    versions = kb.list_available_versions("requests")
    assert "2.31.0" in versions


def test_list_versions_for_unknown_library(kb: KnowledgeBase):
    assert kb.list_available_versions("unknown") == []


# ── 5. Completeness ──────────────────────────────────────────────────────

def test_snapshot_completeness(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    assert snap.snapshot_completeness == "partial"


def test_parameter_completeness(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    info = snap.lookup_symbol("requests.get")
    assert info is not None
    assert info.parameter_completeness == "verified"


def test_signature_metadata(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    info = snap.lookup_symbol("requests.get")
    assert info is not None
    assert info.positional_parameters == ["url", "params"]
    assert info.max_positional_arguments == 2
    assert info.min_positional_arguments == 1
    assert info.signature_completeness == "verified"


# ── 6. Missing symbols ───────────────────────────────────────────────────

def test_lookup_missing_symbol(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    assert snap.lookup_symbol("requests.nonexistent") is None


def test_has_symbol_false(kb: KnowledgeBase):
    snap = kb.get_snapshot("requests", "2.31.0")
    assert snap is not None
    assert snap.has_symbol("requests.nonexistent") is False


# ── Extra: library support check ─────────────────────────────────────────

def test_is_library_supported(kb: KnowledgeBase):
    assert kb.is_library_supported("requests") is True
    assert kb.is_library_supported("nonexistent") is False


# ── Extra: caching ───────────────────────────────────────────────────────

def test_snapshot_is_cached(kb: KnowledgeBase):
    snap1 = kb.get_snapshot("requests", "2.31.0")
    snap2 = kb.get_snapshot("requests", "2.31.0")
    assert snap1 is snap2  # same object, cached
