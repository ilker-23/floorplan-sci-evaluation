# Next Experiment Steps

This is the immediate work order. It is intentionally practical and strict.

## Current Reality

The dataset and split pipeline is now established in Colab/Drive.

Known benchmark state:

- converted layout records: 74,985;
- train/validation/test split: 59,988 / 7,499 / 7,498;
- oracle GT-copy sanity check: mIoU = 1.0, overlap excess = 0.0;
- nearest-neighbor train-program baseline: mIoU about 0.133;
- program-template train-median baseline: mIoU about 0.192;
- legacy GNN with GT-spatial edges is a leakage diagnostic, not a final model;
- the next publishable result must come from `colab/train_leakage_free_gnn.py`.

Therefore the next real scientific step is not prose polishing. It is producing
a leakage-free candidate model and a reviewer-facing evidence pack.

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

1. Oracle GT copy, sanity check only.
2. Nearest-neighbor train-program-signature baseline.
3. Program-template train-median baseline.
4. Legacy notebook checkpoint with program edges, diagnostic.
5. Legacy notebook checkpoint with GT-spatial edges, leakage diagnostic only.
6. Retrained leakage-free GNN candidate.

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

## Step 8: Build the Reviewer Evidence Pack

After collecting metric JSON files, run:

```bash
python scripts/build_review_evidence_pack.py \
  --run oracle_gt_copy=reports/metrics/oracle_gt_copy_metrics.json \
  --run nn_train_program_signature=reports/metrics/nn_train_program_signature_metrics.json \
  --run program_template_train_median=reports/metrics/program_template_train_median_metrics.json \
  --run leakage_free_program_gnn=reports/metrics/leakage_free_program_gnn_metrics.json \
  --baseline nn_train_program_signature \
  --baseline program_template_train_median \
  --diagnostic oracle_gt_copy \
  --reference program_template_train_median \
  --output-md reports/q1_review_evidence_pack.md \
  --output-json reports/q1_review_evidence_pack.json
```

Only rows marked as candidate evidence can support the main model claim.
