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
