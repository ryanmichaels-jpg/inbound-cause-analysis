"""Internal consistency tests for the taxonomy module.

Enforces invariants like:
- every content asset has a theme mapping (or explicit None for mixed)
- channel affinity rankings cover the full persona enum
- persona theme affinity rankings reference only known themes
- persona population shares sum to 1.0
- channel target volumes sum to TOTAL_LEADS_DEFAULT
"""
