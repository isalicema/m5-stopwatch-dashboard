#include "provisioning.h"

#include <WiFi.h>


namespace {

constexpr char kAccessPointPassword[] = "m5dashboard";

const char kPagePrefix[] PROGMEM = R"HTML(
<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>M5 监控屏配网</title><style>
*{box-sizing:border-box}body{margin:0;background:#080a0d;color:#f4f5f6;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
main{max-width:520px;margin:auto;padding:28px 20px 48px}h1{font-size:25px;margin:0 0 8px}.sub{color:#9da3ad;margin:0 0 26px;line-height:1.6}
section{margin:18px 0 26px;padding:18px;border:1px solid #292e37;border-radius:16px;background:#0d1015}h2{font-size:18px;margin:0 0 4px}label{display:block;margin:16px 0 7px;color:#c8ccd2;font-size:14px}input,select{width:100%;border:1px solid #343943;border-radius:12px;background:#12151a;color:#fff;padding:13px 14px;font-size:16px;outline:none}
input:focus,select:focus{border-color:#6d78ff}select{appearance:auto}small{display:block;color:#858b96;margin-top:7px;line-height:1.5}button{width:100%;margin-top:26px;border:0;border-radius:13px;background:#5865f2;color:#fff;padding:14px;font-size:17px;font-weight:600}
.tip{margin-top:24px;padding:15px;border-radius:12px;background:#111820;color:#aab3bd;line-height:1.6;font-size:14px}</style></head><body><main>
<h1>M5 监控屏配网</h1><p class="sub">可同时保存家庭和公司两套配置。设备开机后会自动连接当前能用的网络，不需要手动切换。</p>
<form method="post" action="/save"><section><h2>家庭</h2>
<label>从附近网络选择</label><select onchange="if(this.value)document.getElementById('home-ssid').value=this.value">
<option value="">点击选择附近 Wi-Fi</option>%NETWORK_OPTIONS%</select>
<label>家庭 Wi-Fi 名称</label>
)HTML";

const char kPageSuffix[] PROGMEM = R"HTML(
<label>家庭 Wi-Fi 密码</label><input name="password" type="password" autocomplete="new-password" placeholder="留空则保留现有密码">
<label>家庭 Mac 令牌</label><input name="token" type="password" autocomplete="off" placeholder="留空则保留现有令牌"></section>
<section><h2>公司</h2>
<label>从附近网络选择</label><select onchange="if(this.value)document.getElementById('work-ssid').value=this.value">
<option value="">点击选择附近 Wi-Fi</option>%NETWORK_OPTIONS%</select>
<label>公司 Wi-Fi 名称</label><input id="work-ssid" name="ssid2" value="%SSID2%" placeholder="尚未设置">
<label>公司 Wi-Fi 密码</label><input name="password2" type="password" autocomplete="new-password" placeholder="留空则保留现有密码">
<label>公司 MacBook 令牌</label><input name="token2" type="password" autocomplete="off" placeholder="留空则保留现有令牌"></section>
<small>支持普通 2.4GHz Wi-Fi。企业证书、网页认证和禁止设备互访的网络不能直接使用。</small>
<label>Mac 桥接地址（可选）</label><input name="host" value="%HOST%" placeholder="留空自动发现">
<label>桥接端口</label><input name="port" type="number" min="1" max="65535" value="%PORT%">
<button type="submit">保存并重启</button></form>
<div class="tip">桥接地址建议留空。设备会自动发现当前地点的 Mac，并自动尝试两台 Mac 的令牌；密码和令牌不会被广播。</div>
</main></body></html>
)HTML";

}  // namespace


ProvisioningPortal::ProvisioningPortal() : server_(80) {}


String ProvisioningPortal::htmlEscape(const String &value) const {
  String escaped;
  escaped.reserve(value.length() + 16);
  for (size_t i = 0; i < value.length(); ++i) {
    switch (value[i]) {
      case '&': escaped += F("&amp;"); break;
      case '<': escaped += F("&lt;"); break;
      case '>': escaped += F("&gt;"); break;
      case '"': escaped += F("&quot;"); break;
      case '\'': escaped += F("&#39;"); break;
      default: escaped += value[i];
    }
  }
  return escaped;
}


bool ProvisioningPortal::begin(const DashboardSettings &current, const String &apName) {
  current_ = current;
  apName_ = apName;
  restartAt_ = 0;
  networkOptions_ = "";

  WiFi.disconnect(true);
  delay(200);
  WiFi.mode(WIFI_STA);
  int count = WiFi.scanNetworks(false, true);
  for (int index = 0; index < count && index < 24; ++index) {
    String ssid = WiFi.SSID(index);
    String escapedSsid = htmlEscape(ssid);
    if (ssid.length() == 0 ||
        networkOptions_.indexOf("value=\"" + escapedSsid + "\"") >= 0) {
      continue;
    }
    networkOptions_ +=
        "<option value=\"" + escapedSsid + "\">" + escapedSsid + "</option>";
  }
  WiFi.scanDelete();

  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(apName_.c_str(), kAccessPointPassword)) return false;
  dns_.start(53, "*", WiFi.softAPIP());

  server_.on("/", HTTP_GET, [this]() { handleRoot(); });
  server_.on("/save", HTTP_POST, [this]() { handleSave(); });
  server_.on("/generate_204", HTTP_ANY, [this]() { redirectToRoot(); });
  server_.on("/hotspot-detect.html", HTTP_ANY, [this]() { redirectToRoot(); });
  server_.on("/connecttest.txt", HTTP_ANY, [this]() { redirectToRoot(); });
  server_.onNotFound([this]() { redirectToRoot(); });
  server_.begin();
  return true;
}


String ProvisioningPortal::page() const {
  String body = FPSTR(kPagePrefix);
  body.replace("%NETWORK_OPTIONS%", networkOptions_);
  body += "<input id=\"home-ssid\" name=\"ssid\" value=\"" +
          htmlEscape(current_.ssid) + "\" required>";
  String suffix = FPSTR(kPageSuffix);
  suffix.replace("%NETWORK_OPTIONS%", networkOptions_);
  suffix.replace("%SSID2%", htmlEscape(current_.ssid2));
  suffix.replace("%HOST%", htmlEscape(current_.host));
  suffix.replace("%PORT%", String(current_.port));
  body += suffix;
  return body;
}


void ProvisioningPortal::handleRoot() {
  server_.sendHeader("Cache-Control", "no-store");
  server_.send(200, "text/html; charset=utf-8", page());
}


void ProvisioningPortal::handleSave() {
  DashboardSettings next = current_;
  String newSsid = server_.arg("ssid");
  newSsid.trim();
  if (newSsid.length() == 0 || newSsid.length() > 64) {
    server_.send(400, "text/plain; charset=utf-8", "Wi-Fi 名称无效");
    return;
  }

  String newPassword = server_.arg("password");
  if (newSsid != current_.ssid || newPassword.length() > 0) next.password = newPassword;
  next.ssid = newSsid;

  String newSsid2 = server_.arg("ssid2");
  newSsid2.trim();
  if (newSsid2.length() > 64) {
    server_.send(400, "text/plain; charset=utf-8", "公司 Wi-Fi 名称无效");
    return;
  }
  String newPassword2 = server_.arg("password2");
  if (newSsid2.length() == 0) {
    next.ssid2 = "";
    next.password2 = "";
  } else {
    if (newSsid2 != current_.ssid2 || newPassword2.length() > 0) next.password2 = newPassword2;
    next.ssid2 = newSsid2;
  }

  next.host = server_.arg("host");
  next.host.trim();
  if (next.host.length() > 253) {
    server_.send(400, "text/plain; charset=utf-8", "桥接地址无效");
    return;
  }

  long port = server_.arg("port").toInt();
  if (port < 1 || port > 65535) {
    server_.send(400, "text/plain; charset=utf-8", "桥接端口无效");
    return;
  }
  next.port = static_cast<uint16_t>(port);

  String newToken = server_.arg("token");
  if (newToken.length() > 0) next.token = newToken;
  if (next.token.length() < 16 || next.token.length() > 256) {
    server_.send(400, "text/plain; charset=utf-8", "桥接令牌无效");
    return;
  }

  String newToken2 = server_.arg("token2");
  if (newToken2.length() > 0) next.token2 = newToken2;
  if (next.token2.length() > 0 && (next.token2.length() < 16 || next.token2.length() > 256)) {
    server_.send(400, "text/plain; charset=utf-8", "公司 MacBook 令牌无效");
    return;
  }

  if (!saveDashboardSettings(next)) {
    server_.send(500, "text/plain; charset=utf-8", "保存失败，请重试");
    return;
  }
  server_.send(200, "text/html; charset=utf-8",
               "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
               "<body style='background:#080a0d;color:#fff;font-family:sans-serif;padding:32px'>"
               "<h2>保存成功</h2><p>设备正在重启，可以关闭此页面。</p></body>");
  restartAt_ = millis() + 1500;
}


void ProvisioningPortal::redirectToRoot() {
  server_.sendHeader("Location", "http://192.168.4.1/", true);
  server_.send(302, "text/plain", "");
}


void ProvisioningPortal::handle() {
  dns_.processNextRequest();
  server_.handleClient();
  if (restartAt_ != 0 && static_cast<int32_t>(millis() - restartAt_) >= 0) ESP.restart();
}
