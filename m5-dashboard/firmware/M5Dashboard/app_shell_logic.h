#pragma once

#include <cstddef>
#include <cstdint>

inline bool dashboardUsbPairingTokenValid(const char *token,
                                          std::size_t length) {
  if (token == nullptr || length < 16 || length > 128) return false;
  for (std::size_t index = 0; index < length; ++index) {
    char value = token[index];
    bool allowed = (value >= '0' && value <= '9') ||
                   (value >= 'A' && value <= 'Z') ||
                   (value >= 'a' && value <= 'z') || value == '-' || value == '_';
    if (!allowed) return false;
  }
  return true;
}

// A transient permission request can briefly surface as `waiting` even when
// the desktop is allowed to approve it automatically.  Treat waiting as an
// alert candidate first, and only notify after a later fresh state snapshot
// confirms that the same wait has persisted for the configured delay.
struct DashboardWaitingAlertModel {
  int candidateCount = 0;
  int notifiedCount = 0;
  uint32_t candidateSince = 0;
};

inline void dashboardWaitingAlertSeed(DashboardWaitingAlertModel &model,
                                      int currentCount) {
  model = DashboardWaitingAlertModel();
  model.notifiedCount = currentCount > 0 ? currentCount : 0;
}

inline bool dashboardWaitingAlertUpdate(DashboardWaitingAlertModel &model,
                                        int currentCount, uint32_t now,
                                        uint32_t delayMs) {
  if (currentCount <= 0) {
    model = DashboardWaitingAlertModel();
    return false;
  }

  if (model.notifiedCount > currentCount) {
    model.notifiedCount = currentCount;
  }
  if (currentCount <= model.notifiedCount) {
    model.candidateCount = 0;
    model.candidateSince = 0;
    return false;
  }

  if (model.candidateCount != currentCount) {
    model.candidateCount = currentCount;
    model.candidateSince = now;
    return false;
  }
  if (static_cast<uint32_t>(now - model.candidateSince) < delayMs) {
    return false;
  }

  model.notifiedCount = currentCount;
  model.candidateCount = 0;
  model.candidateSince = 0;
  return true;
}

// The stopwatch interaction follows M5Stack's MIT-licensed StopWatch UserDemo:
// stopped: A no-op / B start; running: A lap / B pause;
// paused: A reset / B resume.
// https://github.com/m5stack/M5StopWatch-UserDemo/tree/main/main/apps/app_stopwatch

enum class DashboardAppMode {
  launcher,
  dashboard,
  stopwatch,
  countdownTimer,
};

enum class LocalStopwatchState {
  stopped,
  running,
  paused,
};

constexpr std::size_t kLocalStopwatchMaxLaps = 24;
constexpr std::size_t kLocalStopwatchVisibleLaps = 3;

struct LocalStopwatchModel {
  LocalStopwatchState state = LocalStopwatchState::stopped;
  uint64_t accumulatedMs = 0;
  uint32_t startedAt = 0;
  uint64_t laps[kLocalStopwatchMaxLaps] = {};
  std::size_t lapCount = 0;
};

inline uint64_t localStopwatchElapsedMs(const LocalStopwatchModel &model,
                                        uint32_t now) {
  uint64_t elapsed = model.accumulatedMs;
  if (model.state == LocalStopwatchState::running) {
    elapsed += static_cast<uint32_t>(now - model.startedAt);
  }
  return elapsed;
}

inline void localStopwatchStart(LocalStopwatchModel &model, uint32_t now) {
  if (model.state == LocalStopwatchState::running) return;
  model.startedAt = now;
  model.state = LocalStopwatchState::running;
}

inline void localStopwatchPause(LocalStopwatchModel &model, uint32_t now) {
  if (model.state != LocalStopwatchState::running) return;
  model.accumulatedMs = localStopwatchElapsedMs(model, now);
  model.startedAt = 0;
  model.state = LocalStopwatchState::paused;
}

inline void localStopwatchReset(LocalStopwatchModel &model) {
  model = LocalStopwatchModel();
}

inline void localStopwatchLap(LocalStopwatchModel &model, uint32_t now) {
  if (model.state != LocalStopwatchState::running ||
      model.lapCount >= kLocalStopwatchMaxLaps) {
    return;
  }
  model.laps[model.lapCount++] = localStopwatchElapsedMs(model, now);
}

inline std::size_t localStopwatchMaximumLapOffset(std::size_t lapCount) {
  return lapCount > kLocalStopwatchVisibleLaps
             ? lapCount - kLocalStopwatchVisibleLaps
             : 0;
}

// Offset is measured from the newest three rows. Positive pageDirection moves
// toward older laps; negative pageDirection moves back toward newer laps.
inline std::size_t localStopwatchLapPageOffset(std::size_t currentOffset,
                                               int pageDirection,
                                               std::size_t lapCount) {
  std::size_t maximum = localStopwatchMaximumLapOffset(lapCount);
  if (currentOffset > maximum) currentOffset = maximum;
  if (pageDirection > 0) {
    std::size_t remaining = maximum - currentOffset;
    return currentOffset +
           (remaining < kLocalStopwatchVisibleLaps ? remaining
                                                   : kLocalStopwatchVisibleLaps);
  }
  if (pageDirection < 0) {
    return currentOffset < kLocalStopwatchVisibleLaps
               ? 0
               : currentOffset - kLocalStopwatchVisibleLaps;
  }
  return currentOffset;
}

inline std::size_t localStopwatchFirstVisibleLap(std::size_t lapCount,
                                                 std::size_t offset) {
  std::size_t visible = lapCount < kLocalStopwatchVisibleLaps
                            ? lapCount
                            : kLocalStopwatchVisibleLaps;
  std::size_t maximum = localStopwatchMaximumLapOffset(lapCount);
  if (offset > maximum) offset = maximum;
  return lapCount - visible - offset;
}

inline void localStopwatchLeftAction(LocalStopwatchModel &model, uint32_t now) {
  if (model.state == LocalStopwatchState::running) {
    localStopwatchLap(model, now);
  } else if (model.state == LocalStopwatchState::paused) {
    localStopwatchReset(model);
  }
}

inline void localStopwatchRightAction(LocalStopwatchModel &model, uint32_t now) {
  if (model.state == LocalStopwatchState::running) {
    localStopwatchPause(model, now);
  } else {
    localStopwatchStart(model, now);
  }
}

inline const char *localStopwatchLeftLabel(LocalStopwatchState state) {
  return state == LocalStopwatchState::paused ? "RESET" : "LAP";
}

inline const char *localStopwatchRightLabel(LocalStopwatchState state) {
  return state == LocalStopwatchState::running ? "STOP" : "START";
}

enum class LocalCountdownState {
  idle,
  running,
  paused,
  expired,
  overtimePaused,
};

enum class LocalCountdownAction {
  none,
  started,
  paused,
  resumed,
  reset,
  presetChanged,
  expired,
};

constexpr uint16_t kLocalCountdownMinimumMinutes = 1;
constexpr uint16_t kLocalCountdownMaximumMinutes = 99;

struct LocalCountdownModel {
  LocalCountdownState state = LocalCountdownState::idle;
  uint16_t presetMinutes[2] = {8, 10};
  int8_t activePreset = -1;
  uint64_t accumulatedMs = 0;
  uint32_t startedAt = 0;
};

struct LocalCountdownEditorModel {
  bool open = false;
  uint8_t selectedPreset = 0;
  uint16_t draftMinutes[2] = {8, 10};
};

inline bool localCountdownClockAdvances(LocalCountdownState state) {
  return state == LocalCountdownState::running ||
         state == LocalCountdownState::expired;
}

inline bool localCountdownActive(const LocalCountdownModel &model) {
  return model.state != LocalCountdownState::idle;
}

inline bool localCountdownCanReset(LocalCountdownState state) {
  return state == LocalCountdownState::paused ||
         state == LocalCountdownState::overtimePaused;
}

inline uint64_t localCountdownElapsedMs(const LocalCountdownModel &model,
                                        uint32_t now) {
  uint64_t elapsed = model.accumulatedMs;
  if (localCountdownClockAdvances(model.state)) {
    elapsed += static_cast<uint32_t>(now - model.startedAt);
  }
  return elapsed;
}

inline uint64_t localCountdownTargetMs(const LocalCountdownModel &model) {
  if (model.activePreset < 0 || model.activePreset > 1) return 0;
  return static_cast<uint64_t>(model.presetMinutes[model.activePreset]) *
         60ULL * 1000ULL;
}

inline uint64_t localCountdownRemainingMs(const LocalCountdownModel &model,
                                          uint32_t now) {
  uint64_t target = localCountdownTargetMs(model);
  uint64_t elapsed = localCountdownElapsedMs(model, now);
  return elapsed >= target ? 0 : target - elapsed;
}

inline uint64_t localCountdownOvertimeMs(const LocalCountdownModel &model,
                                         uint32_t now) {
  uint64_t target = localCountdownTargetMs(model);
  uint64_t elapsed = localCountdownElapsedMs(model, now);
  return elapsed > target ? elapsed - target : 0;
}

inline bool localCountdownPresetValid(uint16_t minutes) {
  return minutes >= kLocalCountdownMinimumMinutes &&
         minutes <= kLocalCountdownMaximumMinutes;
}

inline void localCountdownSetPreset(LocalCountdownModel &model,
                                    std::size_t presetIndex,
                                    uint16_t minutes) {
  if (presetIndex > 1 || !localCountdownPresetValid(minutes)) return;
  model.presetMinutes[presetIndex] = minutes;
}

inline bool localCountdownBeginEditing(const LocalCountdownModel &model,
                                       LocalCountdownEditorModel &editor) {
  if (model.state != LocalCountdownState::idle) return false;
  editor.open = true;
  editor.selectedPreset = 0;
  editor.draftMinutes[0] = model.presetMinutes[0];
  editor.draftMinutes[1] = model.presetMinutes[1];
  return true;
}

inline void localCountdownCancelEditing(LocalCountdownEditorModel &editor) {
  editor.open = false;
}

inline bool localCountdownSelectEditorPreset(LocalCountdownEditorModel &editor,
                                             std::size_t presetIndex) {
  if (!editor.open || presetIndex > 1 || editor.selectedPreset == presetIndex) {
    return false;
  }
  editor.selectedPreset = static_cast<uint8_t>(presetIndex);
  return true;
}

inline bool localCountdownSetEditorMinutes(LocalCountdownEditorModel &editor,
                                           int minutes) {
  if (!editor.open || editor.selectedPreset > 1) return false;
  int bounded = minutes;
  if (bounded < static_cast<int>(kLocalCountdownMinimumMinutes)) {
    bounded = kLocalCountdownMinimumMinutes;
  }
  if (bounded > static_cast<int>(kLocalCountdownMaximumMinutes)) {
    bounded = kLocalCountdownMaximumMinutes;
  }
  if (editor.draftMinutes[editor.selectedPreset] == bounded) return false;
  editor.draftMinutes[editor.selectedPreset] = static_cast<uint16_t>(bounded);
  return true;
}

inline bool localCountdownAdjustEditorMinutes(LocalCountdownEditorModel &editor,
                                              int deltaMinutes) {
  if (!editor.open || editor.selectedPreset > 1) return false;
  return localCountdownSetEditorMinutes(
      editor, static_cast<int>(editor.draftMinutes[editor.selectedPreset]) +
                  deltaMinutes);
}

inline int localCountdownWheelSteps(int distancePx) {
  // Preserve two deliberate 32 px detents for precise nearby changes, then
  // accelerate to 12 px per minute so a full-height drag can cross common
  // preset ranges such as 18 -> 5 without repeated swipes.
  constexpr int kFinePixelsPerMinute = 32;
  constexpr int kFineSteps = 2;
  constexpr int kFastPixelsPerMinute = 12;
  constexpr int kFineZonePx = kFinePixelsPerMinute * kFineSteps;
  int magnitude = distancePx < 0 ? -distancePx : distancePx;
  int steps = magnitude <= kFineZonePx
                  ? magnitude / kFinePixelsPerMinute
                  : kFineSteps +
                        (magnitude - kFineZonePx) / kFastPixelsPerMinute;
  return distancePx < 0 ? steps : -steps;
}

inline bool localCountdownCommitEditing(LocalCountdownModel &model,
                                        LocalCountdownEditorModel &editor) {
  if (!editor.open || !localCountdownPresetValid(editor.draftMinutes[0]) ||
      !localCountdownPresetValid(editor.draftMinutes[1])) {
    return false;
  }
  model.presetMinutes[0] = editor.draftMinutes[0];
  model.presetMinutes[1] = editor.draftMinutes[1];
  editor.open = false;
  return true;
}

inline void localCountdownStartPreset(LocalCountdownModel &model,
                                      std::size_t presetIndex,
                                      uint32_t now) {
  if (presetIndex > 1) return;
  model.state = LocalCountdownState::running;
  model.activePreset = static_cast<int8_t>(presetIndex);
  model.accumulatedMs = 0;
  model.startedAt = now;
}

inline void localCountdownPause(LocalCountdownModel &model, uint32_t now) {
  if (model.state != LocalCountdownState::running) return;
  model.accumulatedMs = localCountdownElapsedMs(model, now);
  model.startedAt = 0;
  model.state = LocalCountdownState::paused;
}

inline void localCountdownResume(LocalCountdownModel &model, uint32_t now) {
  if (model.state != LocalCountdownState::paused) return;
  model.startedAt = now;
  model.state = LocalCountdownState::running;
}

inline void localCountdownPauseOvertime(LocalCountdownModel &model,
                                        uint32_t now) {
  if (model.state != LocalCountdownState::expired) return;
  model.accumulatedMs = localCountdownElapsedMs(model, now);
  model.startedAt = 0;
  model.state = LocalCountdownState::overtimePaused;
}

inline void localCountdownResumeOvertime(LocalCountdownModel &model,
                                         uint32_t now) {
  if (model.state != LocalCountdownState::overtimePaused) return;
  model.startedAt = now;
  model.state = LocalCountdownState::expired;
}

inline void localCountdownReset(LocalCountdownModel &model) {
  model.state = LocalCountdownState::idle;
  model.activePreset = -1;
  model.accumulatedMs = 0;
  model.startedAt = 0;
}

inline LocalCountdownAction localCountdownPresetAction(
    LocalCountdownModel &model, std::size_t presetIndex, uint32_t now) {
  if (presetIndex > 1) return LocalCountdownAction::none;
  if (model.state == LocalCountdownState::idle) {
    localCountdownStartPreset(model, presetIndex, now);
    return LocalCountdownAction::started;
  }
  if (model.activePreset != static_cast<int8_t>(presetIndex)) {
    return LocalCountdownAction::none;
  }
  if (model.state == LocalCountdownState::running) {
    localCountdownPause(model, now);
    return LocalCountdownAction::paused;
  }
  if (model.state == LocalCountdownState::paused) {
    localCountdownResume(model, now);
    return LocalCountdownAction::resumed;
  }
  if (model.state == LocalCountdownState::expired) {
    localCountdownPauseOvertime(model, now);
    return LocalCountdownAction::paused;
  }
  if (model.state == LocalCountdownState::overtimePaused) {
    localCountdownResumeOvertime(model, now);
    return LocalCountdownAction::resumed;
  }
  return LocalCountdownAction::none;
}

inline LocalCountdownAction localCountdownUpdate(LocalCountdownModel &model,
                                                  uint32_t now) {
  if (model.state != LocalCountdownState::running ||
      localCountdownElapsedMs(model, now) < localCountdownTargetMs(model)) {
    return LocalCountdownAction::none;
  }
  model.state = LocalCountdownState::expired;
  return LocalCountdownAction::expired;
}

enum class AppShellTouchTarget {
  none,
  dashboard,
  stopwatch,
  countdownTimer,
  leftAction,
  rightAction,
  presetA,
  presetB,
  wheelAction,
  resetAction,
  setAction,
  cancelAction,
  saveAction,
};

inline AppShellTouchTarget appLauncherTouchTarget(int x, int y) {
  if (x >= 25 && x <= 145 && y >= 138 && y <= 324) {
    return AppShellTouchTarget::dashboard;
  }
  if (x >= 165 && x <= 285 && y >= 138 && y <= 324) {
    return AppShellTouchTarget::stopwatch;
  }
  if (x >= 305 && x <= 425 && y >= 138 && y <= 324) {
    return AppShellTouchTarget::countdownTimer;
  }
  return AppShellTouchTarget::none;
}

inline AppShellTouchTarget localStopwatchTouchTarget(int x, int y) {
  if (x >= 86 && x <= 215 && y >= 44 && y <= 136) {
    return AppShellTouchTarget::leftAction;
  }
  if (x >= 235 && x <= 364 && y >= 44 && y <= 136) {
    return AppShellTouchTarget::rightAction;
  }
  return AppShellTouchTarget::none;
}

inline bool localStopwatchLapRegionContains(int x, int y) {
  return x >= 42 && x <= 408 && y >= 252 && y <= 400;
}

inline AppShellTouchTarget localCountdownTouchTarget(int x, int y) {
  if (x >= 64 && x <= 224 && y >= 330 && y <= 426) {
    return AppShellTouchTarget::resetAction;
  }
  if (x >= 226 && x <= 386 && y >= 330 && y <= 426) {
    return AppShellTouchTarget::setAction;
  }
  return AppShellTouchTarget::none;
}

inline AppShellTouchTarget localCountdownSettingsTouchTarget(int x, int y) {
  if (x >= 58 && x <= 210 && y >= 48 && y <= 126) {
    return AppShellTouchTarget::presetA;
  }
  if (x >= 240 && x <= 392 && y >= 48 && y <= 126) {
    return AppShellTouchTarget::presetB;
  }
  if (x >= 82 && x <= 368 && y >= 136 && y <= 326) {
    return AppShellTouchTarget::wheelAction;
  }
  if (x >= 64 && x <= 224 && y >= 330 && y <= 426) {
    return AppShellTouchTarget::cancelAction;
  }
  if (x >= 226 && x <= 386 && y >= 330 && y <= 426) {
    return AppShellTouchTarget::saveAction;
  }
  return AppShellTouchTarget::none;
}
