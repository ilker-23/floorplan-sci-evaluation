# Leakage-Free Experimental Protocol

## Hard Diagnosis

The current manuscript is scientifically promising but not submission-ready if:

- graph edges are derived from the ground-truth geometry;
- reported metrics are computed on the training split;
- baseline values are copied from original papers under different protocols.

Any one of these is enough for a serious reviewer to question the paper. The first two are fatal unless fixed.

## Final Problem Definition

Use this exact framing:

> Program-conditioned residential layout placement with editable DXF export.

Avoid these framings unless separately validated:

- unconditional floor-plan generation;
- code-conformant design;
- constructible plan generation;
- complete architectural drafting.

## Allowed Inputs

The final model may receive:

- room type labels;
- target room area or target width/height if explicitly declared as part of the design program;
- user-specified adjacency graph;
- optional building boundary if supplied by the user or dataset protocol before seeing target room placement.

The final model must not receive:

- adjacency edges extracted from ground-truth box contact unless the task is explicitly called reconstruction;
- relative directions extracted from target geometry;
- node positions, center coordinates, or grid cells derived from the target layout;
- any test-set statistic used to tune hyperparameters.

## Recommended Split

Use a deterministic frozen split:

- train: 70%
- validation: 15%
- test: 15%

If plan families, augmentations, or near-duplicates exist, split by group/family, not by individual file.

## Model Selection

Validation set may be used for:

- choosing epoch;
- choosing loss weights;
- choosing threshold parameters;
- early stopping.

Test set may be used only once for final reporting.

## Baseline Requirement

At minimum, report in-house baselines under the same split and metrics:

1. MLP room-placement baseline.
2. GCN.
3. GAT.
4. GATv2 without adjacency loss.
5. GATv2 without target size input.
6. Full GATv2 objective.

If House-GAN, House-GAN++, Graph2Plan, or HouseDiffusion values are copied from papers, mark them as "reported literature values, not directly comparable". They cannot be used as proof of superiority.

## Final Manuscript Language

Allowed:

- "editable layer-separated DXF layout skeleton"
- "early-stage design support"
- "rapid layout exploration"
- "program-conditioned placement"

Not allowed without extra validation:

- "constructible"
- "code-conformant"
- "drafting-ready"
- "building-code compliant"
- "seismic safety"
- "deployment-ready"

## Required Final Statement

The methods section must contain:

> All final metrics were computed on a held-out test split that was not used for training, model selection, hyperparameter tuning, threshold selection, or early stopping.
