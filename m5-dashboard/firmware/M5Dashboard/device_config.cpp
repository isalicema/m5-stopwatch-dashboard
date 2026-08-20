#include "device_config.h"

#include <Preferences.h>


namespace {

constexpr char kNamespace[] = "m5dash";
constexpr uint8_t kSettingsVersion = 3;

}  // namespace


DashboardSettings loadDashboardSettings(const DashboardSettings &defaults) {
  Preferences prefs;
  DashboardSettings value = defaults;
  if (!prefs.begin(kNamespace, false)) return value;

  if (!prefs.getBool("seeded", false)) {
    prefs.putString("ssid", defaults.ssid);
    prefs.putString("password", defaults.password);
    prefs.putString("ssid2", defaults.ssid2);
    prefs.putString("password2", defaults.password2);
    // Automatic discovery is the default. A fixed address can still be entered in the portal.
    prefs.putString("host", "");
    prefs.putUShort("port", defaults.port);
    prefs.putString("token", defaults.token);
    prefs.putString("token2", defaults.token2);
    prefs.putBool("seeded", true);
    prefs.putUChar("version", kSettingsVersion);
  } else {
    uint8_t version = prefs.getUChar("version", 1);
    if (version < 2) {
      // v1 firmware compiled the old Mac IP into NVS. Migrate once to discovery mode.
      prefs.putString("host", "");
    }
    if (version < 3) {
      // Preserve the original network and token as the home profile, then add
      // empty work slots. This upgrade never erases a working installation.
      prefs.putString("ssid2", "");
      prefs.putString("password2", "");
      prefs.putString("token2", "");
    }
    if (version < kSettingsVersion) prefs.putUChar("version", kSettingsVersion);
  }

  value.ssid = prefs.getString("ssid", defaults.ssid);
  value.password = prefs.getString("password", defaults.password);
  value.ssid2 = prefs.getString("ssid2", defaults.ssid2);
  value.password2 = prefs.getString("password2", defaults.password2);
  value.host = prefs.getString("host", defaults.host);
  value.port = prefs.getUShort("port", defaults.port);
  value.token = prefs.getString("token", defaults.token);
  value.token2 = prefs.getString("token2", defaults.token2);
  prefs.end();

  if (value.port == 0) value.port = 8765;
  return value;
}


bool saveDashboardSettings(const DashboardSettings &settings) {
  Preferences prefs;
  if (!prefs.begin(kNamespace, false)) return false;
  bool ok = true;
  ok = prefs.putString("ssid", settings.ssid) > 0 && ok;
  // Empty passwords are valid for open Wi-Fi networks.
  prefs.putString("password", settings.password);
  prefs.putString("ssid2", settings.ssid2);
  prefs.putString("password2", settings.password2);
  prefs.putString("host", settings.host);
  ok = prefs.putUShort("port", settings.port) > 0 && ok;
  ok = prefs.putString("token", settings.token) > 0 && ok;
  prefs.putString("token2", settings.token2);
  ok = prefs.putBool("seeded", true) > 0 && ok;
  ok = prefs.putUChar("version", kSettingsVersion) > 0 && ok;
  prefs.end();
  return ok;
}
