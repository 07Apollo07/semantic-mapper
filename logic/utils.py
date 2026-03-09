def excel_col_to_idx(col_str):
    """Convert Excel column (A, B, AA) to 0-based index."""
    if not col_str or not isinstance(col_str, str):
        return None
    col_str = col_str.upper().strip()
    if not col_str.isalpha():
        return None
    idx = 0
    for char in col_str:
        idx = idx * 26 + (ord(char) - ord('A') + 1)
    return idx - 1
