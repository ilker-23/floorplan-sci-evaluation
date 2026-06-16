# Final SCI Tables Template

Use these tables only with held-out test results.

## Table 1. Dataset and Split

| Split | Plans | Mean rooms | Room range | Source | Used for |
|---|---:|---:|---:|---|---|
| Train | TBD | TBD | TBD | RPLAN | Model fitting |
| Validation | TBD | TBD | TBD | RPLAN | Model selection |
| Test | TBD | TBD | TBD | RPLAN | Final reporting only |

Required note:

> The test split was not used for training, hyperparameter tuning, early stopping, threshold selection, or model selection.

## Table 2. Main Held-Out Test Results

| Model/run | Role | mIoU ↑ | Adj-P ↑ | Adj-R ↑ | Adj-F1 ↑ | Overlap excess ↓ | Boundary ↓ | Area MAPE ↓ | Conn. valid ↑ | Use in paper |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Oracle GT copy | Sanity check | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Sanity only |
| Nearest-neighbor train-program signature | Baseline | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Main baseline |
| Program-template train median | Baseline | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Main baseline |
| Legacy GNN + program edges | Diagnostic/candidate | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Use only if leakage-free |
| Legacy GNN + GT-spatial edges | Leakage diagnostic | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Upper-bound diagnostic only |
| Retrained leakage-free GNN | Candidate | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Main model only if it beats baselines |

## Table 3. Ablation Study

| Configuration | mIoU ↑ | Adj-F1 ↑ | Overlap ↓ | Boundary ↓ | Area MAPE ↓ |
|---|---:|---:|---:|---:|---:|
| Full model | TBD | TBD | TBD | TBD | TBD |
| Without target room size | TBD | TBD | TBD | TBD | TBD |
| Without GIoU | TBD | TBD | TBD | TBD | TBD |
| Without adjacency loss | TBD | TBD | TBD | TBD | TBD |
| Without overlap/OOB loss | TBD | TBD | TBD | TBD | TBD |

## Table 4. Room-Count Stratification

| Room count | n | mIoU ↑ | Adj-F1 ↑ | Overlap ↓ | Boundary ↓ | Level-1 screen pass ↑ |
|---|---:|---:|---:|---:|---:|---:|
| 4-5 | TBD | TBD | TBD | TBD | TBD | TBD |
| 6-7 | TBD | TBD | TBD | TBD | TBD | TBD |
| 8+ | TBD | TBD | TBD | TBD | TBD | TBD |

## Table 5. DXF Validation

| Metric | Held-out test value |
|---|---:|
| DXF files evaluated | TBD |
| Export success rate | TBD |
| Mean entities per file | TBD |
| Closed polyline rate | TBD |
| Mean room layers | TBD |
| Files with wall layer | TBD |
| Median file size | TBD |

## Table 6. Architectural Screening

| Rule | Violation rate | Interpretation |
|---|---:|---|
| Room overlap | TBD | Spatial conflict |
| Boundary violation | TBD | Layout outside frame/boundary |
| Excess aspect ratio | TBD | Implausible room proportion |
| Minimum area | TBD | Only if metric scale is available |
| Disconnected graph | TBD | Circulation/topology failure |
| Isolated service room | TBD | Functional access failure |

## Table 7. Failure Modes

| Failure mode | Frequency | Typical cause | Mitigation |
|---|---:|---|---|
| Small auxiliary room displacement | TBD | Weak constraints for small spaces | Add weighted loss for service rooms |
| Room overlap | TBD | Adjacency loss overpowering overlap penalty | Keep overlap/OOB active in topology stage |
| Boundary protrusion | TBD | Box center/size bounded separately | Boundary-aware parameterization |
| Missing adjacency | TBD | Program graph under-constrained | Stronger edge/contact loss |
| Awkward circulation | TBD | No corridor/access reasoning | Add circulation graph constraint |
