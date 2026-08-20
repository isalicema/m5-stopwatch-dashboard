#pragma once

#include <cstddef>
#include <cstdint>

enum class DashboardCodexIconMode {
  idle,
  working,
  waiting,
  done,
  failed,
};

inline bool dashboardDeadlinePending(uint32_t now, uint32_t deadline) {
  return deadline != 0 && static_cast<int32_t>(deadline - now) > 0;
}

inline DashboardCodexIconMode selectDashboardCodexIconMode(
    bool connected, int active, int waiting, int errors, bool doneVisible) {
  if (!connected) return DashboardCodexIconMode::idle;
  if (waiting > 0) return DashboardCodexIconMode::waiting;
  if (active > 0) return DashboardCodexIconMode::working;
  if (errors > 0) return DashboardCodexIconMode::failed;
  if (doneVisible) return DashboardCodexIconMode::done;
  return DashboardCodexIconMode::idle;
}

inline size_t dashboardAnimationFrame(uint32_t now, uint32_t intervalMs,
                                      size_t frameCount) {
  if (intervalMs == 0 || frameCount == 0) return 0;
  return static_cast<size_t>(now / intervalMs) % frameCount;
}

inline uint8_t dashboardClaudeScalePercent(size_t frame) {
  constexpr uint8_t scales[] = {92, 95, 99, 104, 108, 104, 99, 95};
  return scales[frame % (sizeof(scales) / sizeof(scales[0]))];
}

constexpr uint32_t kDashboardCompletionDurationMs = 2000;

struct DashboardCompletionAnimationFrame {
  bool visible = false;
  uint16_t ringDegrees = 0;
  uint8_t claudeIconScalePercent = 150;
  uint8_t codexFrameIndex = 0;
  uint16_t successRadius = 0;
  uint8_t intensityPercent = 100;
};

constexpr uint16_t kDashboardCompletionFullRadius = 340;

inline uint16_t dashboardCompletionSmoothPermille(uint32_t elapsed,
                                                  uint32_t duration) {
  if (duration == 0 || elapsed >= duration) return 1000;
  uint64_t t = static_cast<uint64_t>(elapsed) * 1000 / duration;
  return static_cast<uint16_t>(t * t * (3000 - 2 * t) / 1000000);
}

inline DashboardCompletionAnimationFrame dashboardCompletionAnimationFrame(
    uint32_t elapsedMs) {
  DashboardCompletionAnimationFrame frame;
  if (elapsedMs >= kDashboardCompletionDurationMs) return frame;

  frame.visible = true;
  frame.ringDegrees = elapsedMs >= 1000
                          ? 360
                          : static_cast<uint16_t>(elapsedMs * 360 / 1000);

  if (elapsedMs < 180) {
    frame.codexFrameIndex = 0;
  } else if (elapsedMs < 330) {
    frame.codexFrameIndex = 1;
  } else if (elapsedMs < 500) {
    frame.codexFrameIndex = 2;
  } else {
    frame.codexFrameIndex = 1;
  }

  if (elapsedMs < 280) {
    frame.claudeIconScalePercent =
        static_cast<uint8_t>(141 + elapsedMs * 15 / 280);
  } else if (elapsedMs < 500) {
    frame.claudeIconScalePercent =
        static_cast<uint8_t>(156 - (elapsedMs - 280) * 6 / 220);
  }

  if (elapsedMs >= 1000 && elapsedMs < 1140) {
    frame.successRadius =
        static_cast<uint16_t>((elapsedMs - 1000) * 64 / 140);
  } else if (elapsedMs < 1230 && elapsedMs >= 1140) {
    frame.successRadius =
        static_cast<uint16_t>(64 - (elapsedMs - 1140) * 6 / 90);
  } else if (elapsedMs >= 1230 && elapsedMs < 1700) {
    uint16_t smooth =
        dashboardCompletionSmoothPermille(elapsedMs - 1230, 470);
    frame.successRadius = static_cast<uint16_t>(
        58 + (kDashboardCompletionFullRadius - 58) * smooth / 1000);
  } else if (elapsedMs >= 1700) {
    frame.successRadius = kDashboardCompletionFullRadius;
    frame.intensityPercent = static_cast<uint8_t>(
        (kDashboardCompletionDurationMs - elapsedMs) * 100 / 300);
  }
  return frame;
}
