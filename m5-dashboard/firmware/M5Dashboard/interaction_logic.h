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
  toggleStandby,
  powerOff,
};

struct DashboardPowerButtonState {
  bool wasPressed = false;
  bool secondClick = false;
  bool singleClickPending = false;
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
    return startX < displayWidth / 2 ? DashboardGesture::brightness
                                     : DashboardGesture::volume;
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
    uint32_t doubleClickMs, uint32_t shortPressMaxMs) {
  DashboardPowerAction action = DashboardPowerAction::none;

  if (pressed && !state.wasPressed) {
    state.pressedAt = now;
    if (state.singleClickPending) {
      if (static_cast<uint32_t>(now - state.releasedAt) < doubleClickMs) {
        state.secondClick = true;
        state.singleClickPending = false;
      } else {
        state.singleClickPending = false;
        action = DashboardPowerAction::toggleStandby;
      }
    } else {
      state.secondClick = false;
    }
  }

  if (!pressed && state.wasPressed) {
    uint32_t heldMs = static_cast<uint32_t>(now - state.pressedAt);
    if (state.secondClick && heldMs < shortPressMaxMs) {
      action = DashboardPowerAction::powerOff;
    } else if (!state.secondClick && heldMs < shortPressMaxMs) {
      state.singleClickPending = true;
      state.releasedAt = now;
    }
    state.secondClick = false;
  }

  state.wasPressed = pressed;
  if (action == DashboardPowerAction::none && !pressed && state.singleClickPending &&
      static_cast<uint32_t>(now - state.releasedAt) >= doubleClickMs) {
    state.singleClickPending = false;
    action = DashboardPowerAction::toggleStandby;
  }
  return action;
}

inline bool usbReplyPending(uint32_t now, uint32_t lastRequestAt,
                            uint32_t gracePeriodMs) {
  return lastRequestAt != 0 && static_cast<uint32_t>(now - lastRequestAt) < gracePeriodMs;
}

inline int dashboardCenteredOffset(int displaySize, int designSize) {
  return displaySize > designSize ? (displaySize - designSize) / 2 : 0;
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
