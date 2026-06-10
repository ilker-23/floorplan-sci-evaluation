# Next Experiment Steps

This is the immediate work order. It is intentionally practical and strict.

## Current Reality

Inside this manuscript folder, there is no actual RPLAN dataset, no full prediction JSONL, no training logs, and no full DXF export set. There are manuscript files, figures, scripts, and three DXF examples.

You use RPLAN from Google Drive in Colab. Therefore the next real scientific step is not rewriting prose. It is connecting the Colab/Drive model-data pipeline to the SCI evaluation system.

Start with:

```text
sci_system/colab/COLAB_RPLAN_WORKFLOW.md
```

First run the Drive inventory script:

```bash
python /content/drive/MyDrive/SASA-GAN_Buildings/sci_system/colab/inspect_drive_dataset.py \
  --root "/content/drive/MyDrive/RPLAN" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/rplan_drive_inventory.json"
```

Then inspect `rplan_drive_inventory.json` and edit the converter template if needed.

## Step 1: Locate or Export the Dataset Metadata

Create:

```text
metadata/plans.jsonl
```

Each row must include:

```json
{
  "plan_id": "unique_id",
  "family_id": "optional_group_id",
  "rooms": [
    {"id": "r1", "type": "LivingRoom", "box": [x1, y1, x2, y2]}
  ],
  "edges": [["r1", "r2"]]
}
```

Critical rule:

The `edges` field must reflect the user/design program, not ground-truth geometry contact, for the final claim.

## Step 2: Freeze the Split

Run:

```bash
python3 sci_system/scripts/make_splits.py \
  --input metadata/plans.jsonl \
  --output-dir sci_system/reports/splits \
  --group-key family_id \
  --seed 20260610
```

No hyperparameter tuning after looking at the test results.

## Step 3: Export Model Predictions

For each trained model, export:

```text
outputs/predictions/MODEL_NAME_test.jsonl
```

It must use the same `plan_id` and room `id` values as ground truth.

Required first models:

1. MLP baseline.
2. GCN.
3. GAT.
4. GATv2.
5. Full GATv2 + topology-aware loss.

## Step 4: Run Layout Metrics

Example:

```bash
python3 sci_system/scripts/evaluate_layout_metrics.py \
  --ground-truth outputs/test_ground_truth.jsonl \
  --predictions outputs/predictions/full_gatv2_test.jsonl \
  --output-json sci_system/reports/layout_metrics_full_gatv2_test.json \
  --by-room-count-csv sci_system/reports/layout_metrics_full_gatv2_by_room_count.csv
```

## Step 5: Run Architectural Screening

Example:

```bash
python3 sci_system/scripts/evaluate_architectural_rules.py \
  --layouts outputs/predictions/full_gatv2_test.jsonl \
  --rules sci_system/configs/architectural_rules.example.json \
  --output-json sci_system/reports/architectural_rules_full_gatv2_test.json
```

This does not prove constructability. It screens for obvious layout failures.

## Step 6: Export DXF for the Test Set

Create:

```text
outputs/dxf_test/
```

Then run:

```bash
python3 sci_system/scripts/validate_dxf.py outputs/dxf_test \
  --output-json sci_system/reports/dxf_validation_test.json
```

Do not use only high-IoU examples.

## Step 7: Only Then Rewrite Results

The Results section must be rewritten only after Steps 1-6 are complete.

If the held-out score drops, do not hide it. A lower but honest held-out score is much more publishable than a high leaked score.
