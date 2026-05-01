"""MORM Chain — DAG-ordered, custom-tx L1 (Phase 10a)."""

__version__ = "0.1.0"
GENESIS_HASH = b"\x00" * 32
FINALITY_DEPTH = 3   # Phase 17b: block at H is finalized once max_height ≥ H + FINALITY_DEPTH
