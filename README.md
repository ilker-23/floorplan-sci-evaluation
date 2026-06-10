# Floor Plan SCI Evaluation System

This repository contains the evaluation and manuscript-support system for a program-conditioned residential floor-plan layout generation study.

The goal is not to make optimistic figures. The goal is to make the work survive a serious SCI/Elsevier review.

## What This Repository Does

- Defines a leakage-free experimental protocol for RPLAN/Graph2Plan-style floor-plan data.
- Converts Colab/Google Drive dataset workflows into reproducible JSONL records.
- Generates deterministic train/validation/test splits.
- Evaluates layout-specific metrics beyond FID.
- Screens preliminary architectural validity.
- Validates DXF layout-skeleton exports.
- Audits manuscript text for risky unsupported claims.
- Provides final SCI table and results-section templates.

## Start Here

Read:

1. `SCI_HARD_REVISION_PLAN.md`
2. `NEXT_EXPERIMENT_STEPS.md`
3. `colab/COLAB_RPLAN_WORKFLOW.md`
4. `notebooks/rplan_inventory_and_split_colab.ipynb`

## Core Scripts

```bash
python scripts/make_splits.py --help
python scripts/validate_layout_jsonl.py --help
python scripts/evaluate_layout_metrics.py --help
python scripts/evaluate_architectural_rules.py --help
python scripts/validate_dxf.py --help
python scripts/audit_manuscript_claims.py --help
```

## Local Smoke Test

Run this before pushing changes:

```bash
python -m py_compile scripts/*.py colab/*.py tests/smoke_test.py
python tests/smoke_test.py
```

The smoke tests use tiny fixtures in `tests/fixtures/`. They do not validate scientific performance; they only confirm that the evaluation tools still run and produce structurally sensible outputs.

## Expected Data Format

The canonical layout format is JSONL:

```json
{"plan_id":"plan_000001","family_id":"family_000001","rooms":[{"id":"r1","type":"LivingRoom","box":[0.10,0.10,0.45,0.45]}],"edges":[["r1","r2"]]}
```

Boxes use normalized `[x1, y1, x2, y2]` coordinates unless a script explicitly states otherwise.

## Scientific Boundary

The system supports claims about:

- editable DXF layout skeletons;
- geometric layout validity;
- program-conditioned room placement;
- preliminary early-stage design support.

It does not, by itself, support claims about:

- construction drawings;
- building-code compliance;
- seismic safety;
- deployable post-disaster housing plans.

Those require additional architectural, regulatory, and structural validation.
