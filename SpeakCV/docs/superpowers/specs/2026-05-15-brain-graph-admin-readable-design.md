# Brain Graph Redesign for Admin Readability

## Context
Current AI Brain graph in Admin Config is hard to read because labels overlap, edge density is visually noisy, and the initial view does not provide a fast overview for operational decisions.

## Goal
Make the graph readable-first for admin workflows while preserving relationship correctness and adding practical interaction for investigation.

## Non-Goals
- Not replicating decorative GNN demo visuals exactly.
- Not introducing advanced analytics or model-level graph science.
- Not changing ingestion business logic.

## Design Principles
1. Overview first, details on demand.
2. Reduce cognitive load by default.
3. Preserve relationship fidelity when drilling down.
4. Keep interactions predictable and reversible.

## Information Architecture
### Default screen behavior
- Show overview metrics immediately: total nodes, total edges, cluster count.
- Render graph with low-noise defaults.
- Auto-focus broad structure, not a specific dense subgraph.

### Progressive disclosure
- Default label mode: show short labels only for top-N important nodes.
- Full text shown in tooltip/details panel on hover/click.
- Dense information moved out of the canvas into side details.

## Visual Model
### Layout engine
- Replace static circular layout with force-directed layout.
- Apply gentle center gravity to keep clusters in view.
- Freeze simulation after stabilization to avoid motion distraction.

### Node encoding
- Color by semantic type cluster (`principle`, `rubric`, `red_flag`, `follow_up_strategy`, `question_pattern`, `domain_knowledge`).
- Size by importance score (degree + optional weight contribution).
- Top-N nodes are eligible for default labels.

### Edge encoding
- Thin, low-opacity edges by default.
- Increase opacity/thickness only for focused neighborhood.
- Keep relation type in tooltip/details, not always on-canvas.

## Interaction Design
### Hover
- Show tooltip with: full label/content snippet, type, confidence, degree.

### Click node
- Focus 1-hop neighborhood.
- Dim unrelated nodes/edges.
- Sync selected node to candidate list row.

### Filters
- Toggle chips by node type.
- Optional confidence threshold slider.
- “Reset view” button to restore overview state.

### Navigation controls
- Zoom in/out and pan.
- Fit-to-screen action.
- Reset camera to initial overview.

## Component Architecture
- `BrainGraphPanel`: graph canvas + controls.
- `BrainGraphLegend`: type-color mapping + counts.
- `BrainGraphDetails`: selected node metadata and related edges.
- `brainGraphAdapter`: transform `jobData.candidates` to normalized graph model.

## Data Contract (UI side)
### Node (derived)
- `id`
- `type`
- `labelShort`
- `labelFull`
- `confidence`
- `degree`
- `importanceScore`

### Edge (derived)
- `id`
- `source`
- `target`
- `relationType`
- `confidence`

### Derived sets
- `topLabelNodeIds`
- `visibleNodeIds` (after filters)
- `focusedNeighborhoodIds`

## Performance Strategy
- Debounce expensive recomputation for filters.
- Recompute layout only when graph dataset changes materially.
- Freeze physics after settle.
- Fallback mode for large datasets: cap rendered edges to top-K by confidence until user zooms/focuses.

## Accessibility
- Keyboard accessible controls (filters/reset/zoom).
- Color is not the only indicator (selection halo + details text).
- Minimum contrast preserved for labels and controls.
- Tooltip info mirrored in details panel for non-hover users.

## Responsive Behavior
- Desktop (`lg+`): 3/9 split (controls/graph).
- Tablet/mobile: stack controls over graph, keep graph height stable with internal scrolling.
- Prevent horizontal overflow from breaking page layout.

## Acceptance Criteria
1. Admin can understand high-level graph structure in under 3 seconds on first load.
2. Label overlap is substantially reduced versus current implementation.
3. Clicking a node clearly reveals its direct neighborhood.
4. Type filtering updates graph without jank.
5. Reset returns to clean overview state reliably.

## Risks and Mitigations
- Risk: Force layout jitter causes distraction.
  - Mitigation: freeze after settle + reset button.
- Risk: Too much hidden detail reduces trust.
  - Mitigation: details panel + candidate list sync.
- Risk: Large graph performance drops.
  - Mitigation: edge capping fallback and selective emphasis.

## Rollout Plan (Design-Level)
1. Introduce adapter + component split.
2. Integrate force layout with current dataset.
3. Add focus/filter/reset interactions.
4. Tune defaults (top-N labels, edge opacity, node size scale).
5. Validate with real seed files and admin workflow checks.

## Success Metrics
- Reduced time-to-understand in internal usability checks.
- Fewer complaints about “graph looks wrong/noisy.”
- Faster publish-review cycles in admin usage.
