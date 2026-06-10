# Colab + Google Drive RPLAN Workflow

This is the serious path for the next experiments. The local manuscript folder contains the SCI evaluation system; the dataset and model training can stay in Google Drive/Colab.

## Goal

Produce a defensible SCI evidence package:

1. `metadata/plans.jsonl`
2. frozen train/validation/test split
3. leakage-free model predictions on the held-out test set
4. layout metrics
5. architectural screening report
6. DXF validation report

## Colab Cell 1: Mount Drive

```python
from google.colab import drive
drive.mount("/content/drive")
```

## Colab Cell 2: Define Paths

Edit these paths for your Drive.

```python
from pathlib import Path

DRIVE_ROOT = Path("/content/drive/MyDrive")
PROJECT_DIR = DRIVE_ROOT / "SASA-GAN_Buildings"
RPLAN_DIR = DRIVE_ROOT / "RPLAN"  # change this

SCI = PROJECT_DIR / "sci_system"
METADATA_DIR = PROJECT_DIR / "metadata"
OUTPUT_DIR = PROJECT_DIR / "outputs"
REPORT_DIR = SCI / "reports"

for p in [METADATA_DIR, OUTPUT_DIR, REPORT_DIR]:
    p.mkdir(parents=True, exist_ok=True)
```

## Colab Cell 3: Inspect the RPLAN Folder

Run this before writing converters. It will tell us what format your Drive dataset actually uses.

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/colab/inspect_drive_dataset.py \
  --root "/content/drive/MyDrive/RPLAN" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/rplan_drive_inventory.json"
```

## Colab Cell 4: Convert RPLAN to SCI JSONL

Before converting, deep-inspect the candidate file identified by the inventory. For your current Drive inventory, the strongest candidates are:

- `Interface/static/Data/data_train_converted.pkl`
- `Interface/static/Data/data_test_converted.pkl`

Run:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/colab/inspect_rplan_record.py \
  --file "/content/drive/MyDrive/RPLAN/Interface/static/Data/data_train_converted.pkl" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/reports/rplan_train_converted_structure.json" \
  --max-depth 6 \
  --max-items 12
```

and:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/colab/inspect_rplan_record.py \
  --file "/content/drive/MyDrive/RPLAN/Interface/static/Data/data_test_converted.pkl" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/reports/rplan_test_converted_structure.json" \
  --max-depth 6 \
  --max-items 12
```

Send these two JSON summaries back before finalizing the converter.

The final target is:

```text
metadata/plans.jsonl
```

Each row must have:

```json
{"plan_id":"...","family_id":"...","rooms":[{"id":"r1","type":"LivingRoom","box":[x1,y1,x2,y2]}],"edges":[["r1","r2"]]}
```

Important: if edges are derived from ground-truth box contacts, the experiment is reconstruction, not leakage-free program-conditioned generation. For the final paper, prefer program/user adjacency edges.

For the observed Graph2Plan file structure, use:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/colab/graph2plan_train_pkl_to_jsonl.py \
  --source "/content/drive/MyDrive/RPLAN/Interface/static/Data/data_train_converted.pkl" \
  --output "/content/drive/MyDrive/SASA-GAN_Buildings/metadata/plans.jsonl" \
  --summary-json "/content/drive/MyDrive/SASA-GAN_Buildings/reports/plans_conversion_summary.json"
```

Use `rplan_to_sci_jsonl_template.py` only if your local RPLAN copy differs from the inspected Graph2Plan structure.

## Colab Cell 5: Freeze Split

First validate the converted metadata:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/validate_layout_jsonl.py \
  --input "/content/drive/MyDrive/SASA-GAN_Buildings/metadata/plans.jsonl" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/plans_schema_validation.json"
```

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/make_splits.py \
  --input "/content/drive/MyDrive/SASA-GAN_Buildings/metadata/plans.jsonl" \
  --output-dir "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/splits" \
  --group-key family_id \
  --seed 20260610
```

From this point onward, do not tune hyperparameters on the test split.

## Colab Cell 6: Train Models

Before training/evaluation, create frozen ground-truth files from the split:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/filter_layout_jsonl_by_split.py \
  --input "/content/drive/MyDrive/SASA-GAN_Buildings/metadata/plans.jsonl" \
  --split-assignments "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/splits/split_assignments.csv" \
  --output-dir "/content/drive/MyDrive/SASA-GAN_Buildings/outputs" \
  --strict
```

Minimum models:

1. MLP room-feature baseline
2. GCN
3. GAT
4. GATv2
5. GATv2 + topology-aware loss

Each model must export predictions for the test split:

```text
outputs/predictions/MODEL_NAME_test.jsonl
```

## Colab Cell 7: Evaluate Layout Metrics

First validate that predictions exactly match the frozen test split:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/validate_prediction_set.py \
  --ground-truth "/content/drive/MyDrive/SASA-GAN_Buildings/outputs/test_ground_truth.jsonl" \
  --predictions "/content/drive/MyDrive/SASA-GAN_Buildings/outputs/predictions/full_gatv2_test.jsonl" \
  --split-assignments "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/splits/split_assignments.csv" \
  --split test \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/prediction_set_full_gatv2_test.json"
```

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/evaluate_layout_metrics.py \
  --ground-truth "/content/drive/MyDrive/SASA-GAN_Buildings/outputs/test_ground_truth.jsonl" \
  --predictions "/content/drive/MyDrive/SASA-GAN_Buildings/outputs/predictions/full_gatv2_test.jsonl" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/layout_metrics_full_gatv2_test.json" \
  --by-room-count-csv "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/layout_metrics_full_gatv2_by_room_count.csv"
```

## Colab Cell 8: Architectural Screening

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/evaluate_architectural_rules.py \
  --layouts "/content/drive/MyDrive/SASA-GAN_Buildings/outputs/predictions/full_gatv2_test.jsonl" \
  --rules "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/configs/architectural_rules.example.json" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/architectural_rules_full_gatv2_test.json"
```

## Colab Cell 9: DXF Validation

Export DXF for a held-out test subset or the full test set:

```text
outputs/dxf_test/
```

Then:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/validate_dxf.py \
  "/content/drive/MyDrive/SASA-GAN_Buildings/outputs/dxf_test" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/dxf_validation_test.json"
```

## Colab Cell 10: Aggregate Manuscript Tables

After metrics, architectural screening, and DXF validation exist, generate a table:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/aggregate_results.py \
  --model "Full GATv2" \
  --layout "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/layout_metrics_full_gatv2_test.json" \
  --architectural "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/architectural_rules_full_gatv2_test.json" \
  --dxf "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/dxf_validation_test.json" \
  --output-csv "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/main_results_table.csv" \
  --output-md "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/main_results_table.md"
```

## Final Rule

If held-out performance drops, we report the drop honestly. A modest clean score is stronger than a high leaked score.
