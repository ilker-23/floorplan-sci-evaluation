# Model Prediction Export Protocol

## Purpose

Every model, baseline, and ablation must export predictions to the same JSONL
schema before evaluation. Do not report numbers from a custom model-specific
metric script unless the JSONL output also passes `validate_prediction_set.py`.

## Required JSONL Schema

Each line is one test plan:

```json
{
  "plan_id": "10007",
  "rooms": [
    {"id": "r0", "type": "Kitchen", "box": [0.22, 0.24, 0.43, 0.33]},
    {"id": "r1", "type": "Bathroom", "box": [0.28, 0.33, 0.43, 0.43]}
  ],
  "edges": [["r0", "r1"]]
}
```

Rules:

- `plan_id` must match the frozen test split.
- Every expected test `plan_id` must appear exactly once.
- Room ids must match the ground-truth room ids for that plan.
- Boxes must be normalized `[x1, y1, x2, y2]` coordinates in `[0, 1]`.
- The file must be created by inference or by an explicitly named baseline.
- Never use the test ground-truth boxes to construct a claimed model output.

## Mandatory Gate

Run this before any metric:

```bash
python scripts/validate_prediction_set.py \
  --ground-truth outputs/test_ground_truth.jsonl \
  --predictions outputs/model_predictions.jsonl \
  --split-assignments reports/splits/split_assignments.csv \
  --split test \
  --output-json reports/model_prediction_validation.json
```

If this fails, the metric result is not reportable.

## If The Model Does Not Export JSONL Yet

Add a thin adapter after model inference:

1. Load `outputs/test_ground_truth.jsonl` only for ids, room order, room types,
   and room count.
2. Run the model using the same condition/program information.
3. Convert generated boxes to normalized `[x1, y1, x2, y2]`.
4. Copy `plan_id`, room ids, and room types from the test record.
5. Save one JSON object per line.

This adapter is allowed to use test metadata required for conditioning, but not
test target coordinates when reporting a model result.
