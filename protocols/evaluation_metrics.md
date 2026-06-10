# Evaluation Metrics Protocol

## Primary Metrics

These are the metrics that should carry the scientific claim.

### 1. Box mIoU

Mean Intersection-over-Union between predicted and target room boxes, matched by room instance id.

Report:

- mean +- standard deviation over test plans;
- median;
- 25th and 75th percentiles;
- percentage above 0.50 and 0.70.

### 2. Adjacency Precision, Recall, and F1

Recover predicted adjacency by room box contact. Compare with the input adjacency graph.

Report:

- precision: predicted contacts that are required by graph;
- recall: required graph edges recovered as contacts;
- F1: harmonic mean.

This is more important than FID for a graph-conditioned floor-plan model.

### 3. Boundary Violation Rate

Fraction of room boxes extending outside the normalized canvas or supplied boundary.

Report both:

- percentage of plans with any violation;
- mean violation area ratio.

### 4. Overlap Ratio

Mean pairwise room overlap area divided by total predicted room area.

Report:

- mean overlap ratio;
- percentage of plans with any non-trivial overlap.

### 5. Room Area Error

Mean absolute percentage error between predicted and target room areas.

If room sizes are input, this metric is mandatory because it checks whether the model preserves the supplied program.

### 6. Connectivity Validity

Whether the recovered room adjacency graph is connected, excluding optional exterior/balcony nodes if the protocol defines them as optional.

Report:

- percentage of valid connected plans;
- room-count-stratified validity.

## Secondary Metrics

### FID

Allowed only as a relative visual-quality indicator. Do not use FID as the main claim because Inception-v3 is trained on natural images, not architectural drawings.

### Manhattan Compliance Score

Useful only if computed on generated raster drawings or DXF geometry from all compared methods. If the representation is axis-aligned by construction, high MCS is a format property, not a learned achievement.

### Graph Edit Distance

Acceptable only if graph recovery rules are fully specified:

- contact threshold;
- overlap handling;
- whether doors or mere wall contact define edges;
- node substitution cost;
- edge insertion/deletion cost.

## Reporting by Difficulty

Every final table should include room-count stratification:

- 4-5 rooms;
- 6-7 rooms;
- 8+ rooms.

If the model fails mainly on small auxiliary rooms, report this instead of hiding it in the mean.

## Minimum Tables for SCI Manuscript

1. Main held-out test metrics table.
2. Ablation table.
3. Room-count stratified table.
4. DXF validity table.
5. Failure-mode table.
