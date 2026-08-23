#pragma once

#include <stddef.h>
#include <stdint.h>

constexpr size_t kDashboardFactoryOtaPartitionSize = 0x4F0000;
constexpr int kDashboardOtaMinimumBatteryPercent = 40;

inline bool dashboardOtaSha256Valid(const char *value, size_t length) {
  if (value == nullptr || length != 64) return false;
  for (size_t index = 0; index < length; ++index) {
    char item = value[index];
    if (!((item >= '0' && item <= '9') || (item >= 'a' && item <= 'f'))) return false;
  }
  return true;
}

inline bool dashboardOtaSizeValid(size_t imageSize, size_t partitionSize) {
  return imageSize > 0 && imageSize <= kDashboardFactoryOtaPartitionSize &&
         imageSize <= partitionSize;
}

inline bool dashboardOtaCanStart(bool wifiConnected, bool bridgeConnected,
                                 bool screenLocked, bool configMode,
                                 bool voiceActive, bool timerActive,
                                 bool animationActive, int batteryPercent,
                                 bool usbPowered) {
  return wifiConnected && bridgeConnected && !screenLocked && !configMode &&
         !voiceActive && !timerActive && !animationActive &&
         (usbPowered || batteryPercent >= kDashboardOtaMinimumBatteryPercent);
}
