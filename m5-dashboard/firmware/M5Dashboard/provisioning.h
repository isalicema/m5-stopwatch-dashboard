#pragma once

#include <Arduino.h>
#include <DNSServer.h>
#include <WebServer.h>
#include <WiFi.h>

#include "device_config.h"


class ProvisioningPortal {
 public:
  ProvisioningPortal();

  bool begin(const DashboardSettings &current, const String &apName);
  void handle();
  const String &apName() const { return apName_; }
  IPAddress address() const { return WiFi.softAPIP(); }

 private:
  String htmlEscape(const String &value) const;
  String page() const;
  void handleRoot();
  void handleSave();
  void redirectToRoot();

  DNSServer dns_;
  WebServer server_;
  DashboardSettings current_;
  String apName_;
  String networkOptions_;
  uint32_t restartAt_ = 0;
};
