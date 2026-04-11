"""Database utility functions and classes."""

import re
import secrets
from typing import Any, List, Optional


def first_value(row: Optional[dict]) -> Optional[Any]:
    """Get the first value from a dict row (row_factory=dict_row)."""
    if not row:
        return None
    values = list(row.values())
    return values[0] if values else None


def dollar_quote_tag(cypher_query: str) -> str:
    """Pick a dollar-quote tag that does not appear in the query (for safe literal embedding)."""
    for tag in ("$cypher$", "$q$", "$body$", "$x$"):
        if tag not in cypher_query:
            return tag
    # Fallback: use a tag with random suffix so it's unlikely to appear
    return "$c" + secrets.token_hex(4) + "$"


def _update_delimiter_depth(
    c: str, depth_p: int, depth_b: int, depth_br: int
) -> Optional[tuple[int, int, int]]:
    """Adjust delimiter depths for ``c``; return None if a closing bracket has no opener."""
    if c == "(":
        return depth_p + 1, depth_b, depth_br
    if c == ")":
        if depth_p < 1:
            return None
        return depth_p - 1, depth_b, depth_br
    if c == "[":
        return depth_p, depth_b + 1, depth_br
    if c == "]":
        if depth_b < 1:
            return None
        return depth_p, depth_b - 1, depth_br
    if c == "{":
        return depth_p, depth_b, depth_br + 1
    if c == "}":
        if depth_br < 1:
            return None
        return depth_p, depth_b, depth_br - 1
    return depth_p, depth_b, depth_br


def split_top_level_commas(s: str) -> Optional[List[str]]:
    """Split s by commas only at top level (not inside (), [], {}, or strings).
    Returns None if quotes or brackets are unbalanced (ambiguous input)."""
    parts: List[str] = []
    cur: List[str] = []
    depth_p, depth_b, depth_br = 0, 0, 0
    in_sq, in_dq = False, False
    i = 0
    while i < len(s):
        c = s[i]
        if in_sq:
            if c == "'" and (i == 0 or s[i - 1] != "\\"):
                in_sq = False
            cur.append(c)
            i += 1
            continue
        if in_dq:
            if c == '"' and (i == 0 or s[i - 1] != "\\"):
                in_dq = False
            cur.append(c)
            i += 1
            continue
        if c == "'":
            in_sq = True
            cur.append(c)
            i += 1
            continue
        if c == '"':
            in_dq = True
            cur.append(c)
            i += 1
            continue

        new_depths = _update_delimiter_depth(c, depth_p, depth_b, depth_br)
        if new_depths is None:
            return None
        depth_p, depth_b, depth_br = new_depths

        if c == "," and depth_p == 0 and depth_b == 0 and depth_br == 0:
            parts.append("".join(cur).strip())
            cur = []
            i += 1
            continue

        cur.append(c)
        i += 1

    if in_sq or in_dq or depth_p != 0 or depth_b != 0 or depth_br != 0:
        return None
    parts.append("".join(cur).strip())
    return parts


def cypher_return_columns(cypher_query: str) -> List[str]:
    """
    Infer RETURN column names from Cypher so we can build AS (col1 agtype, ...).
    AGE requires the AS clause to match the return column count and names.
    """
    # Find position of RETURN
    return_match = re.search(r"\bRETURN\s+", cypher_query, re.IGNORECASE)
    if not return_match:
        return ["result"]
    
    start_pos = return_match.end()
    
    # Find position of next keyword that ends the RETURN clause
    # Using \b instead of \s+ to avoid potential ReDoS from backtracking on spaces
    end_match = re.search(
        r";|\b(?:ORDER\s+BY|LIMIT|SKIP)\b",
        cypher_query[start_pos:],
        re.IGNORECASE | re.DOTALL,
    )
    
    if end_match:
        return_expr = cypher_query[start_pos : start_pos + end_match.start()].strip()
    else:
        return_expr = cypher_query[start_pos:].strip()

    if not return_expr:
        return ["result"]
        
    parts = split_top_level_commas(return_expr)
    if parts is None:
        return ["result"]
        
    names: List[str] = []
    for i, part in enumerate(parts):
        # Prefer "AS alias"
        # Using \b instead of \s+ to avoid unnecessary scanning/backtracking
        as_match = re.search(r"\bAS\s+(\w+)\s*$", part, re.IGNORECASE)
        if as_match:
            name = as_match.group(1)
        else:
            name = f"c{i + 1}"
        
        # Safe identifier: alphanumeric and underscore only
        # \w matches [a-zA-Z0-9_] in Python 3 by default
        if re.match(r"^[a-zA-Z_]\w*$", name):
            names.append(name)
        else:
            names.append(f"c{i + 1}")
            
    return names if names else ["result"]
