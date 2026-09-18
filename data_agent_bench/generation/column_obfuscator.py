"""
ColumnObfuscator: Deterministic, reproducible column renaming for
anti-memorization experiments.

Uses SHA256-based hashing to generate opaque labels from semantic column names.
The mapping is fully reversible given the same seed.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Tuple


class ColumnObfuscator:
    """
    Deterministic column name obfuscation.

    Given ["income", "age", "approved"], produces mappings like:
        {"income": "var_a3f2", "age": "var_8b1c", "approved": "target_d4e7"}

    The same (column_name, seed) pair always produces the same label.
    """

    # Prefixes by inferred role
    _TARGET_NAMES = {
        "target", "label", "class", "outcome", "approved", "diagnosis",
        "fraud", "is_fraud", "survived", "default", "churn", "species",
        "cultivar", "readmitted", "converted", "returned", "progression",
        "median_house_value",
    }
    _ID_SUFFIXES = ("_id", "id")

    def __init__(self, seed: int = 42):
        self.seed = seed

    def obfuscate(self, columns: List[str], seed: Optional[int] = None) -> Dict[str, str]:
        """
        Map semantic column names to opaque labels.

        Returns {original_name: obfuscated_name}
        """
        s = seed if seed is not None else self.seed
        col_map: Dict[str, str] = {}
        used: set = set()

        for col in columns:
            prefix = self._infer_prefix(col)
            label = self._hash_label(col, prefix, s, used)
            col_map[col] = label
            used.add(label)

        return col_map

    def reverse_map(self, col_map: Dict[str, str]) -> Dict[str, str]:
        """Returns {obfuscated: original} for ground truth mapping."""
        return {v: k for k, v in col_map.items()}

    def obfuscate_dataframe(self, df, seed: Optional[int] = None):
        """
        Rename DataFrame columns and return (renamed_df, col_map).
        """
        col_map = self.obfuscate(list(df.columns), seed)
        return df.rename(columns=col_map), col_map

    def _infer_prefix(self, col: str) -> str:
        col_lower = col.lower().strip()
        if col_lower in self._TARGET_NAMES:
            return "target"
        if col_lower.endswith(self._ID_SUFFIXES) or col_lower == "id":
            return "idx"
        return "var"

    def _hash_label(self, col: str, prefix: str, seed: int, used: set) -> str:
        raw = hashlib.sha256(f"{col}:{seed}".encode()).hexdigest()
        for offset in range(0, len(raw) - 3, 4):
            suffix = raw[offset:offset + 4]
            label = f"{prefix}_{suffix}"
            if label not in used:
                return label
        return f"{prefix}_{raw[:8]}"
