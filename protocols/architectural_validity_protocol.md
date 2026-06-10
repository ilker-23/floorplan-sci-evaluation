# Architectural Validity Protocol

This protocol defines what we can responsibly claim as floor-plan design quality. It separates geometric validity from architectural validity and prevents the manuscript from overclaiming.

## Validity Levels

### Level 1: Geometric Layout Validity

A plan satisfies Level 1 if:

- room boxes are inside the canvas or declared boundary;
- room overlaps are below a declared tolerance;
- required graph adjacencies are recovered as physical contacts;
- the recovered graph is connected;
- room sizes are close to the supplied program.

This is the current realistic target for the GNN-GAN system.

### Level 2: Preliminary Architectural Plausibility

A plan satisfies Level 2 if, in addition to Level 1:

- circulation has a plausible access path to major rooms;
- wet spaces are reasonably grouped or adjacent to service zones where applicable;
- bedrooms are not accessible only through unrelated private rooms;
- auxiliary spaces are not isolated;
- room proportions are within acceptable ranges;
- minimum approximate residential room areas are not violated.

This can be partially automated and partially assessed by experts.

### Level 3: Constructability / Code Compliance

A plan satisfies Level 3 only if it includes:

- walls with thickness;
- doors and openings;
- windows or facade logic;
- structural grid or load-bearing strategy;
- accessibility constraints;
- local building-code checks;
- seismic/design-code constraints.

The current system does not reach Level 3. Do not claim it.

## Automated Rule Checks

The `evaluate_architectural_rules.py` script checks only what can be inferred from the JSONL layout representation:

- minimum room area if metric area information is available;
- maximum aspect ratio;
- overlap and boundary issues;
- adjacency graph connectivity;
- required public/private/service adjacency patterns if configured.

## Recommended Turkish Residential Minimum-Area Placeholders

These are placeholders for screening, not a legal code:

| Room type | Suggested minimum area |
|---|---:|
| LivingRoom | 16 m2 |
| Kitchen | 7 m2 |
| MasterRoom | 12 m2 |
| Bedroom / ChildRoom / SecondRoom | 9 m2 |
| Bathroom | 3 m2 |
| WC | 1.5 m2 |
| Corridor / Hall | 3 m2 |
| Balcony | 2 m2 |
| Storage | 1.5 m2 |

If the dataset has no metric scale, report these checks as unavailable instead of pretending normalized pixels imply real square meters.

## Expert Review Criteria

For SCI, use expert review only after the automated checks:

1. Functional validity.
2. Circulation clarity.
3. Room proportion quality.
4. Wet-zone/service logic.
5. Drawing readability.
6. Overall early-stage design usefulness.

Do not ask experts whether the plan is "buildable" unless structural and code information is present.

## Manuscript Claim Rule

If only Level 1 is validated:

> The system produces geometrically valid, editable preliminary layout skeletons.

If Level 1 plus partial Level 2 is validated:

> The system supports early-stage architectural layout exploration.

Never write:

> The system produces constructible, code-compliant housing plans.
