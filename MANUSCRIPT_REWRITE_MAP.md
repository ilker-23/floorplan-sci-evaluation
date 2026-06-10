# Manuscript Rewrite Map

## Current Manuscript Problem

The manuscript is promising, but it currently mixes three levels of claim:

1. What is proven: box-level layout placement can be learned and exported as DXF polylines.
2. What is plausible but not fully proven: topology-aware graph conditioning improves layout validity.
3. What is not proven yet: code-conformant, constructible, drafting-ready post-disaster housing plans.

The SCI version must stay almost entirely in level 1 and level 2.

## Recommended Abstract Skeleton

Automated residential layout placement requires translating a room program into a geometrically coherent arrangement while preserving user-specified adjacencies. We present a program-conditioned GATv2 framework that predicts room bounding boxes from room labels, target sizes, and an adjacency graph. The model is trained with a topology-aware objective combining box regression, Generalized-IoU, adjacency compliance, overlap, and boundary penalties. Predicted layouts are converted into semantic masks for optional adversarial rendering and exported as editable, layer-separated DXF layout skeletons. Evaluation on a frozen held-out RPLAN test split reports spatial accuracy, adjacency recovery, overlap, boundary violation, area error, connectivity validity, and DXF structural validity. The results show that graph-attention placement with explicit architectural penalties supports rapid early-stage layout exploration, while remaining limited to preliminary layout skeletons rather than complete code-compliant construction drawings.

## Replace These Claims

| Current phrase | Replace with |
|---|---|
| CAD-ready plan | editable layer-separated DXF layout skeleton |
| drafting-ready layout | editable preliminary layout |
| code-conformant layouts | geometrically structured layouts |
| constructible alternatives | candidate layout alternatives |
| by construction keeps every room inside | bounds parameters; OOB penalties discourage protrusion |
| superiority over SOTA | competitive under reported metrics; direct comparison requires unified protocol |

## Add These Limitations

1. The system predicts room layout skeletons, not complete architectural drawings.
2. It does not validate building codes, seismic requirements, structural systems, or accessibility.
3. If target room sizes are input, the task is placement-conditioned on a supplied program, not full program generation.
4. FID is secondary because natural-image features are imperfect for architectural drawings.
5. DXF validity means structurally editable geometry, not construction-document completeness.

## Reviewer Attack Points and Preemptive Answers

### Attack: Your graph leaks ground-truth geometry.

Answer only if fixed:

> The final protocol constructs graph edges exclusively from user-specified program adjacencies. No target coordinates, box contacts, or relative directions derived from the reference layout are used as model input.

### Attack: Your results are on training data.

Answer only if fixed:

> All reported final results are computed on a frozen held-out test split. Validation was used only for model selection and threshold tuning.

### Attack: FID is not meaningful for floor plans.

Answer:

> We report FID only as a secondary visual-distribution indicator and base the main conclusions on layout-specific metrics: mIoU, adjacency F1, overlap ratio, boundary violation, area error, connectivity, and DXF validity.

### Attack: DXF output is not a real construction drawing.

Answer:

> We therefore describe the output as an editable layout skeleton. The system does not claim construction-document completeness, code compliance, or structural validity.
