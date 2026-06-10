# SCI Hard Revision Plan

This is the working plan for turning the current GNN-GAN manuscript into a defensible SCI/Elsevier paper. It is intentionally strict.

## Phase 0: Stop Unsafe Claims

Before any submission, replace:

- "CAD-ready plan" -> "editable layer-separated DXF layout skeleton"
- "drafting-ready layout" -> "editable preliminary layout"
- "code-conformant" -> "geometrically structured"
- "constructible alternatives" -> "candidate layout alternatives"
- "keeps every predicted room inside the drawing frame by construction" -> "bounds box parameters, while out-of-bounds penalties discourage protrusion"

Reason: the current output is room boxes/layers, not a complete architectural construction drawing.

## Phase 1: Rebuild the Dataset Protocol

Deliverables:

1. `metadata/plans.jsonl`
2. `sci_system/reports/splits/split_manifest.json`
3. `sci_system/reports/splits/split_assignments.csv`

Rules:

- Use only program-visible information as input.
- Do not derive final input edges from target box contact unless the task is explicitly labelled reconstruction.
- Freeze train/validation/test before model tuning.

Command template:

```bash
python3 sci_system/scripts/make_splits.py \
  --input metadata/plans.jsonl \
  --output-dir sci_system/reports/splits \
  --group-key family_id \
  --seed 20260610
```

## Phase 2: Train the Minimum Baseline Set

Train all models under the same split:

1. MLP with room features only.
2. GCN.
3. GAT.
4. GATv2 without target room sizes.
5. GATv2 without GIoU.
6. GATv2 without adjacency loss.
7. GATv2 without overlap/OOB penalties.
8. Full GATv2 objective.

If the GAN stage is kept:

9. GNN layout only.
10. GNN + Pix2Pix.
11. GNN + Pix2Pix without feature matching/R1.

Minimum seeds:

- Preferred: 3 seeds.
- If only 1 seed is possible, do not write model-level standard deviation. Report test-example distribution instead.

## Phase 3: Export Prediction JSONL

Every model must export predictions in this structure:

```json
{"plan_id":"...","rooms":[{"id":"r1","type":"Kitchen","box":[x1,y1,x2,y2]}],"edges":[["r1","r2"]]}
```

Ground truth and predictions must use the same room ids.

Command template:

```bash
python3 sci_system/scripts/evaluate_layout_metrics.py \
  --ground-truth outputs/test_ground_truth.jsonl \
  --predictions outputs/full_gatv2_predictions.jsonl \
  --output-json sci_system/reports/layout_metrics_test_full_gatv2.json \
  --by-room-count-csv sci_system/reports/layout_metrics_test_full_gatv2_by_room_count.csv
```

## Phase 4: Validate DXF at Scale

Do not use only three pretty DXF examples.

Export DXF for the whole held-out test set or a declared test subset. Then run:

```bash
python3 sci_system/scripts/validate_dxf.py outputs/dxf_test \
  --output-json sci_system/reports/dxf_validation_report.json
```

Minimum table:

- number of DXF files;
- export success rate;
- closed polyline rate;
- layer consistency;
- mean room layers;
- median file size.

## Phase 5: Rewrite the Manuscript Around the Real Claim

Recommended title:

> Program-Conditioned Residential Layout Placement with Graph Attention and Editable DXF Export

Stronger version, only if GAN results are truly central:

> A Graph-Attention and Adversarial Framework for Program-Conditioned Residential Layout Placement and Editable DXF Export

Core contributions:

1. Leakage-free program-conditioned graph representation.
2. GATv2-based room-placement regressor.
3. Topology-aware loss with explicit adjacency, overlap, and boundary terms.
4. Domain-specific held-out evaluation.
5. Deterministic DXF layout-skeleton export and validation.

## Phase 6: Required Manuscript Tables

### Table 1: Dataset and Split

| Split | Plans | Mean rooms | Room range | Notes |
|---|---:|---:|---:|---|

### Table 2: Main Held-Out Test Results

| Model | mIoU | Adj-F1 | Overlap | Boundary violation | Area MAPE | Conn. valid | Time |
|---|---:|---:|---:|---:|---:|---:|---:|

### Table 3: Ablation

| Configuration | mIoU | Adj-F1 | Overlap | Boundary violation |
|---|---:|---:|---:|---:|

### Table 4: Room-Count Stratification

| Room count | n | mIoU | Adj-F1 | Failure rate |
|---|---:|---:|---:|---:|

### Table 5: DXF Validation

| Metric | Value |
|---|---:|

### Table 6: Failure Modes

| Failure mode | Frequency | Typical cause | Mitigation |
|---|---:|---|---|

## Phase 7: Submission Gate

Do not submit until all are true:

- No leakage warning remains in limitations.
- Test metrics are held-out.
- Claim audit has no unsupported high-risk phrases.
- DXF report covers more than cherry-picked examples.
- Baselines were evaluated under the same protocol, or literature values are clearly marked as non-comparable.

## Current Status

Already installed:

- split generator;
- layout metric evaluator;
- DXF validator;
- risky-claim auditor;
- example JSONL schema;
- strict protocols.

Still needed from the research pipeline:

- actual `metadata/plans.jsonl`;
- leakage-free training/inference outputs;
- held-out prediction JSONL files;
- full test DXF export folder.
