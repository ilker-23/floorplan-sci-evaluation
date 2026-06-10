# DXF Validation Protocol

## Claim Discipline

The current DXF outputs support the phrase:

> editable layer-separated DXF layout skeleton

They do not yet support:

- complete CAD drawing;
- construction drawing;
- code-compliant plan;
- drafting-ready architectural plan.

Those stronger claims require doors, windows, wall thicknesses, openings, dimensions, circulation logic, and preferably CAD-software validation.

## Required DXF Evidence

For every held-out test plan exported to DXF, measure:

1. Export success rate.
2. Number of closed polylines.
3. Number of room layers.
4. Whether each expected room has a layer/entity.
5. Self-intersection count if supported by downstream geometry tooling.
6. Out-of-bounds entities.
7. Non-axis-aligned entity count.
8. File openability in at least one CAD viewer, if available.

## Minimum Manuscript Table

| Metric | Value |
|---|---:|
| DXF export success | TBD |
| Mean entities per file | TBD |
| Closed room-polyline rate | TBD |
| Layer consistency | TBD |
| Non-axis-aligned entities | TBD |
| Median file size | TBD |

## Supplementary Material

Include at least 20 DXF examples from the held-out test set:

- 5 high-IoU;
- 10 median-IoU;
- 5 low-IoU/failure cases.

Do not include only the best examples.
