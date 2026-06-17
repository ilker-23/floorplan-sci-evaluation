# 24-48 Hour Q1 Evidence Pack

This is the minimum pack to prepare before rewriting the manuscript.

## Claim Gate

Final claim:

> Leakage-free graph-conditioned vector layout prediction for residential floor
> plans, evaluated under architectural validity metrics and exported as editable
> DXF layout skeletons.

Do not claim:

- code compliance;
- construction readiness;
- deployable housing plans;
- superiority over literature values measured under different protocols.

## Main Result Table

| Run | Role | mIoU | Adj-F1 | Overlap excess | Boundary | Area MAPE | Connectivity | Use in paper |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Oracle GT copy | sanity check | TBD | TBD | TBD | TBD | TBD | TBD | sanity only |
| Nearest-neighbor train signature | baseline | TBD | TBD | TBD | TBD | TBD | TBD | main baseline |
| Program-template train median | baseline | TBD | TBD | TBD | TBD | TBD | TBD | main baseline |
| Legacy GNN with GT-spatial edges | diagnostic | TBD | TBD | TBD | TBD | TBD | TBD | leakage diagnostic only |
| Legacy GNN with program edges | diagnostic/candidate | TBD | TBD | TBD | TBD | TBD | TBD | only if leakage-free |
| Retrained leakage-free GNN | candidate | TBD | TBD | TBD | TBD | TBD | TBD | main model if it beats baseline |
| GATv2 complete type-pair graph | candidate | TBD | TBD | TBD | TBD | TBD | TBD | use if it beats baselines without topology collapse |
| GATv2 hybrid program/type graph | candidate | TBD | TBD | TBD | TBD | TBD | TBD | strongest candidate if both mIoU and topology improve |

## Minimum Qualitative Figure

Use randomly selected test plans:

- 4 good cases;
- 4 median cases by mIoU;
- 4 low-tail failure cases.

Each case should show:

- ground truth;
- nearest-neighbor baseline;
- program-template baseline;
- leakage-free candidate;
- DXF skeleton if exported.

## Failure Modes

| Failure mode | Evidence metric | Likely cause | Required wording |
|---|---|---|---|
| Excess room overlap | overlap_excess_ratio | weak collision penalty or copied GT overlap structure | not constructible |
| Boundary protrusion | boundary_violation_ratio | center/size not jointly bounded | layout skeleton only |
| Missing adjacency | adj_f1, ged_simple | program graph under-constrained | topology incomplete |
| Low connectivity | connectivity_valid_rate | contact graph not recovered | circulation not solved |
| Small room distortion | area_mape, aspect_error | room-size conditioning insufficient | requires architectural post-processing |

## Reviewer Response Readiness

Prepare direct answers to these questions:

1. What exactly is the model allowed to see at inference time?
2. Are any edges or positions derived from ground-truth geometry?
3. Which split was used for early stopping?
4. Which result is the final held-out result?
5. Why are oracle and GT-spatial results not main claims?
6. What does DXF validation prove, and what does it not prove?
