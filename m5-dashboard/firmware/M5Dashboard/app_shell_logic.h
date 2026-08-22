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

// The stopwatch interaction follows M5Stack's MIT-licensed StopWatch UserDemo:
// stopped: A no-op / B start; running: A lap / B pause;
// paused: A reset / B resume.
// https://github.com/m5stack/M5StopWatch-UserDemo/tree/main/main/apps/app_stopwatch

enum class DashboardAppMode {
  launcher,
  dashboard,
  stopwatch,
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

enum class AppShellTouchTarget {
  none,
  dashboard,
  stopwatch,
  leftAction,
  rightAction,
};

inline AppShellTouchTarget appLauncherTouchTarget(int x, int y) {
  if (x >= 62 && x <= 212 && y >= 132 && y <= 332) {
    return AppShellTouchTarget::dashboard;
  }
  if (x >= 238 && x <= 388 && y >= 132 && y <= 332) {
    return AppShellTouchTarget::stopwatch;
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
