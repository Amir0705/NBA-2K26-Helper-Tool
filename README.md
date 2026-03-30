# NBA-2K26-Helper-Tool

## Generate tendencies

Use the generator to read all era-split attribute source files (for example `attribute_source_2025_2020.csv`) and `Copilot_Optimized_ATD_Tendencies.csv`:

```bash
python generate_tendencies.py --root /home/runner/work/NBA-2K26-Helper-Tool/NBA-2K26-Helper-Tool --output generated_tendencies.csv
```

This creates a consolidated `generated_tendencies.csv` with player identifiers and baseline tendency values derived from the rules file's `NBA Norm` row (capped by `Absolute Cap`).
