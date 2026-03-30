# NBA-2K26-Helper-Tool

## Generate tendencies

Use the generator to read all era-split attribute source files (for example `attribute_source_2025_2020.csv`) and `Copilot_Optimized_ATD_Tendencies.csv`:

```bash
python generate_tendencies.py --root . --output generated_tendencies.csv
```

This creates a consolidated `generated_tendencies.csv` with player identifiers and stat-based tendency values calculated from each player's database metrics, then blended with the rules file norms and capped by the configured cap row.
