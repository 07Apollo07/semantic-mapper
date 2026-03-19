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

def get_cell_value(row, col_identifier):
    """
    Extracts a value from a pandas Series/DataFrame row given a column identifier.
    The identifier can be a direct column name or an Excel column letter (A, B, C...).
    """
    if not col_identifier: return "N/A"
    
    # 1. Try as direct column name
    if col_identifier in row.index:
        return str(row[col_identifier])
    
    # 2. Try as Excel letter (A, B, C...)
    idx = excel_col_to_idx(col_identifier)
    if idx is not None and 0 <= idx < len(row):
        return str(row.iloc[idx])
        
    return "N/A"
