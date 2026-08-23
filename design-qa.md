# StopWatch Editorial Design System QA

## Evidence

- Source visual truth: `design/ticktick-focus-editorial-reference.png`
- Rendered implementation preview: `design/ticktick-focus-editorial-preview.png`
- Side-by-side comparison: `design/ticktick-focus-design-qa-comparison.png`
- Five-face context sheet: `design/stopwatch-ui-preview.png`
- Source dimensions: 1254 × 1254 pixels, normalized to 466 × 466 for comparison.
- Implementation dimensions: 466 × 466 pixels at a 466 × 466 CSS viewport and density 1.
- State: TickTick positive stopwatch running at `01:42:18`; countdown ready at `25分钟`.
- Browser verification: local HTML wrappers rendered both previews with no console errors.
- Five-face migration preview: `design/stopwatch-ui-preview.png`
- Migration before/after comparison: `design/stopwatch-ui-language-migration-comparison.png`
- Provider icon source/implementation comparison: `design/provider-icon-design-qa-comparison.png`
- Provider reset-copy before/after comparison: `design/provider-reset-copy-design-qa-comparison.png`
- Prepared 96 × 96 device assets: `design/assets/codex-brand-icon-96.png` and
  `design/assets/claude-brand-icon-96.png`, extracted from the locally installed Codex and Claude
  desktop applications and converted to indexed PNGs with transparency.
- Individual 466 × 466 captures: `clock-editorial-preview.png`, `focus-editorial-preview.png`,
  `codex-editorial-preview.png`, `claude-editorial-preview.png`, and
  `typeless-editorial-preview.png` in the `design` directory.
- Status safe circle: the complete `专注 / 进行中` text-group bounds (`84 × 72`) are contained
  inside the 209-pixel inner radius; the red disc begins after the full label width.
- Visual safe circle: both action-button rectangles and all four corners are contained inside the
  209-pixel inner radius centered at `(225, 225)` in the 450-pixel firmware design frame.
- Touch safe circle: the expanded primary `182 × 66` and end `76 × 66` hit rectangles are contained
  inside the 225-pixel physical radius and dispatch the current stopwatch/countdown action.

## Four-face Design Language Migration

- Clock: replaces the dark segmented ring with a warm-white time poster. Weather, focus progress,
  Codex remaining quota, and Claude remaining quota remain visible; `星盘` and `成果` retain their
  original routes in two 118 × 48 controls with larger invisible hit rectangles.
- Codex: makes remaining quota the hero value and uses the dedicated blue-violet Codex brand icon
  inside the existing 96 × 96 task-detail touch slot. A subtle scale pulse preserves live status
  feedback without returning to the generic robot placeholder.
- Claude: shares the Codex hierarchy with a provider-specific orange accent, preserving the real
  Claude desktop-app icon, quotas, usage, reset time, and transcript route when a task is active.
- Typeless: turns the recording state into a `LIVE / READY / ERROR` hero, keeps the real waveform
  and peak value, and provides one clear microphone action inside the existing central touch zone.
- Shared geometry: every header uses the same `104 × 72` safe bounds; clock actions and all provider
  and voice footer controls are mathematically contained in the 209-pixel visual radius. Expanded
  clock, provider-icon, and voice hit regions are contained in the 225-pixel physical radius.
- Browser QA: the old sheet and the final sheet were combined into one same-state comparison, then
  each final face was cropped at exactly 466 × 466 to inspect the circular boundary.
- Provider reset copy: the shared Codex/Claude idle footer now renders `↺3d8h` instead of the
  sentence-length reset label. Active, waiting, and error states plus the existing 96 × 96 touch
  geometry remain unchanged. The `↺` glyph is included in the embedded Noto UI font, so the device
  build does not depend on a browser fallback.
- Validation: 73 main dashboard tests, 22 companion tests, and the standalone C++ interaction test
  pass. The UAC `firmware.bin` builds successfully at 4,528,368 bytes with SHA-256
  `7ef414487d37ed1e5d3df043c19fb282ffb6eee8e93b134a51a3b61cceb2945b`.
- Device boundary: no upload, flash, erase, or device write was performed in this migration round.

## Full-view Comparison

The side-by-side image preserves the selected direction's dominant hierarchy: warm white base,
cropped coral-red disc, oversized black timer, compact A/B mode strip, and a black primary action.
The corrected implementation keeps the complete button silhouettes inside the inner round safe
area while using larger, invisible hit rectangles for reliable touch input.

No separate focused crop was needed because the complete 466-pixel screen and all labels remain
legible in the 932 × 466 comparison image.

## Findings

- No actionable P0, P1, or P2 differences remain after the status and action safe-area corrections.
- Provider icon QA passes at the exact 96 × 96 device slot and within complete 466 × 466 round-screen
  captures. Both brand marks remain legible, stay clear of the hero values and headings, and keep the
  original provider-detail hit geometry unchanged.
- Provider reset-copy QA passes in the Claude idle state at 466 × 466: `↺3d8h` remains centered,
  leaves clear footer whitespace, and does not change the Codex/Claude interaction contract.
- [P3] The generated reference uses a more condensed display face than the embedded runtime can
  guarantee. The browser preview uses an available heavy grotesk fallback; firmware uses M5GFX
  `Font8` for the hero timer and the embedded Noto UI font for Chinese labels. Confirm optical
  weight on the physical AMOLED before final font calibration.
- [P3] The reference's soft red shading is intentionally reduced to a solid coral token for a
  cleaner flat style and inexpensive embedded rendering.
- The touch control says `结束` and stops with one direct tap; the physical A/B buttons retain their
  existing double-click-to-end safety rule. Touch and hardware inputs share the same existing
  TickTick end route after their respective input gesture is resolved.

## Required Fidelity Surfaces

- Fonts and typography: hierarchy and weight match; exact condensed numerals remain a hardware-only
  P3 calibration item.
- Spacing and layout rhythm: top status, hero timer, selector, and actions remain inside the round
  safe area with clear vertical grouping.
- Colors and visual tokens: warm white `#F8F5ED`, ink `#050505`, coral `#FF3B30`, and yellow
  `#FFC400` match the selected direction.
- Image quality and asset fidelity: the selected raster reference is preserved; the production UI
  uses native M5GFX text and geometry at device resolution, avoiding scaled full-screen artwork.
- Copy and content: `专注 / 进行中`, `A 正计时`, `B 25分钟`, `暂停`, and `结束` are visible
  and aligned with the existing input contract.

## Comparison History

1. First render: the top status label was clipped by the circular safe area (P2).
2. First fix: moved the top status anchor and underline inward, but did not yet verify the complete
   leading-glyph bounding box.
3. Owner review caught a remaining P1: the lower action silhouettes crossed the circular visible
   boundary, and the preview had not verified the full rectangles or real touch areas.
4. Second fix: moved the visual action row from `64/318 × 351` to `106/282 × 344`, reduced it to
   `166/62 × 52`, and moved the selector row inward to `52/225 × 282`.
5. Interaction fix: added separate `182 × 66` and `76 × 66` hit rectangles, mathematical circle
   containment checks, and real touch dispatch for stopwatch/countdown start-pause/end.
6. Third render: the full silhouettes, labels, and surrounding black screen edge are visible; the
   geometry and interaction tests pass.
7. Owner review caught a remaining P2: the left strokes of `专` still crossed the top-left circular
   crop even though the text anchor appeared inside the screen.
8. Third fix: moved the complete status group to firmware `x = 124`, lowered its baselines to
   `62 / 92`, added an `84 × 72` inner-circle containment assertion, and shifted the coral disc
   right to keep the full second line on the warm-white field.
9. Fourth render: `专注 / 进行中` and its underline are fully visible with clear circular-edge and
   red-disc separation; the focused 466 × 466 browser capture passes.

## Implementation Checklist

- [x] Replace the dark dashboard ring and twin-card layout.
- [x] Add editorial white/coral/black/yellow visual tokens.
- [x] Make the active timer the single hero value.
- [x] Preserve A/B mode and single-/double-click semantics in the visible controls.
- [x] Keep the full status text bounding box inside the 209-pixel inner safe circle.
- [x] Keep visual action rectangles inside the 209-pixel inner safe circle.
- [x] Keep expanded action hit rectangles inside the 225-pixel physical circle.
- [x] Wire the visible action controls to the existing TickTick routes.
- [x] Verify 466 × 466 round-screen crop in the local browser.
- [x] Run the full Python test suite and the independent C++ interaction test.
- [x] Migrate Clock, Codex, Claude, and Typeless to the same editorial system.
- [x] Preserve clock shortcuts, provider transcript touch, and Typeless mic touch.
- [x] Replace the generic Codex robot and Claude `CL` page placeholders with real provider icons.
- [x] Compare the 96 × 96 source assets and 466 × 466 round-screen renders in one QA artifact.
- [x] Shorten the shared Codex/Claude idle reset label to `↺3d8h` and embed the required glyph.
- [x] Compile the complete UAC firmware without uploading it.
- [ ] Confirm `Font8` optical size and touch feel on the physical AMOLED.

final result: passed

# AI Hotspot + Obsidian Dice QA

## Evidence

- Selected source visual truth: `design/ai-obsidian-selected-reference.png`
- Rendered implementation: `design/ai-obsidian-implementation.png`
- Same-frame source/implementation comparison: `design/ai-obsidian-design-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Comparison normalization: each two-face panel is 1000 × 480 pixels at density 1; every device
  circle uses the production 466 × 466 geometry.
- State: AI alert active for `GPT-6 正式发布`; Obsidian has selected `把控制编进拓扑` from
  `Smart Workspace · Insights` with 312 eligible notes.
- Browser verification: the selected in-app browser rendered the focused two-face view and the full
  seven-face sheet with no console errors.
- Focused evidence: the full 466 × 466 circles are already visible at readable scale in the
  comparison; no secondary crop is needed to judge edge containment or action geometry.

## Full-view Comparison

The implementation preserves the selected direction's warm-white base, blunt black editorial
type, bright coral/yellow generated assets, oversized signal value, and black primary actions.
Content density was reduced to fit the real round display: the AI title becomes `AI 热点 / 尖叫`,
the current headline uses two lines, and secondary actions use the short labels `打开` and `再摇`.

The final proportion pass scales the AI burst from 220 × 220 to 280 × 280 and positions it at
`(185, -5)`. The Obsidian yellow disc now uses the shared editorial accent geometry
`center (364, 130), radius 164`, matching Clock, Focus, Codex, Claude, and Typeless.

Both page headers, feature illustrations, headline/title blocks, metadata, state indicators, and
complete action silhouettes remain inside the round visible area. Primary and secondary touch
rectangles are independently contained in the larger physical touch radius.

## Findings and Fixes

1. First implementation render exposed a P2 asset defect: the indexed dice PNG mapped transparency
   to an opaque yellow palette entry, leaving a black square behind the dice.
2. The asset pipeline now reserves palette index 0 exclusively for transparent pixels and shifts
   all visible colours to indexes 1...255. The feature header was regenerated from the corrected
   files, and the second same-frame comparison shows clean compositing on both pages.
3. Owner review identified a P2 cross-page proportion mismatch: the AI explosion carried less
   colour weight than the other faces, while the Obsidian yellow disc used a smaller, offset
   `radius 144` geometry.
4. The AI asset was enlarged to 280 × 280 without crossing the header or headline, and the yellow
   disc was replaced with the same 164-radius geometry used by the first five faces. The revised
   two-face comparison and seven-face context sheet show consistent accent mass and clean crops.
5. No actionable P0, P1, or P2 visual differences remain. The implementation intentionally removes
   the reference's tiny `开启` status and shake-hint copy to keep touch actions and article/note copy
   dominant at 466 pixels.
6. [P3] Typeface condensation and final perceived sound/vibration strength require physical AMOLED,
   speaker, and motor calibration. No device upload, flash, erase, or installed-service mutation was
   performed in this round.
7. The AI alert auto-switch is currently awake-state behavior. Existing deep standby disables
   Wi-Fi, so this build does not claim active wake from standby or lock state.

## Interaction and Safety Checks

- AI alert: a new article ID switches to page 6, starts the high-frequency tone sequence, and starts
  a 650 ms vibration. `知道了` acknowledges; `打开` opens the source URL on the paired Mac.
- Obsidian dice: `打开文档` opens the selected Markdown note; `再摇`, the hero dice region, or an IMU
  shake rolls another authorized note. A 900 ms cooldown prevents repeated shake rolls.
- Content boundary: default scan root is `~/Smart Workspace`; `Alice Writing`, hidden metadata,
  `.obsidian`, `.trash`, `.git`, and `node_modules` remain excluded.
- Geometry: static firmware assertions keep both visible action rectangles inside radius 209 and
  their expanded touch rectangles inside the 225-pixel physical radius.

## Validation

- Main bridge/firmware-support suite: 85 tests passed after the final asset correction.
- Companion suite: 22 tests passed.
- Standalone C++ interaction test: passed.
- JSON configuration validation and macOS audio-helper compilation: passed.
- Proportion-corrected UAC `firmware.bin`: build passed at 4,542,864 bytes, SHA-256
  `a7f929101f81dac94b428f1525f1f91b46357f350f8fcdbafbe4a4493ffb5b6d`.
- `git diff --check`: passed; the existing mixed worktree was preserved.

final result: passed

---

# Clock Mint Identity QA

## Evidence

- Source visual truth: `design/clock-focus-before.png`
  plus the Owner requirement that Clock and TickTick must not share the same red identity.
- Rendered implementation: `design/clock-focus-after.png`
- Same-frame before/after comparison: `design/clock-mint-design-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Viewport and normalization: both Clock + TickTick panels are 1000 × 480 pixels at density 1;
  each watch face retains the production 466 × 466 geometry.
- State: Clock at `21:08`, charging at 82%; TickTick stopwatch active at `01:42:18`.
- Browser verification: the selected in-app browser rendered the focused comparison and seven-face
  sheet without console errors.
- Focused evidence: both complete 466-pixel circles are legible in the 1000 × 480 capture, so no
  additional crop is needed to judge hue separation, text contrast, or edge containment.

## Findings and Comparison History

1. Owner review identified a P2 identity collision: Clock and TickTick both used the same coral-red
   accent disc, making the first two pages too similar during swipe navigation.
2. Clock now uses bright mint `#18E5A1` for its accent disc, battery/status emphasis, and summary
   indicator dot. TickTick keeps coral red `#FF3B30` as the dedicated focus/active identity.
3. The after comparison shows immediate mint/red separation while preserving the established
   warm-white, black, and yellow system. No actionable P0, P1, or P2 differences remain.

## Required Fidelity Surfaces

- Fonts and typography: unchanged; hierarchy, wrapping, weights, and numeral scale are identical to
  the approved Clock and TickTick layouts.
- Spacing and layout rhythm: unchanged; the shared 164-radius accent geometry and all safe-area
  placements remain intact.
- Colors and visual tokens: Clock is now mint `#18E5A1`; TickTick remains coral `#FF3B30`; yellow
  weather/action accents and ink/paper contrast remain unchanged.
- Image quality and asset fidelity: no raster assets were added or replaced; this is a token-only
  identity change rendered natively at device geometry.
- Copy and content: all Clock and TickTick labels, metrics, dates, actions, and timer values remain
  unchanged.

## Validation

- Focused Clock/provider layout suite: 12 tests passed.
- `git diff --check`: passed.
- No flashing, device write, service mutation, or firmware upload was performed in this design-only
  session.

final result: passed

---

# Clock Weekly Provider Arcs QA

## Evidence

- Source visual truth: `design/clock-focus-after.png` plus the Owner geometry correction:
  Codex rises from 9 o'clock to 12 o'clock; Claude rises from 3 o'clock to 12 o'clock; the two
  directions oppose one another and neither arc enters the lower half.
- Rendered implementation: `design/clock-weekly-quota-arcs.png`
- Same-frame before/after comparison: `design/clock-weekly-quota-arcs-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Viewport and normalization: the implementation is a direct 466 × 466 crop at density 1. The
  1000 × 480 approved-source capture is cropped to the first face at native density and aligned in
  a 466 × 466 comparison panel; no device frame is included.
- State: Clock at `21:08`, charging at 82%; Codex weekly remaining is 73%; Claude weekly remaining
  is 61%.
- Browser verification: the in-app browser rendered the focused clock, same-frame comparison, and
  full seven-face sheet without console warnings or errors.
- Interaction state: static Clock overview. No touch target or dispatch geometry changed; `星盘`
  and `成果` retain their existing visual and touch regions.

## Findings and Comparison History

1. The clarified Owner direction resolves the provider mapping: Codex is the left blue-violet arc
   and fills from the 9 o'clock start toward the apex; Claude is the right orange arc and fills from
   the 3 o'clock start toward the apex.
2. Draft comparison found one P2 content duplication: the old mock status pill still repeated
   `C73 · A61` even though the new arcs own provider quota glanceability and the current runtime pill
   reports daily multi-AI throughput. The mock was corrected to `专68m · AI 5.03亿`.
3. Final comparison confirms that both 9-pixel arcs stay between radii 207 and 216, leave a 2-degree
   breathing split around 12 o'clock, and never enter the lower half. The header, battery, time hero,
   date, two summary pills, and bottom actions remain readable and unobstructed.
4. The firmware uses the same weekly-remaining semantics and opposite fill directions as the mock.
   Rounded five-pixel caps preserve the soft editorial finish at both fixed and live endpoints.
5. No actionable P0, P1, or P2 differences remain after the content correction.

## Required Fidelity Surfaces

- Fonts and typography: all sizes, weights, baselines, wrapping, and tabular time numerals remain
  unchanged. The perimeter visualization adds no new copy inside the constrained round screen.
- Spacing and layout rhythm: the arcs hug the perimeter and preserve the complete lower action zone.
  The small apex split keeps the two provider tracks visually independent instead of forming one
  undifferentiated upper semicircle.
- Colors and visual tokens: Codex uses the approved blue-violet `#5F67FF`; Claude uses the approved
  orange `#E27A56`; Clock remains mint `#18E5A1`; the shared track is neutral `#5E605B` for legibility
  across both warm paper and mint surfaces.
- Image quality and asset fidelity: the arcs are native vector/firmware primitives at device
  geometry, with browser SVG paths and M5GFX smooth caps; no raster placeholder or generated asset
  was introduced.
- Copy and content: the compact pill remains dedicated to TickTick focus minutes and daily combined
  AI tokens. Provider weekly remaining values are encoded by arc length and retain full numeric
  detail on the Codex and Claude pages.

## Validation

- Focused Clock/provider layout suite: 13 tests passed.
- UAC firmware software build: passed; this was a local compile only.
- `git diff --check`: passed for the three scoped implementation files.
- No flashing, device write, service mutation, or firmware upload was performed.

final result: passed

---

# Clock Lower Provider Arcs QA

## Evidence

- Source visual truth: `design/clock-weekly-quota-arcs.png` plus the Owner correction that the
  upper arcs were visually unattractive and should move to 9→6 and 3→6.
- Rendered implementation: `design/clock-lower-weekly-quota-arcs.png`
- Same-frame upper/lower comparison: `design/clock-lower-arcs-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Viewport and normalization: both source and implementation are direct 466 × 466 round-screen
  captures at density 1, with identical Clock state and no device frame.
- State: Clock at `21:08`, charging at 82%; Codex weekly remaining is 73%; Claude weekly remaining
  is 61%.
- Browser verification: the in-app browser rendered the focused Clock, comparison, and complete
  seven-face sheet without console warnings or errors.
- Interaction state: static Clock overview. The existing `星盘` and `成果` touch targets and dispatch
  behavior are unchanged.

## Findings and Comparison History

1. Owner review identified a P2 composition issue in the upper-arc version: both provider tracks
   competed with the two-line title, battery cluster, and mint accent near the top of the face.
2. Codex now fills along the shortest lower-left quarter from 9 o'clock toward 6 o'clock. Claude
   fills along the shortest lower-right quarter from 3 o'clock toward 6 o'clock. Their directions
   remain opposed and their values still mean weekly remaining quota.
3. The lower placement restores clear negative space above the time hero and turns the paired arcs
   into a visual base. At the action-row height, each arc keeps about 25 pixels of lateral clearance
   from the nearest pill; the center page-indicator zone remains between the two arcs rather than
   underneath either colored segment.
4. The two tracks stop one degree to either side of 6 o'clock, retaining the same small provider
   separation used at the former apex. Header, battery, time, date, summaries, actions, and physical
   circle containment remain intact.
5. No actionable P0, P1, or P2 differences remain after the positional correction.

## Required Fidelity Surfaces

- Fonts and typography: unchanged; the lower arcs no longer sit beside the title or battery copy,
  improving quiet space without altering type scale, weight, baselines, or wrapping.
- Spacing and layout rhythm: the 9-pixel tracks remain between radii 207 and 216. The lower-left and
  lower-right quarters frame rather than overlap the two action pills, with a narrow split at 6.
- Colors and visual tokens: Codex remains `#5F67FF`, Claude remains `#E27A56`, Clock remains mint
  `#18E5A1`, and the neutral track remains `#5E605B`; only position and fill direction changed.
- Image quality and asset fidelity: browser SVG paths and firmware-native M5GFX arcs use identical
  geometry and smooth endpoint caps; no raster or placeholder asset was added.
- Copy and content: all Clock labels and values remain unchanged from the corrected v18 design.
  Provider quota details remain available on their dedicated pages.

## Validation

- Focused Clock/provider layout suite: 13 tests passed.
- UAC firmware software build: passed; this was a local compile only.
- `git diff --check`: passed for the scoped implementation and QA files.
- No flashing, device write, service mutation, or firmware upload was performed.

final result: passed

---

# Clock Compact Provider Arcs QA

## Evidence

- Source visual truth: `design/clock-lower-weekly-quota-arcs.png` plus the Owner correction to
  lower the starts to 8 and 4 o'clock, widen the 6 o'clock gap, thicken the arcs, and move them
  closer to the outer frame.
- Rendered implementation: `design/clock-compact-weekly-quota-arcs.png`
- Same-frame before/after comparison: `design/clock-compact-arcs-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Viewport and normalization: both source and implementation are direct 466 × 466 round-screen
  captures at density 1, with the same Clock state and no device frame.
- State: Clock at `21:08`, charging at 82%; Codex weekly remaining is 73%; Claude weekly remaining
  is 61%.
- Browser verification: the in-app browser rendered the focused Clock, same-frame comparison, and
  complete seven-face sheet without console warnings or errors.
- Interaction state: static Clock overview. The `星盘` and `成果` visual bounds, expanded touch
  bounds, and dispatch behavior are unchanged.

## Findings and Comparison History

1. Owner review identified three P2 proportion issues in the 9→6 / 3→6 version: the starts still
   felt too high, the 6 o'clock split was too tight, and the thin inset tracks looked detached from
   the physical frame.
2. Codex now begins at 8 o'clock and Claude at 4 o'clock. Both arcs retain the shortest route toward
   6 o'clock, so the colored segments read as compact corner accents rather than side rails.
3. The centerline endpoint gap grows from about 7 pixels to about 37 pixels; after the rounded caps,
   the visible 6 o'clock breathing space is about 24 pixels.
4. Arc thickness increases from 9 to 14 pixels. The outer radius moves from 216 to 222, leaving a
   3-pixel inset from the 225-radius face clip while remaining safely inside the physical circle.
5. The focused comparison confirms that the heavier arcs now visually attach to the bezel without
   crowding the action pills or center page-indicator zone. No actionable P0, P1, or P2 differences
   remain.

## Required Fidelity Surfaces

- Fonts and typography: unchanged; the new starts sit below the date and summary row, leaving all
  text hierarchy, baselines, wrapping, and optical weight untouched.
- Spacing and layout rhythm: the shorter 55-degree tracks form two compact lower corners. Their
  14-pixel weight balances the 6-pixel black bezel, and the widened center gap prevents a U-shape.
- Colors and visual tokens: Codex remains `#5F67FF`, Claude remains `#E27A56`, Clock remains mint
  `#18E5A1`, and the shared neutral track remains `#5E605B`.
- Image quality and asset fidelity: SVG and firmware use matching 222/208 radii, 215-pixel
  centerline, and 7-pixel smooth caps; no raster substitute or placeholder was introduced.
- Copy and content: all Clock labels, values, provider semantics, and dedicated provider-page
  details remain unchanged.

## Validation

- Focused Clock/provider layout suite: 13 tests passed.
- UAC firmware software build: passed; this was a local compile only.
- `git diff --check`: passed for the scoped implementation and QA files.
- No flashing, device write, service mutation, or firmware upload was performed.

final result: passed

---

# Clock Light Provider Tracks QA

## Evidence

- Source visual truth: `design/clock-compact-weekly-quota-arcs.png` plus the Owner request to
  replace the shared gray track with a lighter Codex blue and lighter Claude orange.
- Rendered implementation: `design/clock-light-provider-tracks.png`
- Same-frame before/after comparison: `design/clock-light-provider-tracks-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Viewport and normalization: both comparison captures are direct 466 × 466 round-screen renders
  at density 1, using identical geometry, content, and state.
- State: Clock at `21:08`, charging at 82%; Codex weekly remaining is 73%; Claude weekly remaining
  is 61%.
- Browser verification: focused Clock, same-frame comparison, and complete seven-face sheet all
  rendered in the in-app browser without console warnings or errors.
- Interaction state: static Clock overview. Button geometry, expanded touch bounds, and dispatch
  behavior remain unchanged.

## Findings and Comparison History

1. The prior shared `#5E605B` gray made the lower edge feel muddy and did not preserve provider
   identity outside the active segment.
2. The Codex background track is now a low-saturation light blue `#C8CBFF`; the Claude background
   track is now a low-saturation light orange `#F3C6B5`.
3. Active quota colors remain `#5F67FF` and `#E27A56`, preserving a clear active-versus-track
   hierarchy without changing the 73% and 61% readings.
4. The lighter tracks sit cleanly on the warm paper background, keep the mint Clock identity
   dominant, and make the two provider arcs legible before reading their dedicated pages.
5. The focused comparison confirms that no actionable P0, P1, or P2 difference remains.

## Required Fidelity Surfaces

- Fonts and typography: unchanged.
- Spacing and layout rhythm: unchanged; both 55-degree tracks retain 14-pixel weight, 222/208
  radii, 215-pixel centerline, 7-pixel caps, and the widened 6 o'clock gap.
- Colors and visual tokens: only the two background tracks changed. Clock mint, active Codex blue,
  active Claude orange, black ink, warm paper, and yellow secondary accent remain unchanged.
- Image quality and asset fidelity: SVG and firmware use the same provider-specific track colors;
  no raster substitute or placeholder was introduced.
- Copy and content: unchanged.

## Validation

- Focused Clock/provider layout suite: 13 tests passed.
- UAC firmware software build: passed; this was a local compile only.
- `git diff --check`: passed for the scoped implementation and QA files.
- No flashing, device write, service mutation, or firmware upload was performed.

final result: passed

---

# Clock Short Arcs vs. Semicircle Candidate QA

## Evidence

- Source visual truth: `design/clock-light-provider-tracks.png` plus the Owner geometry brief for
  a Codex left semicircle from 6→12 and a Claude right semicircle from 12→6.
- Rendered candidate: `design/clock-semicircle-provider-arcs-candidate.png`
- Same-frame option comparison: `design/clock-short-vs-semicircle-qa-comparison.png`
- Candidate source: `design/stopwatch-ui-preview-semicircle-candidate.svg`
- Viewport and normalization: both Clock captures are 466 × 466 pixels at density 1 with identical
  content, state, colors, 14-pixel track weight, and 215-pixel centerline radius.
- State: Clock at `21:08`, charging at 82%; Codex weekly remaining is 73%; Claude weekly remaining
  is 61%.
- Browser verification: candidate and same-frame comparison rendered without console warnings or
  errors.

## Findings and Comparison

1. The candidate faithfully moves Codex to the full left half from 6→12 and Claude to the full
   right half from 12→6 while preserving their active and light-track colors.
2. The semicircle version makes provider quota a persistent frame around the entire face and gives
   the 73%/61% values much more visual weight than the compact lower-corner version.
3. The trade-off is density: the left arc now sits beside the Clock title and time hero, while the
   right arc runs beside the battery and mint field. The current short arcs preserve more quiet
   space and keep time as the dominant information.
4. Rounded endpoints meet at 12 and 6 as specified. Their color handoffs are clear, but the result
   reads closer to a near-complete outer ring than two independent accents.
5. No P0, P1, or P2 fidelity issue remains in the candidate rendering; the visual-weight choice is
   intentionally left for Owner selection.

## Required Fidelity Surfaces

- Fonts and typography: identical across both options.
- Spacing and layout rhythm: all content geometry is identical; only arc sweep changes from two
  55-degree lower-corner tracks to two 180-degree side tracks.
- Colors and visual tokens: identical Codex active/light blue and Claude active/light orange.
- Image quality and asset fidelity: both options are browser-rendered vector paths at equal scale;
  no raster or placeholder asset was introduced into the source design.
- Copy and content: identical.

## Validation

- Candidate SVG structure: valid XML.
- Focused option captures: 466 × 466 pixels each; comparison capture: 980 × 540 pixels.
- Browser console: no warnings or errors on candidate or comparison.
- `git diff --check`: passed.
- The approved v21 SVG, firmware, and device state remain unchanged; this is a design-only candidate.

final result: passed

---

# Clock Summary-Aligned Provider Arcs QA

## Evidence

- Source visual truth: `design/clock-light-provider-tracks.png` plus the Owner request to align
  both provider-arc starts with the top edge of the weather/focus-summary row.
- Rendered implementation: `design/clock-summary-aligned-provider-arcs.png`
- Same-frame before/after comparison: `design/clock-summary-aligned-arcs-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Viewport and normalization: both focused captures are 466 × 466 pixels at density 1 with the
  same Clock content and state.
- State: Clock at `21:08`, charging at 82%; Codex weekly remaining is 73%; Claude weekly remaining
  is 61%.
- Browser verification: focused Clock, same-frame comparison, and complete seven-face sheet all
  rendered without console warnings or errors.

## Findings and Comparison History

1. The prior compact arcs began at y=340.5, visually below the y=285 summary-row top. That made
   the arcs feel attached mainly to the action buttons rather than to the whole lower information
   block.
2. The SVG starts now sit at `(24.4, 285)` and `(441.6, 285)`, exactly level with the two summary
   capsules. Firmware start angles move to 164.6° and 15.4°, placing both physical endpoints at
   approximately y=282, matching the native summary-capsule top.
3. Arc thickness, 222/208 radii, light provider tracks, active provider colors, and the widened
   6 o'clock gap remain unchanged.
4. The new horizontal anchor makes the two arcs frame the summary and action rows as one lower
   module while preserving the open top half and the time hero.
5. The focused comparison shows no actionable P0, P1, or P2 difference after the alignment fix.

## Required Fidelity Surfaces

- Fonts and typography: unchanged.
- Spacing and layout rhythm: only the two outer start endpoints move upward; summary capsules,
  action pills, lower endpoints, bezel inset, and center gap remain unchanged.
- Colors and visual tokens: unchanged Codex active/light blue, Claude active/light orange, Clock
  mint, warm paper, black ink, and yellow accent.
- Image quality and asset fidelity: SVG and firmware continue to use native vector/arc geometry
  with smooth 7-pixel endpoint caps; no raster substitute or placeholder was introduced.
- Copy and content: unchanged.

## Validation

- Focused Clock/provider layout suite: 13 tests passed.
- UAC firmware software build: passed; this was a local compile only.
- Browser console: no warnings or errors on focused, comparison, or full-sheet views.
- `git diff --check`: passed.
- No flashing, device write, service mutation, or firmware upload was performed.

final result: passed

---

# Clock Cap-Aligned Used-Quota Arcs QA

## Evidence

- Source visual truth: `design/clock-summary-aligned-provider-arcs.png` plus the Owner corrections
  that the visible rounded edge—not its centerline—must align with the capsule top, and that deep
  color must represent weekly usage rather than weekly remaining quota.
- Rendered implementation: `design/clock-used-quota-arcs.png`
- Same-frame before/after comparison: `design/clock-used-quota-arcs-qa-comparison.png`
- Seven-face context sheet: `design/stopwatch-ui-preview.png`
- Viewport and normalization: both focused captures are 466 × 466 pixels at density 1 with the
  same Clock content and state.
- Static preview state: Codex is 73% remaining / 27% used; Claude is 61% remaining / 39% used.
- Browser verification: focused Clock, comparison, and complete seven-face sheet rendered without
  console warnings or errors.

## Findings and Comparison History

1. The previous pass aligned the arc endpoint centerline to the capsule top. Its 7-pixel rounded
   cap therefore protruded 7 pixels above the intended visual anchor.
2. Each SVG endpoint center moves down by 7 pixels, from y=285 to y=292; the firmware endpoints
   move to angles 162.7° and 17.3°, placing their cap centers at approximately y=289. The visible
   cap edges now align with the y=285 SVG and y=282 firmware capsule tops.
3. The previous deep segments encoded remaining quota. That produced a light segment equal to
   usage near 6 o'clock and made progress read like depletion or rollback.
4. The implementation now consumes `weekUsedPercent` directly. Deep Codex and Claude segments
   start at 6 o'clock and grow outward: 0% used is fully light, 45% used is 45% deep, and 100% used
   is fully deep.
5. Arc thickness, bezel inset, provider colors, lower endpoints, 6 o'clock gap, text, capsules,
   actions, and interaction bounds remain unchanged. No actionable P0, P1, or P2 issue remains.

## Required Fidelity Surfaces

- Fonts and typography: unchanged.
- Spacing and layout rhythm: only the cap-aware outer endpoint centers move down 7 pixels; all
  content and lower arc geometry remain unchanged.
- Colors and visual tokens: colors are unchanged; their semantics are corrected so deep equals
  used and light equals remaining.
- Image quality and asset fidelity: SVG and firmware use native vector/arc geometry with matching
  14-pixel tracks and smooth 7-pixel caps; no raster substitute or placeholder was introduced.
- Copy and content: unchanged.

## Validation

- Focused Clock/provider layout suite: 13 tests passed.
- UAC firmware software build: passed; this was a local compile only.
- Candidate SVG structure: valid XML.
- Browser console: no warnings or errors on focused, comparison, or full-sheet views.
- `git diff --check`: passed.
- No flashing, device write, service mutation, or firmware upload was performed.

final result: passed
