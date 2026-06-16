# Q1 Comparison Protocol

This protocol exists to keep the manuscript honest when comparing against
published or highly visible floor-plan generation systems.

## Comparator 1: FloorplanGAN

FloorplanGAN is strong because it makes a narrow claim and supports it with a
coherent experiment package:

- vector-format residential floor-plan generation;
- raster discrimination through differentiable rendering;
- fixed six-room residential subset from RPLAN;
- DCGAN and SAGAN raster baselines;
- distribution-level evaluation, nearest-neighbor classifier, ROC, PCA-style
  domain features, and a professional user study;
- explicit limitations around room count, bounding boxes, and residential scope.

The lesson for this project is not "copy the architecture". The lesson is:

> A Q1 paper survives because the problem statement, input assumptions, output
> representation, evaluation metrics, and limitations all match each other.

## Comparator 2: Floor Plan Generation Using GNNs

The referenced GNN repository is closer to this project technically but is not a
complete Q1 evidence package by itself. It uses a two-stage idea:

- CNN stage for room centroid prediction;
- GAT-Net stage for room width and height estimation;
- boundary graph plus room graph;
- living-to-all edges because the CNN centroid output does not provide true
  room connections.

Reviewer warning:

> If centroids or spatial relations from the target layout are given to the
> model, the task is layout completion or size estimation, not unconstrained
> floor-plan generation.

## Required Positioning for Our Study

Use this positioning unless stronger leakage-free results prove otherwise:

> Leakage-free graph-conditioned vector layout prediction and evaluation for
> residential floor plans, with editable DXF layout-skeleton export.

Avoid these claims unless separately validated:

- construction-ready design;
- full architectural drafting;
- building-code compliance;
- general floor-plan generation for arbitrary building types;
- superiority over FloorplanGAN, Graph2Plan, House-GAN, or HouseDiffusion when
  protocols differ.

## Fatal Reviewer Risks

Any of the following can justify rejection:

- final results use graph edges derived from ground-truth geometry;
- final results use target centroids, target relative directions, or target grid
  cells as model inputs;
- test-set examples were selected manually for qualitative figures only;
- paper reports only model loss or image quality without architectural metrics;
- oracle or diagnostic results are mixed into the main result table;
- DXF output is called CAD-ready or construction-ready without validation.

## Minimum Q1 Evidence Pack

The 24-48 hour rescue package must contain:

1. Frozen train/validation/test split.
2. Oracle copy sanity check.
3. Nearest-neighbor in-house baseline.
4. Program-template in-house baseline.
5. Legacy/leaked model reported only as diagnostic.
6. Leakage-free candidate model on the held-out test split.
7. Main table with mIoU, adjacency F1, overlap excess, boundary violation,
   area MAPE, and connectivity.
8. Stratified table by room count.
9. Random qualitative grid including good, median, and poor cases.
10. Failure-mode table with explicit causes and planned mitigation.

## Decision Rule

If the leakage-free model does not beat the in-house baselines, do not frame the
paper as a new state-of-the-art generator. Reframe it as:

- a leakage audit;
- a reproducible evaluation protocol;
- a vector/DXF layout-skeleton benchmark;
- a negative-result-informed roadmap for graph-conditioned floor-plan models.

This is less glamorous, but much more defensible.
