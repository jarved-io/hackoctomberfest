"""
Trusted API reference data loader.

Loads versioned JSON snapshots of API signatures from the ``data/`` directory.
Each snapshot documents known symbols, their parameters, and data provenance.

Snapshot files live at::

    data/<library>/<version>.json

Completeness model:
  complete — The snapshot comprehensively covers the API surface.
  partial  — Only selected symbols/parameters are represented.
  unknown  — Completeness is not established.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import DATA_DIR


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SymbolInfo:
    """Reference information for a single API symbol."""
    name: str
    kind: str = "function"                  # function | method | class
    module: str = ""
    parameters: list[str] = field(default_factory=list)
    parameter_completeness: str = "unknown" # verified | partial | unknown
    description: str = ""
    positional_parameters: list[str] = field(default_factory=list)
    min_positional_arguments: int | None = None
    max_positional_arguments: int | None = None
    signature_completeness: str = "unknown" # verified | partial | unknown


@dataclass
class Snapshot:
    """A versioned API reference snapshot for one library."""
    library: str
    version: str
    source_name: str = ""
    source_url: str = ""
    snapshot_completeness: str = "partial"  # complete | partial | unknown
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)

    def lookup_symbol(self, symbol_name: str) -> SymbolInfo | None:
        """Look up a symbol by fully-qualified name (e.g. 'requests.get')."""
        return self.symbols.get(symbol_name)

    def has_symbol(self, symbol_name: str) -> bool:
        return symbol_name in self.symbols

    def list_symbols(self) -> list[str]:
        return list(self.symbols.keys())


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """Loads and caches versioned API reference data from JSON files.

    Usage::

        kb = KnowledgeBase()
        snap = kb.get_snapshot("requests", "2.31.0")
        if snap:
            info = snap.lookup_symbol("requests.get")
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or DATA_DIR
        self._cache: dict[str, Snapshot] = {}

    # -- public API --

    def get_snapshot(self, library: str, version: str) -> Snapshot | None:
        """Load a versioned snapshot, returning ``None`` if unavailable.

        Handles missing files, malformed JSON, and invalid structure
        gracefully — never raises to the caller.
        """
        cache_key = f"{library}:{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._snapshot_path(library, version)
        if not path.exists():
            logger.warning("No reference data at %s", path)
            return None

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load %s: %s", path, exc)
            return None

        snapshot = self._parse_snapshot(raw)
        if snapshot is not None:
            self._cache[cache_key] = snapshot
        return snapshot

    def list_available_versions(self, library: str) -> list[str]:
        """List version strings for which snapshots exist."""
        lib_dir = self._data_dir / library
        if not lib_dir.is_dir():
            return []
        return sorted(p.stem for p in lib_dir.glob("*.json"))

    def list_libraries(self) -> list[str]:
        """Names of all libraries that have at least one snapshot."""
        if not self._data_dir.is_dir():
            return []
        return sorted(
            d.name for d in self._data_dir.iterdir()
            if d.is_dir() and any(d.glob("*.json"))
        )

    def is_library_supported(self, library: str) -> bool:
        """True if *any* reference data exists for the library."""
        lib_dir = self._data_dir / library
        return lib_dir.is_dir() and any(lib_dir.glob("*.json"))

    # -- internals --

    def _snapshot_path(self, library: str, version: str) -> Path:
        return self._data_dir / library / f"{version}.json"

    def _parse_snapshot(self, raw: dict[str, Any]) -> Snapshot | None:
        """Parse raw JSON into a ``Snapshot``.  Returns ``None`` on error."""
        try:
            source = raw.get("source", {})
            snapshot = Snapshot(
                library=raw["library"],
                version=raw["version"],
                source_name=source.get("name", ""),
                source_url=source.get("url", ""),
                snapshot_completeness=raw.get("snapshotCompleteness", "unknown"),
            )
            for sym_name, sym_data in raw.get("symbols", {}).items():
                pos_params = sym_data.get("positionalParameters", [])
                max_pos = sym_data.get("maxPositionalArguments")
                if max_pos is None and "positionalParameters" in sym_data:
                    max_pos = len(pos_params)
                min_pos = sym_data.get("minPositionalArguments")
                sig_comp = sym_data.get(
                    "signatureCompleteness",
                    "verified" if "positionalParameters" in sym_data else "unknown",
                )

                snapshot.symbols[sym_name] = SymbolInfo(
                    name=sym_name,
                    kind=sym_data.get("kind", "function"),
                    module=sym_data.get("module", ""),
                    parameters=sym_data.get("parameters", []),
                    parameter_completeness=sym_data.get(
                        "parameterCompleteness", "unknown"
                    ),
                    description=sym_data.get("description", ""),
                    positional_parameters=pos_params,
                    min_positional_arguments=min_pos,
                    max_positional_arguments=max_pos,
                    signature_completeness=sig_comp,
                )
            return snapshot
        except (KeyError, TypeError, AttributeError) as exc:
            logger.error("Malformed snapshot data: %s", exc)
            return None
