# SCI Evaluation System for GNN-GAN Floor-Plan Research

This folder is the hard gate before any Elsevier/SCI submission. Its purpose is to stop the manuscript from relying on attractive figures or optimistic numbers, and to force every claim through a reproducible protocol.

## What This System Enforces

1. Leakage-free evaluation: no reference-geometry-derived graph edges may be used as model input in the final protocol.
2. Held-out reporting: final numbers must come from a frozen test split, not the training split.
3. Domain-specific metrics: mIoU and FID are not enough for floor plans.
4. DXF evidence: CAD-readiness must be measured, not only shown in screenshots.
5. Claim discipline: terms such as "constructible", "code-conformant", and "drafting-ready" are forbidden unless directly validated.

## Folder Structure

- `protocols/leakage_free_protocol.md`: final experimental protocol.
- `protocols/evaluation_metrics.md`: exact metric definitions and reporting rules.
- `protocols/dxf_validation_protocol.md`: what CAD-ready is allowed to mean.
- `configs/layout_records.example.jsonl`: expected JSONL format for ground truth and predictions.
- `configs/split_config.example.json`: split settings template.
- `configs/architectural_rules.example.json`: preliminary architectural screening rules.
- `colab/COLAB_RPLAN_WORKFLOW.md`: Google Drive/Colab workflow for the real RPLAN experiments.
- `colab/inspect_drive_dataset.py`: inventories the Drive dataset before conversion.
- `colab/rplan_to_sci_jsonl_template.py`: editable converter template for RPLAN/Graph2Plan-style data.
- `scripts/make_splits.py`: deterministic train/validation/test split generator.
- `scripts/evaluate_layout_metrics.py`: layout metric evaluator for JSONL prediction files.
- `scripts/evaluate_architectural_rules.py`: geometric and preliminary architectural screening.
- `scripts/validate_dxf.py`: dependency-free DXF structural validator.
- `scripts/audit_manuscript_claims.py`: searches the manuscript for risky unsupported claims.
- `reports/`: place generated metric reports here.
- `templates/final_tables.md`: final SCI table shells.
- `templates/results_section_skeleton.md`: final Results section structure.

## Minimum Acceptable SCI Evidence Package

Before submission, produce:

1. `reports/split_manifest.json`
2. `reports/layout_metrics_test.json`
3. `reports/layout_metrics_by_room_count.csv`
4. `reports/dxf_validation_report.json`
5. A revised manuscript table reporting `mean +- std` over at least 3 seeds or clearly over test examples.

## Non-Negotiable Rule

If the final model still uses reference-geometry-derived edges as input, the paper must not claim program-conditioned generation. It can only claim reconstruction under geometry-derived graph conditioning, which is much weaker.
