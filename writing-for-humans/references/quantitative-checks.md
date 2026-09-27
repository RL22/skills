# Quantitative checks

Run from the active Sprintz workspace:

```bash
python3 scripts/validate_writing.py <draft-path>
```

For machine-readable output:

```bash
python3 scripts/validate_writing.py --json <draft-path>
```

For enforcement:

```bash
python3 scripts/validate_writing.py --strict <draft-path>
```

## Rule groups

- W001–W002: banned vocabulary and clichés
- W003: throat-clearing opening
- W004: excessive dash usage
- W005: exclamation points
- W006: sentences over 45 words
- W007: uniform sentence cadence
- W008: paragraph walls
- W009: nominalization density
- W010: unsupported hype
- W011: missing evidence marker
- W012: unclear claim type
- W013: opt-in synonym drift
- W014: thesis possibly too late
- W015: maximal promise
- W016: shame or psychological invalidation

Warnings and review findings are not automatically errors. Use editorial
judgment before changing meaning or strategy.
