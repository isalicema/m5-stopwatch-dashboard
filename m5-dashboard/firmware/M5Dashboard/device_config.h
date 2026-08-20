#pragma once

#include <Arduino.h>


struct DashboardSettings {
  // Home / primary network. Existing single-network installs migrate here.
  String ssid;
  String password;
  // Work / secondary network. Both profiles are tried automatically.
  String ssid2;
  String password2;
  String host;
  uint16_t port = 8765;
  // One token per Mac. The firmware tries both, so they do not need to match.
  String token;
  String token2;
};


DashboardSettings loadDashboardSettings(const DashboardSettings &defaults);
bool saveDashboardSettings(const DashboardSettings &settings);
