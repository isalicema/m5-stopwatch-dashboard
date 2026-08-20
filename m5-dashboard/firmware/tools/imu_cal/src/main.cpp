// ───────────────────────────────────────────────────────────────────────────
// M0：IMU / RTC 标定小程序（一次性工具）
//
// 在屏幕和串口上实时显示 BMI270 三轴加速度、重力朝向、粗略姿态标签，以及
// RTC 当前时间 / 掉电标志。用来确定这块 StopWatch 上 BMI270 的默认轴向，
// 给正式固件的 imu_logic.h 定标。
//
// 不写 NVS、不触碰正式固件的任何状态。用法见同目录 platformio.ini。
// ───────────────────────────────────────────────────────────────────────────
#include <M5Unified.h>

#include <math.h>
#include <stdio.h>

namespace {

M5Canvas canvas(&M5.Display);
uint32_t lastDrawAt = 0;

// 返回重力主要落在哪个轴（|值| 最大者）及其带符号值。
const char *dominantAxis(float ax, float ay, float az, float &signedOut) {
  float mx = fabsf(ax), my = fabsf(ay), mz = fabsf(az);
  if (mx >= my && mx >= mz) { signedOut = ax; return ax >= 0 ? "+X" : "-X"; }
  if (my >= mx && my >= mz) { signedOut = ay; return ay >= 0 ? "+Y" : "-Y"; }
  signedOut = az;
  return az >= 0 ? "+Z" : "-Z";
}

// 仅用于辅助确认轴向直觉的粗略姿态标签（阈值只影响显示，不影响数据）。
const char *posture(float ax, float ay, float az) {
  if (az > 0.7f) return "平放? 正面朝上";
  if (az < -0.7f) return "平放? 屏幕朝下";
  if (ay > 0.7f) return "竖直? +Y 朝上";
  if (ay < -0.7f) return "竖直? -Y 朝上";
  if (ax > 0.7f) return "倾斜? +X 朝下";
  if (ax < -0.7f) return "倾斜? -X 朝下";
  return "倾斜中";
}

template <typename TFont>
void drawLine(const char *text, int y, uint16_t color, const TFont &font) {
  canvas.setFont(&font);
  canvas.setTextSize(1);
  canvas.setTextColor(color);
  canvas.drawString(text, canvas.width() / 2, y);
}

}  // namespace

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);  // 默认 internal_imu / internal_rtc = true，自动带起 BMI270+RX8130
  M5.Display.setRotation(0);
  M5.Display.setBrightness(180);
  canvas.setColorDepth(16);
  canvas.createSprite(M5.Display.width(), M5.Display.height());
  Serial.begin(115200);
  Serial.printf("M0 IMU/RTC calibration | IMU enabled=%d  RTC enabled=%d\n",
                (int)M5.Imu.isEnabled(), (int)M5.Rtc.isEnabled());
}

void loop() {
  M5.update();
  M5.Imu.update();

  uint32_t now = millis();
  if (now - lastDrawAt < 100) {
    delay(5);
    return;
  }
  lastDrawAt = now;

  float ax = 0, ay = 0, az = 0;
  bool imuOk = M5.Imu.isEnabled() && M5.Imu.getAccel(&ax, &ay, &az);

  bool rtcEnabled = M5.Rtc.isEnabled();
  m5::rtc_datetime_t dt;
  bool rtcOk = rtcEnabled && M5.Rtc.getDateTime(&dt);
  bool voltLow = rtcEnabled ? M5.Rtc.getVoltLow() : true;

  float dom = 0;
  const char *domAxis = imuOk ? dominantAxis(ax, ay, az, dom) : "--";
  const char *pose = imuOk ? posture(ax, ay, az) : "IMU 不可用";

  // ── 串口（方便 pio device monitor 里复制粘贴给我）──
  if (imuOk) {
    Serial.printf("ACC ax=%+.2f ay=%+.2f az=%+.2f  down=%s  %s\n", ax, ay, az,
                  domAxis, pose);
  } else {
    Serial.println("IMU not available");
  }

  // ── 屏幕 ──
  const int cx = canvas.width() / 2;
  canvas.fillSprite(canvas.color565(6, 8, 14));
  canvas.setTextDatum(middle_center);

  drawLine("IMU / RTC 标定 (M0)", 66, canvas.color565(120, 128, 255),
           fonts::efontCN_16);

  char line[64];
  uint16_t accColor =
      imuOk ? canvas.color565(232, 233, 240) : canvas.color565(232, 96, 96);
  snprintf(line, sizeof(line), "ax %+.2f", ax);
  drawLine(line, 138, accColor, fonts::Font4);
  snprintf(line, sizeof(line), "ay %+.2f", ay);
  drawLine(line, 176, accColor, fonts::Font4);
  snprintf(line, sizeof(line), "az %+.2f", az);
  drawLine(line, 214, accColor, fonts::Font4);

  snprintf(line, sizeof(line), "重力朝向 down = %s", domAxis);
  drawLine(line, 256, canvas.color565(90, 220, 130), fonts::efontCN_16);
  drawLine(pose, 284, canvas.color565(214, 200, 120), fonts::efontCN_16);

  if (rtcOk) {
    snprintf(line, sizeof(line), "RTC %04d-%02d-%02d %02d:%02d:%02d",
             (int)dt.date.year, (int)dt.date.month, (int)dt.date.date,
             (int)dt.time.hours, (int)dt.time.minutes, (int)dt.time.seconds);
  } else {
    snprintf(line, sizeof(line), "RTC %s", rtcEnabled ? "读取失败" : "未启用");
  }
  drawLine(line, 328,
           rtcOk ? canvas.color565(200, 205, 220) : canvas.color565(232, 150, 90),
           fonts::efontCN_16);
  drawLine(voltLow ? "RTC 掉电过，需校时" : "RTC 供电正常", 354,
           voltLow ? canvas.color565(232, 150, 90) : canvas.color565(120, 128, 140),
           fonts::efontCN_16);

  drawLine("姿势: 朝上/朝下/竖直/左右倾  各停 2 秒", 398,
           canvas.color565(130, 135, 150), fonts::efontCN_16);

  canvas.pushSprite(0, 0);
}
