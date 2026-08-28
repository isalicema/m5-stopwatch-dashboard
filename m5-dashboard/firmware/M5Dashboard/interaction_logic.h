#pragma once

#include <cstdint>

enum class DashboardGesture {
  none,
  page,
  brightness,
  volume,
};

enum class DashboardPowerAction {
  none,
  toggleScreen,
  openLauncher,
  powerOff,
};

enum class DashboardClickAction {
  none,
  singleClick,
  doubleClick,
};

enum class DashboardFocusTouchTarget {
  none,
  primary,
  end,
};

enum class DashboardClockTouchTarget {
  none,
  orbit,
  results,
};

enum class DashboardFeatureTouchTarget {
  none,
  primary,
  secondary,
  hero,
};

enum class DashboardClockRefresh {
  none,
  secondsOnly,
  fullPage,
};

enum class DashboardTypelessMode {
  unavailable,
  macMic,
  usbMic,
};

constexpr int kEditorialHeaderX = 124;
constexpr int kEditorialHeaderBoundsY = 48;
constexpr int kEditorialHeaderBoundsWidth = 104;
constexpr int kEditorialHeaderBoundsHeight = 72;
constexpr int kEditorialHeaderFirstLineY = 62;
constexpr int kEditorialHeaderSecondLineY = 92;
constexpr int kEditorialHeaderUnderlineY = 116;

constexpr int kClockOrbitActionX = 100;
constexpr int kClockResultsActionX = 232;
constexpr int kClockActionY = 344;
constexpr int kClockActionWidth = 118;
constexpr int kClockActionHeight = 48;
constexpr int kClockOrbitTouchX = 89;
constexpr int kClockResultsTouchX = 225;
// Keep the shortcut targets close to their Y=344..392 visual capsules. The old
// Y=326 start left only a 2 px gap below the Y=282..324 information pills, so
// ordinary taps on weather/AI usage could be interpreted as shortcut taps.
constexpr int kClockActionTouchY = 336;
constexpr int kClockActionTouchWidth = 136;
constexpr int kClockActionTouchHeight = 64;
// Physical samples from the C152 lower edge report the visual Y=344..392
// shortcut capsules around design Y=400..425. Extend only downward: the round
// panel clips the unreachable rectangle corners, and the information pills
// above the shortcuts remain outside the target.
constexpr int kClockActionLowerEdgeCompensation = 32;
// A fingertip on the lower half of the round panel commonly drifts farther
// than the global 18 px gesture lock. Keep the shortcut armed through that
// small drift; a deliberate page swipe still clears this threshold easily.
constexpr int kClockActionTapSlop = 34;

constexpr int kProviderIconX = 296;
constexpr int kProviderIconY = 150;
constexpr int kProviderIconSize = 96;
constexpr int kProviderIconTouchExpansion = 14;
constexpr int kEditorialFooterX = 106;
constexpr int kEditorialFooterY = 344;
constexpr int kEditorialFooterWidth = 238;
constexpr int kEditorialFooterHeight = 52;

constexpr int kVoiceTouchX = 62;
constexpr int kVoiceTouchY = 94;
constexpr int kVoiceTouchWidth = 326;
constexpr int kVoiceTouchHeight = 246;

constexpr int kFeaturePrimaryActionX = 106;
constexpr int kFeatureSecondaryActionX = 282;
constexpr int kFeatureActionY = 344;
constexpr int kFeaturePrimaryActionWidth = 166;
constexpr int kFeatureSecondaryActionWidth = 62;
constexpr int kFeatureActionHeight = 52;
constexpr int kFeaturePrimaryTouchX = 96;
constexpr int kFeatureSecondaryTouchX = 278;
// The physical action row is close to the round lower edge. Expand upward and
// use every safe pixel below it so a fingertip does not have to land on the
// label itself.
constexpr int kFeatureActionTouchY = 330;
constexpr int kFeaturePrimaryTouchWidth = 182;
constexpr int kFeatureSecondaryTouchWidth = 76;
constexpr int kFeatureActionTouchHeight = 78;
// Physical taps on the C152 lower edge land below the design-space footer.
// Match the clock/focus compensation so the whole visible capsule remains
// reachable without moving the artwork or stealing the content row above it.
constexpr int kFeatureActionLowerEdgeCompensation = 32;
constexpr int kFeatureActionTapSlop = 32;
// The AI alert page pairs a wide acknowledgement capsule with a very short
// "open" capsule near the curved right edge. Keep the artwork unchanged, but
// give both actions a fingertip-sized target across the full safe footer row.
constexpr int kAIHotspotActionTouchX = 70;
constexpr int kAIHotspotActionTouchY = 318;
constexpr int kAIHotspotActionTouchRight = 390;
constexpr int kAIHotspotActionTouchBottom = 440;
constexpr int kAIHotspotActionDividerX = 278;
constexpr int kFeatureHeroTouchX = 230;
constexpr int kFeatureHeroTouchY = 96;
constexpr int kFeatureHeroTouchWidth = 176;
constexpr int kFeatureHeroTouchHeight = 176;

constexpr int kFocusStatusX = 124;
constexpr int kFocusStatusBoundsY = 48;
constexpr int kFocusStatusBoundsWidth = 84;
constexpr int kFocusStatusBoundsHeight = 72;
constexpr int kFocusStatusFirstLineY = 62;
constexpr int kFocusStatusSecondLineY = 92;
constexpr int kFocusStatusUnderlineY = 116;

constexpr int kFocusPrimaryActionX = 106;
constexpr int kFocusEndActionX = 282;
constexpr int kFocusActionY = 344;
constexpr int kFocusPrimaryActionWidth = 166;
constexpr int kFocusEndActionWidth = 62;
constexpr int kFocusActionHeight = 52;

constexpr int kFocusPrimaryTouchX = 96;
constexpr int kFocusEndTouchX = 278;
constexpr int kFocusActionTouchY = 338;
constexpr int kFocusPrimaryTouchWidth = 182;
constexpr int kFocusEndTouchWidth = 76;
constexpr int kFocusActionTouchHeight = 66;
constexpr int kFocusActionLowerEdgeCompensation = 32;
constexpr int kFocusActionTapSlop = 34;

constexpr int dashboardSquared(int value) {
  return value * value;
}

constexpr bool dashboardPointInCircle(int x, int y, int centerX, int centerY,
                                      int radius) {
  return dashboardSquared(x - centerX) + dashboardSquared(y - centerY) <=
         dashboardSquared(radius);
}

constexpr bool dashboardRectInsideCircle(int left, int top, int width, int height,
                                         int centerX, int centerY, int radius) {
  return dashboardPointInCircle(left, top, centerX, centerY, radius) &&
         dashboardPointInCircle(left + width, top, centerX, centerY, radius) &&
         dashboardPointInCircle(left, top + height, centerX, centerY, radius) &&
         dashboardPointInCircle(left + width, top + height, centerX, centerY, radius);
}

static_assert(dashboardRectInsideCircle(kFocusPrimaryActionX, kFocusActionY,
                                       kFocusPrimaryActionWidth, kFocusActionHeight,
                                       225, 225, 209),
              "primary focus action must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kFocusStatusX, kFocusStatusBoundsY,
                                       kFocusStatusBoundsWidth,
                                       kFocusStatusBoundsHeight, 225, 225, 209),
              "focus status text must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kFocusEndActionX, kFocusActionY,
                                       kFocusEndActionWidth, kFocusActionHeight,
                                       225, 225, 209),
              "end focus action must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kFocusPrimaryTouchX, kFocusActionTouchY,
                                       kFocusPrimaryTouchWidth,
                                       kFocusActionTouchHeight, 225, 225, 225),
              "primary focus touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kFocusEndTouchX, kFocusActionTouchY,
                                       kFocusEndTouchWidth,
                                       kFocusActionTouchHeight, 225, 225, 225),
              "end focus touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kEditorialHeaderX, kEditorialHeaderBoundsY,
                                       kEditorialHeaderBoundsWidth,
                                       kEditorialHeaderBoundsHeight, 225, 225, 209),
              "editorial header must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kClockOrbitActionX, kClockActionY,
                                       kClockActionWidth, kClockActionHeight,
                                       225, 225, 209),
              "clock orbit action must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kClockResultsActionX, kClockActionY,
                                       kClockActionWidth, kClockActionHeight,
                                       225, 225, 209),
              "clock results action must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kClockOrbitTouchX, kClockActionTouchY,
                                       kClockActionTouchWidth,
                                       kClockActionTouchHeight, 225, 225, 225),
              "clock orbit touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kClockResultsTouchX, kClockActionTouchY,
                                       kClockActionTouchWidth,
                                       kClockActionTouchHeight, 225, 225, 225),
              "clock results touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kProviderIconX - kProviderIconTouchExpansion,
                                       kProviderIconY - kProviderIconTouchExpansion,
                                       kProviderIconSize + 2 * kProviderIconTouchExpansion,
                                       kProviderIconSize + 2 * kProviderIconTouchExpansion,
                                       225, 225, 225),
              "provider icon touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kEditorialFooterX, kEditorialFooterY,
                                       kEditorialFooterWidth, kEditorialFooterHeight,
                                       225, 225, 209),
              "editorial footer must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kVoiceTouchX, kVoiceTouchY,
                                       kVoiceTouchWidth, kVoiceTouchHeight,
                                       225, 225, 225),
              "voice touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kFeaturePrimaryActionX, kFeatureActionY,
                                       kFeaturePrimaryActionWidth,
                                       kFeatureActionHeight, 225, 225, 209),
              "feature primary action must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kFeatureSecondaryActionX, kFeatureActionY,
                                       kFeatureSecondaryActionWidth,
                                       kFeatureActionHeight, 225, 225, 209),
              "feature secondary action must stay inside the visual safe circle");
static_assert(dashboardRectInsideCircle(kFeaturePrimaryTouchX, kFeatureActionTouchY,
                                       kFeaturePrimaryTouchWidth,
                                       kFeatureActionTouchHeight, 225, 225, 225),
              "feature primary touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kFeatureSecondaryTouchX, kFeatureActionTouchY,
                                       kFeatureSecondaryTouchWidth,
                                       kFeatureActionTouchHeight, 225, 225, 225),
              "feature secondary touch target must stay inside the physical circle");
static_assert(dashboardRectInsideCircle(kFeatureHeroTouchX, kFeatureHeroTouchY,
                                       kFeatureHeroTouchWidth,
                                       kFeatureHeroTouchHeight, 225, 225, 225),
              "feature hero touch target must stay inside the physical circle");

inline DashboardFocusTouchTarget dashboardFocusTouchTarget(int x, int y) {
  if (x >= kFocusPrimaryTouchX && x < kFocusPrimaryTouchX + kFocusPrimaryTouchWidth &&
      y >= kFocusActionTouchY &&
      y < kFocusActionTouchY + kFocusActionTouchHeight +
              kFocusActionLowerEdgeCompensation) {
    return DashboardFocusTouchTarget::primary;
  }
  if (x >= kFocusEndTouchX && x < kFocusEndTouchX + kFocusEndTouchWidth &&
      y >= kFocusActionTouchY &&
      y < kFocusActionTouchY + kFocusActionTouchHeight +
              kFocusActionLowerEdgeCompensation) {
    return DashboardFocusTouchTarget::end;
  }
  return DashboardFocusTouchTarget::none;
}

inline bool dashboardFocusTapAccepted(int deltaX, int deltaY) {
  return deltaX >= -kFocusActionTapSlop && deltaX <= kFocusActionTapSlop &&
         deltaY >= -kFocusActionTapSlop && deltaY <= kFocusActionTapSlop;
}

inline bool dashboardTimerPreserveRunningAnchor(bool wasRunning, bool isRunning,
                                                int localSeconds,
                                                int remoteSeconds,
                                                int toleranceSeconds = 3) {
  if (!wasRunning || !isRunning || toleranceSeconds < 0) return false;
  int delta = remoteSeconds - localSeconds;
  if (delta < 0) delta = -delta;
  return delta <= toleranceSeconds;
}

inline int dashboardAlignedRunningTimerBase(int remoteSeconds,
                                            uint32_t anchorAgeSeconds,
                                            bool countsDown) {
  int aligned = countsDown
                    ? remoteSeconds + static_cast<int>(anchorAgeSeconds)
                    : remoteSeconds - static_cast<int>(anchorAgeSeconds);
  return aligned < 0 ? 0 : aligned;
}

inline DashboardClockTouchTarget dashboardClockTouchTarget(int x, int y) {
  if (x >= kClockOrbitTouchX && x < kClockOrbitTouchX + kClockActionTouchWidth &&
      y >= kClockActionTouchY &&
      y < kClockActionTouchY + kClockActionTouchHeight +
              kClockActionLowerEdgeCompensation) {
    return DashboardClockTouchTarget::orbit;
  }
  if (x >= kClockResultsTouchX && x < kClockResultsTouchX + kClockActionTouchWidth &&
      y >= kClockActionTouchY &&
      y < kClockActionTouchY + kClockActionTouchHeight +
              kClockActionLowerEdgeCompensation) {
    return DashboardClockTouchTarget::results;
  }
  return DashboardClockTouchTarget::none;
}

inline bool dashboardClockTapAccepted(int deltaX, int deltaY) {
  return deltaX >= -kClockActionTapSlop && deltaX <= kClockActionTapSlop &&
         deltaY >= -kClockActionTapSlop && deltaY <= kClockActionTapSlop;
}

inline bool dashboardVoiceTouchTarget(int x, int y) {
  const bool inCentralTarget =
      x >= kVoiceTouchX && x <= kVoiceTouchX + kVoiceTouchWidth &&
      y >= kVoiceTouchY && y <= kVoiceTouchY + kVoiceTouchHeight;
  const bool inFooterTarget =
      x >= kEditorialFooterX && x <= kEditorialFooterX + kEditorialFooterWidth &&
      y >= kEditorialFooterY && y <= kEditorialFooterY + kEditorialFooterHeight;
  return inCentralTarget || inFooterTarget;
}

inline DashboardFeatureTouchTarget dashboardFeatureTouchTarget(int x, int y,
                                                                bool includeHero) {
  if (x >= kFeaturePrimaryTouchX &&
      x < kFeaturePrimaryTouchX + kFeaturePrimaryTouchWidth &&
      y >= kFeatureActionTouchY &&
      y < kFeatureActionTouchY + kFeatureActionTouchHeight +
              kFeatureActionLowerEdgeCompensation) {
    return DashboardFeatureTouchTarget::primary;
  }
  if (x >= kFeatureSecondaryTouchX &&
      x < kFeatureSecondaryTouchX + kFeatureSecondaryTouchWidth &&
      y >= kFeatureActionTouchY &&
      y < kFeatureActionTouchY + kFeatureActionTouchHeight +
              kFeatureActionLowerEdgeCompensation) {
    return DashboardFeatureTouchTarget::secondary;
  }
  if (includeHero && x >= kFeatureHeroTouchX &&
      x < kFeatureHeroTouchX + kFeatureHeroTouchWidth &&
      y >= kFeatureHeroTouchY && y < kFeatureHeroTouchY + kFeatureHeroTouchHeight) {
    return DashboardFeatureTouchTarget::hero;
  }
  return DashboardFeatureTouchTarget::none;
}

inline DashboardFeatureTouchTarget dashboardAIHotspotTouchTarget(int x, int y) {
  if (x < kAIHotspotActionTouchX || x >= kAIHotspotActionTouchRight ||
      y < kAIHotspotActionTouchY || y >= kAIHotspotActionTouchBottom ||
      !dashboardPointInCircle(x, y, 225, 225, 225)) {
    return DashboardFeatureTouchTarget::none;
  }
  return x < kAIHotspotActionDividerX
             ? DashboardFeatureTouchTarget::primary
             : DashboardFeatureTouchTarget::secondary;
}

inline bool dashboardFeatureTapAccepted(DashboardGesture gesture,
                                        int deltaX, int deltaY) {
  // The global 18 px gesture lock is intentionally crisp for page navigation,
  // but a round-screen footer tap commonly drifts farther under a fingertip.
  // A short horizontal drift is still far below the 100 px page-swipe gate.
  bool tapLikeGesture = gesture == DashboardGesture::none ||
                        gesture == DashboardGesture::page;
  return tapLikeGesture && deltaX >= -kFeatureActionTapSlop &&
         deltaX <= kFeatureActionTapSlop &&
         deltaY >= -kFeatureActionTapSlop &&
         deltaY <= kFeatureActionTapSlop;
}

inline bool dashboardShakeDetected(bool previousReady, float deltaX, float deltaY,
                                   float deltaZ, uint32_t now,
                                   uint32_t lastShakeAt, uint32_t cooldownMs,
                                   float threshold) {
  if (!previousReady || static_cast<uint32_t>(now - lastShakeAt) < cooldownMs) {
    return false;
  }
  float magnitudeSquared = deltaX * deltaX + deltaY * deltaY + deltaZ * deltaZ;
  return magnitudeSquared >= threshold * threshold;
}

struct DashboardClickButtonState {
  bool singlePending = false;
  uint32_t releasedAt = 0;
};

inline int dashboardHomePageDelta(int currentPage) {
  return currentPage > 0 ? -currentPage : 0;
}

inline DashboardClickAction queueDashboardClick(DashboardClickButtonState &state,
                                                 uint32_t now,
                                                 uint32_t doubleClickMs) {
  if (state.singlePending &&
      static_cast<uint32_t>(now - state.releasedAt) < doubleClickMs) {
    state.singlePending = false;
    return DashboardClickAction::doubleClick;
  }
  state.singlePending = true;
  state.releasedAt = now;
  return DashboardClickAction::none;
}

inline DashboardClickAction flushDashboardClick(DashboardClickButtonState &state,
                                                 uint32_t now,
                                                 uint32_t doubleClickMs) {
  if (state.singlePending &&
      static_cast<uint32_t>(now - state.releasedAt) >= doubleClickMs) {
    state.singlePending = false;
    return DashboardClickAction::singleClick;
  }
  return DashboardClickAction::none;
}

struct DashboardPowerButtonState {
  bool wasPressed = false;
  bool longPressHandled = false;
  bool singleClickPending = false;
  bool secondPressCandidate = false;
  uint32_t pressedAt = 0;
  uint32_t releasedAt = 0;
};

inline int dashboardRemainingPercent(int usedPercent) {
  if (usedPercent < 0) return -1;
  if (usedPercent > 100) usedPercent = 100;
  return 100 - usedPercent;
}

inline DashboardGesture classifyDashboardGesture(int deltaX, int deltaY, int startX,
                                                  int displayWidth, int threshold) {
  int absoluteX = deltaX < 0 ? -deltaX : deltaX;
  int absoluteY = deltaY < 0 ? -deltaY : deltaY;
  if (absoluteX < threshold && absoluteY < threshold) return DashboardGesture::none;
  if (absoluteX * 4 >= absoluteY * 5) return DashboardGesture::page;
  if (absoluteY * 4 >= absoluteX * 5) {
    // Keep vertical controls physically separated on the round display:
    // left 2/5 adjusts brightness, the middle 1/5 is a safety gap, and
    // right 2/5 adjusts notification volume. Horizontal page swipes remain
    // available across the full display because they are classified above.
    if (startX * 5 < displayWidth * 2) return DashboardGesture::brightness;
    if (startX * 5 >= displayWidth * 3) return DashboardGesture::volume;
    return DashboardGesture::none;
  }
  return DashboardGesture::none;
}

inline int adjustedDashboardPercent(int startPercent, int deltaY, int minimum,
                                    int travelPixels, int step) {
  int value = startPercent - deltaY * 100 / travelPixels;
  if (value < minimum) value = minimum;
  if (value > 100) value = 100;
  value = ((value + step / 2) / step) * step;
  if (value < minimum) value = minimum;
  if (value > 100) value = 100;
  return value;
}

inline bool shouldToggleVoiceSessionOnRelease(bool tracking, bool consumed) {
  return tracking && !consumed;
}

inline bool dashboardTypelessUsbAvailable(bool audioReady,
                                           bool physicalUsbConnected,
                                           bool usbLinkUsable,
                                           bool usbBridgeOnline) {
  return audioReady && physicalUsbConnected && usbLinkUsable && usbBridgeOnline;
}

inline DashboardTypelessMode dashboardTypelessMode(bool usbAvailable,
                                                    bool wifiConnected,
                                                    bool wifiBridgeOnline) {
  if (usbAvailable) return DashboardTypelessMode::usbMic;
  if (wifiConnected && wifiBridgeOnline) return DashboardTypelessMode::macMic;
  return DashboardTypelessMode::unavailable;
}

inline DashboardClockRefresh dashboardClockRefresh(int currentSecond,
                                                     int previousSecond,
                                                     int currentMinute,
                                                     int previousMinute) {
  if (previousSecond < 0 || previousMinute < 0 || currentMinute != previousMinute) {
    return DashboardClockRefresh::fullPage;
  }
  if (currentSecond != previousSecond) {
    return DashboardClockRefresh::secondsOnly;
  }
  return DashboardClockRefresh::none;
}

inline bool dashboardPointInExpandedRect(int x, int y, int left, int top,
                                         int width, int height, int padding) {
  return x >= left - padding && x < left + width + padding &&
         y >= top - padding && y < top + height + padding;
}

inline int dashboardTranscriptOffset(int currentOffset, int deltaRows,
                                     int messageCount, int visibleMessages) {
  int maximum = messageCount > visibleMessages ? messageCount - visibleMessages : 0;
  int next = currentOffset + deltaRows;
  if (next < 0) return 0;
  if (next > maximum) return maximum;
  return next;
}

inline DashboardPowerAction updateDashboardPowerButton(
    DashboardPowerButtonState &state, bool pressed, uint32_t now,
    uint32_t shortPressMaxMs, uint32_t doubleClickMs,
    uint32_t longPressMs, bool usbConnected) {
  DashboardPowerAction action = DashboardPowerAction::none;

  if (pressed && !state.wasPressed) {
    state.pressedAt = now;
    state.longPressHandled = false;
    state.secondPressCandidate =
        state.singleClickPending &&
        static_cast<uint32_t>(now - state.releasedAt) < doubleClickMs;
  }

  if (pressed && !state.longPressHandled &&
      static_cast<uint32_t>(now - state.pressedAt) >= longPressMs) {
    state.longPressHandled = true;
    state.singleClickPending = false;
    state.secondPressCandidate = false;
    if (!usbConnected) action = DashboardPowerAction::powerOff;
  }

  if (!pressed && state.wasPressed) {
    uint32_t heldMs = static_cast<uint32_t>(now - state.pressedAt);
    if (!state.longPressHandled && heldMs < shortPressMaxMs) {
      if (state.secondPressCandidate) {
        state.singleClickPending = false;
        action = DashboardPowerAction::openLauncher;
      } else {
        state.singleClickPending = true;
        state.releasedAt = now;
      }
    }
    state.longPressHandled = false;
    state.secondPressCandidate = false;
  }

  if (!pressed && !state.wasPressed && state.singleClickPending &&
      static_cast<uint32_t>(now - state.releasedAt) >= doubleClickMs) {
    state.singleClickPending = false;
    action = DashboardPowerAction::toggleScreen;
  }

  state.wasPressed = pressed;
  return action;
}

inline bool usbReplyPending(uint32_t now, uint32_t lastRequestAt,
                            uint32_t gracePeriodMs) {
  return lastRequestAt != 0 && static_cast<uint32_t>(now - lastRequestAt) < gracePeriodMs;
}

inline int dashboardCenteredOffset(int displaySize, int designSize) {
  return displaySize > designSize ? (displaySize - designSize) / 2 : 0;
}

inline int dashboardPowerTransitionRadius(bool starting, int percent) {
  int clamped = percent < 0 ? 0 : percent > 100 ? 100 : percent;
  return starting ? 12 + clamped * 54 / 100
                  : 66 - clamped * 56 / 100;
}

inline int nextConfiguredWifiProfile(int previousProfile, bool homeConfigured,
                                     bool workConfigured) {
  for (int offset = 1; offset <= 2; ++offset) {
    int candidate = (previousProfile + offset + 2) % 2;
    if ((candidate == 0 && homeConfigured) || (candidate == 1 && workConfigured)) {
      return candidate;
    }
  }
  return -1;
}
