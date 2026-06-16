# Results Section Skeleton

Use this after the held-out Colab experiment is complete.

## 4. Results

### 4.1. Dataset Split and Experimental Protocol

Report the frozen split, number of plans, room-count distribution, and the rule that the test split was never used for model selection.

Required sentence:

> All final results are computed on the held-out test split. The validation split was used for model selection and hyperparameter tuning; the test split was used only once for final reporting.

### 4.2. Main Quantitative Results

Lead with layout-specific metrics, not FID.

Interpret:

- mIoU: spatial placement accuracy;
- adjacency F1: program compliance;
- overlap/boundary: geometric validity;
- area MAPE: room-program preservation;
- connectivity: usable topology.

Separate roles explicitly:

- oracle copy is a sanity check;
- nearest-neighbor and program-template runs are in-house baselines;
- any model that receives GT-spatial edges, GT directions, or GT centroids is a
  diagnostic/upper-bound run;
- only leakage-free held-out test results can support the final claim.

### 4.3. Ablation Analysis

The ablation must answer:

1. Is GATv2 better than simpler graph encoders?
2. Does GIoU improve placement?
3. Does adjacency loss improve topological compliance?
4. Do overlap/OOB penalties prevent invalid plans?
5. How much does target-size input simplify the task?

### 4.4. Architectural Screening

Report Level-1 and partial Level-2 validity. Be strict:

> These checks screen for geometric and preliminary architectural plausibility; they do not certify constructability or code compliance.

### 4.5. DXF Export Validation

Report structural DXF validity:

- closed polylines;
- layer separation;
- export success;
- median file size;
- examples from high, median, and low IoU cases.

Do not call the output a construction drawing.

### 4.6. Failure Analysis

Show bad cases honestly. Minimum failure modes:

- small room displacement;
- overlap;
- boundary protrusion;
- missing adjacency;
- awkward circulation.

Strong paper behavior:

> The lower tail is not hidden; it is analyzed.

### 4.7. Discussion

Discuss why the model works, where it fails, and what is architecturally still missing.

Keep post-disaster framing as motivation, not as proof of deployability.
