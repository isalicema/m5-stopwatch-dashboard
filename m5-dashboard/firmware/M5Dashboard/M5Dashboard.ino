#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <M5Unified.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp32-hal-cpu.h>
#include <time.h>

#include "ui_font_noto_sans_sc_16.h"

#if defined(M5DASH_USB_AUDIO)
#include <USB.h>
#include <USBAudioCard.h>
#include <atomic>
#include "esp32-hal-tinyusb.h"
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <tusb.h>
#if !defined(CONFIG_TINYUSB_AUDIO_ENABLED) || !CONFIG_TINYUSB_AUDIO_ENABLED
#error "M5DASH_USB_AUDIO requires TinyUSB Audio support"
#endif
#endif

#include "device_config.h"
#include "claude_icon.h"
#include "codex_pet_frames.h"
#include "icon_animation.h"
#include "icons.h"
#include "interaction_logic.h"
#include "provisioning.h"

namespace {

#if defined(M5DASH_USB_AUDIO)
USBCDC dashboardUsbSerial;
USBAudioCard dashboardUsbAudio(48000, UAC_BPS_16, UAC_SPK_NONE, UAC_MIC_MONO);
Stream &dashboardBridgeSerial = dashboardUsbSerial;
#else
Stream &dashboardBridgeSerial = Serial;
#endif

M5Canvas canvas(&M5.Display);
M5Canvas frameCanvas(&M5.Display);
M5Canvas transitionCanvas(&M5.Display);
M5Canvas iconCanvas(&M5.Display);

#if M5DASH_HAS_NOTO_UI_FONT
lgfx::VLWfont uiChineseFont;
lgfx::PointerWrapper uiChineseFontData;
#endif
bool uiChineseFontReady = false;

constexpr size_t kMaxTranscriptTasks = 2;
constexpr size_t kMaxTranscriptMessages = 6;
constexpr size_t kVisibleTranscriptMessages = 3;

struct TranscriptMessage {
  bool user = false;
  String text;
};

struct TranscriptTask {
  String id;
  String title;
  String status;
  size_t messageCount = 0;
  TranscriptMessage messages[kMaxTranscriptMessages];
};

struct TranscriptCollection {
  size_t taskCount = 0;
  TranscriptTask tasks[kMaxTranscriptTasks];
};

constexpr size_t kMaxDashboardResults = 6;

struct DashboardResult {
  char provider = 'C';
  String title;
  int64_t completedAt = 0;
};

struct DashboardResultCollection {
  size_t count = 0;
  DashboardResult items[kMaxDashboardResults];
};

struct WeatherData {
  bool available = false;
  float temperatureC = 0;
  int code = -1;
  int64_t updatedAt = 0;
  String city = "苏州";
  String label;
};

struct PrinterData {
  bool connected = false;
  int progress = 0;
  int remainingMin = 0;
  float nozzle = 0;
  float bed = 0;
  float chamber = 0;
  int layer = 0;
  int totalLayers = 0;
  String state = "OFFLINE";
  String file = "";
};

struct CodexData {
  bool connected = false;
  int active = 0;
  int waiting = 0;
  int errors = 0;
  int weekUsedPercent = -1;
  int weekResetInMin = -1;
  int shortUsedPercent = -1;
  int shortResetInMin = -1;
  int64_t todayTokens = 0;
  int64_t lifetimeTokens = 0;
  String firstTitle = "";
  String firstStatus = "";
};

PrinterData printer;
CodexData codex;
CodexData claude;
TranscriptCollection codexTranscripts;
TranscriptCollection claudeTranscripts;
DashboardResultCollection dashboardResults;
WeatherData weather;
DashboardSettings settings;
ProvisioningPortal provisioning;
WiFiUDP discoveryUdp;
bool haveData = false;
bool bridgeOnline = false;
bool usbBridgeOnline = false;
bool configMode = false;
bool discoveryUdpStarted = false;
bool configHoldTriggered = false;
int currentPage = 0;
constexpr int pageCount = 4;
constexpr uint16_t kDiscoveryPort = 8766;
constexpr uint16_t kDiscoveryLocalPort = 42101;
String activeBridgeHost;
uint16_t activeBridgePort = 8765;
uint32_t lastFetchAt = 0;
uint32_t lastWifiAttemptAt = 0;
uint32_t wifiSearchStartedAt = 0;
uint32_t wifiAttemptStartedAt = 0;
uint32_t lastDiscoveryAt = 0;
int wifiAttemptProfile = -1;
int wifiManualProfile = -1;
bool wifiAttemptInProgress = false;
bool wifiManualSwitchPending = false;
bool wifiReconnectPaused = false;
String wifiPickerMessage;
bool transcriptClaude = false;
int transcriptTaskIndex = -1;
int transcriptOffsetFromNewest = 0;
int lastBridgeHttpStatus = 0;
int activeTokenSlot = -1;
int activeUsbTokenSlot = -1;
int pendingUsbTokenSlot = -1;
String connectedSsid;
String usbResponseLine;
uint32_t lastUsbRequestAt = 0;
uint32_t lastUsbStateAt = 0;
uint32_t vibrationStopAt = 0;
uint32_t lastBatteryReadAt = 0;
int deviceBatteryLevel = -1;
bool deviceCharging = false;
volatile bool screenLocked = false;
DashboardPowerButtonState powerButtonState;
bool transitionCanvasReady = false;
bool frameCanvasReady = false;
bool iconCanvasReady = false;
bool configChordActive = false;
int brightnessPercent = 50;
int notificationVolumePercent = 40;
int lastAudibleVolumePercent = 40;
bool notificationMuted = false;
bool speakerOutputEnabled = false;
uint32_t lastAudioPowerGuardAt = 0;
uint32_t lastVibrationPowerGuardAt = 0;
DashboardGesture activeGesture = DashboardGesture::none;
bool touchPending = false;
int gestureStartBrightness = 50;
int gestureStartVolume = 40;
int lastControlHapticStep = -1;
uint32_t lastStateAppliedAt = 0;
uint32_t lastHighPerformanceAt = 0;
bool cpuLowPower = false;
volatile bool voiceCaptureActive = false;
bool voiceSessionActive = false;
bool voiceButtonTracking = false;
bool voiceButtonConsumed = false;
uint32_t voiceButtonPressedAt = 0;
bool aButtonTracking = false;
bool aButtonConsumed = false;
bool aButtonLongTriggered = false;
uint32_t aButtonPressedAt = 0;
bool provisioningTouchPending = false;
RTC_DATA_ATTR bool openWifiPickerAfterRestart = false;
volatile bool voiceCaptureFailed = false;
bool usbAudioReady = false;
uint32_t lastVoiceAnimationAt = 0;
uint32_t lastIconAnimationAt = 0;
uint32_t codexDoneAnimationUntilAt = 0;
bool completionAnimationRunning = false;
uint32_t completionAnimationStartedAt = 0;
uint32_t lastCompletionAnimationFrameAt = 0;
char completionProvider = 'C';
String completionSource;
uint8_t completionCount = 1;
bool completionBaselineReady = false;
int64_t lastSeenCodexCompletionAt = 0;
int64_t lastSeenClaudeCompletionAt = 0;
int lastAnimatedIconPage = -1;
int lastAnimatedIconMode = -1;
size_t lastAnimatedIconFrame = static_cast<size_t>(-1);
int selectedResult = -1;
struct ResultBallMotion {
  float x = 225.0f;
  float y = 235.0f;
  float velocityX = 0.0f;
  float velocityY = 0.0f;
};
ResultBallMotion resultBallMotion[kMaxDashboardResults];
size_t resultBallMotionCount = 0;
bool resultBallMotionReady = false;
bool resultBallPreviousAccelReady = false;
float resultBallPreviousAccelX = 0.0f;
float resultBallPreviousAccelY = 0.0f;
float resultBallPreviousAccelZ = 0.0f;
uint32_t lastResultBallPhysicsAt = 0;
uint32_t lastResultBallFrameAt = 0;
uint32_t lastResultBallShakeAt = 0;
int64_t dashboardServerTime = 0;
uint32_t dashboardServerTimeAt = 0;
volatile int voiceLevelPercent = 0;
constexpr size_t kVoiceWaveformPoints = 72;
int16_t voiceWaveform[kVoiceWaveformPoints] = {};
portMUX_TYPE voiceVisualMux = portMUX_INITIALIZER_UNLOCKED;
constexpr uint32_t kVoiceSampleRate = 48000;
constexpr uint32_t kVoiceBlockDurationMs = 10;
constexpr size_t kVoiceBlockSamples =
    kVoiceSampleRate * kVoiceBlockDurationMs / 1000;
constexpr size_t kUsbVoicePacketSamples = 48;

#if defined(M5DASH_USB_AUDIO)
// The capture/USB split and ES8311 speech profile are selectively adapted
// from digitsisyph/codex-micro-stopwatch (MIT), commit
// e4f51036ebba21815854e7c427a3f51c2dc10fc1. Dashboard UI, CDC state bridge,
// buttons, power policy, and Codex data services remain independent.
struct VoiceAudioBlock {
  uint32_t voiceGeneration;
  uint32_t streamGeneration;
  int16_t samples[kVoiceBlockSamples];
};

constexpr UBaseType_t kVoiceQueuedBlocks = 2;
constexpr uint32_t kVoiceTaskStackBytes = 4096;
constexpr UBaseType_t kUsbAudioTaskPriority = 3;
constexpr UBaseType_t kVoiceCaptureTaskPriority = kUsbAudioTaskPriority + 1;
int16_t voiceCaptureBuffers[2][kVoiceBlockSamples] = {};
VoiceAudioBlock voiceEnqueueBlock = {};
VoiceAudioBlock voiceProducerDropBlock = {};
VoiceAudioBlock voiceUsbTransferBlock = {};
StaticQueue_t voiceAudioQueueControl = {};
uint8_t voiceAudioQueueStorage[kVoiceQueuedBlocks * sizeof(VoiceAudioBlock)] = {};
QueueHandle_t voiceAudioQueue = nullptr;
TaskHandle_t usbAudioTaskHandle = nullptr;
volatile TaskHandle_t voiceCaptureTaskHandle = nullptr;
std::atomic<bool> usbAudioStreaming{false};
std::atomic<bool> usbLinkUsable{false};
std::atomic<bool> usbStreamResetPending{false};
std::atomic<uint32_t> usbStreamGeneration{0};
std::atomic<uint32_t> voiceCaptureGeneration{0};
#else
volatile bool usbAudioStreaming = false;
#endif

enum class OverlayMode {
  none,
  brightness,
  volume,
  connection,
  wifiPicker,
  voice,
  transcript,
  orbit,
  results,
};

OverlayMode overlayMode = OverlayMode::none;
uint32_t overlayUntilAt = 0;

struct ToneStep {
  uint16_t frequency;
  uint16_t durationMs;
  uint16_t gapMs;
};

constexpr ToneStep kPrinterDoneTones[] = {{880, 80, 35}, {1175, 140, 0}};
constexpr ToneStep kPrinterErrorTones[] = {{660, 100, 45}, {520, 100, 45}, {390, 180, 0}};
constexpr ToneStep kCodexWaitingTones[] = {{1047, 120, 0}};
constexpr ToneStep kVolumePreviewTone[] = {{1047, 70, 0}};
constexpr uint16_t kSpeakerReleaseTailMs = 24;
constexpr uint32_t kAudioPowerGuardIntervalMs = 500;
constexpr uint8_t kStopWatchCodecPowerIoExpanderPin = 2;  // M5IOE1 G3.
constexpr uint8_t kStopWatchSpeakerPaIoExpanderPin = 9;  // M5IOE1 G10.
const ToneStep *activeTonePattern = nullptr;
size_t activeToneCount = 0;
size_t activeToneIndex = 0;
uint32_t nextToneAt = 0;

constexpr uint8_t kM5Pm1Address = 0x6E;
constexpr uint8_t kM5Pm1PowerConfigRegister = 0x06;
constexpr uint8_t kM5Pm1GpioDriveRegister = 0x13;
constexpr uint8_t kM5Pm1ButtonStatusRegister = 0x48;
constexpr uint8_t kM5Pm1ButtonConfig1Register = 0x49;
constexpr uint8_t kM5Pm1ButtonConfig2Register = 0x4A;
constexpr uint8_t kM5Pm1NeoConfigRegister = 0x50;
constexpr uint8_t kM5Pm1LedDefaultMask = 0x10;
constexpr uint8_t kM5Pm1LedOpenDrainMask = 0x20;
constexpr uint32_t kM5Pm1I2cFrequency = 100000;
constexpr uint32_t kPowerButtonDoubleClickMs = 500;
constexpr uint32_t kPowerButtonShortPressMaxMs = 1500;
constexpr int kDisplayChipSelectPin = 39;
constexpr uint8_t kTouchResetIoExpanderPin = 3;  // M5IOE1 gpio4.
constexpr int kSwipeThreshold = 55;
constexpr int kGestureLockThreshold = 18;
constexpr int kControlTravelPixels = 300;
constexpr int kControlStepPercent = 1;
constexpr int kMinimumBrightnessPercent = 10;
constexpr uint32_t kControlOverlayMs = 900;
constexpr uint32_t kButtonOverlayMs = 1600;
constexpr uint32_t kConnectionOverlayMs = 3000;
constexpr uint32_t kWifiPickerOverlayMs = 15000;
constexpr uint32_t kAButtonLongPressMs = 800;
constexpr uint32_t kCpuIdleDelayMs = 15000;
constexpr uint32_t kVoiceStoppedOverlayMs = 900;
constexpr uint32_t kTranscriptRefreshMs = 1000;
constexpr int kUiDesignSize = 450;
constexpr int kUiFrameSize = 466;
constexpr int kDashboardRingCenterX = 225;
constexpr int kDashboardRingCenterY = 225;
constexpr int kDashboardRingOuterRadius = 216;
constexpr int kDashboardRingInnerRadius = 201;
constexpr int kPageIndicatorY = 418;
constexpr int kPageIndicatorActiveRadius = 3;
static_assert(kPageIndicatorY + kPageIndicatorActiveRadius <
                  kDashboardRingCenterY + kDashboardRingInnerRadius,
              "page indicator must not overlap the dashboard ring");
constexpr int kCenterIconX = 177;
constexpr int kCenterIconY = 170;
constexpr int kCenterIconSize = 96;
constexpr uint32_t kIconAnimationRefreshMs = 100;
constexpr uint32_t kCodexDoneAnimationMs = kDashboardCompletionDurationMs;
constexpr uint32_t kCompletionAnimationRefreshMs = 40;
constexpr uint32_t kCompletionStateGapMs = 15000;
constexpr uint32_t kResultBallPhysicsIntervalMs = 20;
constexpr uint32_t kResultBallFrameIntervalMs = 33;
constexpr uint32_t kResultBallShakeCooldownMs = 180;
constexpr uint8_t kVoiceButtonPin = 1;  // StopWatch KEYB (blue), active low.
constexpr uint32_t kCpuHighFrequencyMhz = 240;
constexpr uint32_t kCpuLowFrequencyMhz = 80;
constexpr uint32_t kWifiRetryIntervalMs = 750;
constexpr uint32_t kWifiConnectAttemptMs = 12000;
constexpr uint32_t kAutoWifiSearchTimeoutMs = 60000;
constexpr uint32_t kUsbRequestIntervalMs = 2000;
constexpr uint32_t kUsbReplyGraceMs = 500;
constexpr uint32_t kUsbStateStaleMs = 6000;
constexpr size_t kUsbRxQueueBytes = 4096;
constexpr size_t kUsbMaxLineBytes = 32768 + 64;
constexpr char kUsbRequestPrefix[] = "M5DASH_USB_V1|GET|";
constexpr char kUsbResponsePrefix[] = "M5DASH_USB_V1|OK|";
constexpr char kUsbErrorPrefix[] = "M5DASH_USB_V1|ERR|";

void drawCurrentPage();
size_t visibleDashboardResultCount();
void drawProvisioningPage(const String &apName, bool ready);
void showConnectionStatus();
void openWifiPicker();
void openTranscript();
bool overlayVisible();
bool completionAnimationActive(uint32_t now);
bool beginVoiceCapture();
void endVoiceCapture();
#if defined(M5DASH_USB_AUDIO)
void stopVoiceCaptureHardware();
#endif

uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return canvas.color565(r, g, b);
}

bool completionAnimationActive(uint32_t now) {
  return completionAnimationRunning &&
         static_cast<uint32_t>(now - completionAnimationStartedAt) <
             kDashboardCompletionDurationMs;
}

int designFrameOffset() {
  return dashboardCenteredOffset(kUiFrameSize, kUiDesignSize);
}

int displayFrameOffsetX() {
  return dashboardCenteredOffset(M5.Display.width(), kUiFrameSize);
}

int displayFrameOffsetY() {
  return dashboardCenteredOffset(M5.Display.height(), kUiFrameSize);
}

uint16_t currentRenderedBackground() {
  uint32_t now = millis();
  if (completionAnimationActive(now)) {
    DashboardCompletionAnimationFrame frame = dashboardCompletionAnimationFrame(
        static_cast<uint32_t>(now - completionAnimationStartedAt));
    if (frame.successRadius >= kDashboardCompletionFullRadius) {
      bool claudeProvider = completionProvider == 'A';
      uint8_t backgroundR = claudeProvider ? 15 : 7;
      uint8_t backgroundG = claudeProvider ? 11 : 8;
      uint8_t backgroundB = claudeProvider ? 9 : 17;
      uint8_t accentR = claudeProvider ? 217 : 95;
      uint8_t accentG = claudeProvider ? 119 : 103;
      uint8_t accentB = claudeProvider ? 87 : 255;
      uint8_t intensity = frame.intensityPercent;
      return rgb(
          static_cast<uint8_t>(backgroundR +
                               (static_cast<int>(accentR) - backgroundR) * intensity / 100),
          static_cast<uint8_t>(backgroundG +
                               (static_cast<int>(accentG) - backgroundG) * intensity / 100),
          static_cast<uint8_t>(backgroundB +
                               (static_cast<int>(accentB) - backgroundB) * intensity / 100));
    }
  }
  if (!haveData ||
      ((overlayMode == OverlayMode::voice || overlayMode == OverlayMode::wifiPicker ||
        overlayMode == OverlayMode::transcript || overlayMode == OverlayMode::orbit ||
        overlayMode == OverlayMode::results) &&
       overlayVisible())) {
    if (overlayMode == OverlayMode::transcript || overlayMode == OverlayMode::orbit ||
        overlayMode == OverlayMode::results) {
      return rgb(8, 9, 12);
    }
    if (overlayMode == OverlayMode::voice) return rgb(9, 9, 10);
    return rgb(7, 8, 14);
  }
  if (currentPage == 0) return rgb(8, 9, 12);
  if (currentPage == 1) return rgb(5, 14, 10);
  if (currentPage == 2) return rgb(7, 8, 17);
  return rgb(15, 11, 9);
}

void composeRenderedFrame(uint16_t background) {
  if (!frameCanvasReady) return;
  frameCanvas.fillSprite(background);
  int offset = designFrameOffset();
  canvas.pushSprite(&frameCanvas, offset, offset);
}

void fillDisplayFrameMargins(uint16_t background) {
  int offsetX = displayFrameOffsetX();
  int offsetY = displayFrameOffsetY();
  int displayWidth = M5.Display.width();
  int displayHeight = M5.Display.height();
  if (offsetY > 0) {
    M5.Display.fillRect(0, 0, displayWidth, offsetY, background);
    M5.Display.fillRect(0, offsetY + kUiFrameSize, displayWidth,
                        displayHeight - offsetY - kUiFrameSize, background);
  }
  if (offsetX > 0) {
    M5.Display.fillRect(0, offsetY, offsetX, kUiFrameSize, background);
    M5.Display.fillRect(offsetX + kUiFrameSize, offsetY,
                        displayWidth - offsetX - kUiFrameSize, kUiFrameSize, background);
  }
}

void pushRenderedFrame(uint16_t background) {
  M5.Display.startWrite();
  fillDisplayFrameMargins(background);
  if (frameCanvasReady) {
    frameCanvas.pushSprite(displayFrameOffsetX(), displayFrameOffsetY());
  } else {
    canvas.pushSprite(dashboardCenteredOffset(M5.Display.width(), kUiDesignSize),
                      dashboardCenteredOffset(M5.Display.height(), kUiDesignSize));
  }
  M5.Display.endWrite();
}

bool initializeUiChineseFont() {
#if M5DASH_HAS_NOTO_UI_FONT
  static_assert(kUiFontGlyphCount >= 7000,
                "The embedded Noto font must include the full GB2312 UI set");
  if (reinterpret_cast<const volatile char *>(kUiFontIdentity)[0] != 'M') return false;
  uiChineseFontData.set(kUiFontVlw, kUiFontVlwSize);
  uiChineseFontReady = uiChineseFont.loadFont(&uiChineseFontData);
  return uiChineseFontReady;
#else
  return false;
#endif
}

void useChinese16() {
#if M5DASH_HAS_NOTO_UI_FONT
  if (uiChineseFontReady) {
    canvas.setFont(&uiChineseFont);
  } else {
    canvas.setFont(&fonts::efontCN_16);
  }
#else
  canvas.setFont(&fonts::efontCN_16);
#endif
  canvas.setTextSize(1);
}

void useChinese24() {
  canvas.setFont(&fonts::efontCN_24);
  canvas.setTextSize(1);
}

void useNumberFont() {
  canvas.setFont(&fonts::Font4);
  canvas.setTextSize(1);
}

void requireHighPerformance() {
  lastHighPerformanceAt = millis();
  if (!cpuLowPower) return;
  if (setCpuFrequencyMhz(kCpuHighFrequencyMhz)) cpuLowPower = false;
}

void enterCpuLowPower() {
  if (cpuLowPower) return;
  if (setCpuFrequencyMhz(kCpuLowFrequencyMhz)) cpuLowPower = true;
}

void updateCpuPolicy() {
  if (voiceCaptureActive || configMode) return;
  if (!cpuLowPower && millis() - lastHighPerformanceAt >= kCpuIdleDelayMs) {
    enterCpuLowPower();
  }
}

void applyDisplayBrightness() {
  M5.Display.setBrightness(static_cast<uint8_t>(brightnessPercent * 255 / 100));
}

void applySpeakerVolume() {
  int outputPercent = notificationMuted ? 0 : notificationVolumePercent;
  M5.Speaker.setVolume(static_cast<uint8_t>(outputPercent * 255 / 100));
}

bool enableSpeakerOutput() {
  if (speakerOutputEnabled) return true;
  if (!M5.Speaker.begin()) {
    // begin() enables the StopWatch codec/PA before setting up I2S. Make sure a
    // partial initialization cannot leave either rail powered.
    M5.Speaker.end();
    speakerOutputEnabled = false;
    return false;
  }
  speakerOutputEnabled = true;
  applySpeakerVolume();
  return true;
}

void forceAudioPowerRailsOff() {
  auto &ioe1 = M5.getIOExpander(0);
  // StopWatch M5IOE1 G10 enables the speaker PA; G3 powers the shared ES8311.
  // Write both explicitly in addition to Speaker.end(), because the M5Unified
  // callback does not report an I2C write failure to the application.
  ioe1.digitalWrite(kStopWatchSpeakerPaIoExpanderPin, false);
  ioe1.digitalWrite(kStopWatchCodecPowerIoExpanderPin, false);
}

void disableSpeakerOutput() {
  // stop() clears queued channels; end() is what actually disables the
  // StopWatch PA and ES8311 audio power rails.
  M5.Speaker.stop();
  M5.Speaker.end();
  speakerOutputEnabled = false;
  forceAudioPowerRailsOff();
  lastAudioPowerGuardAt = millis();
}

void updateAudioPowerGuard() {
  if (speakerOutputEnabled || voiceCaptureActive || voiceSessionActive) return;
  uint32_t now = millis();
  if (static_cast<uint32_t>(now - lastAudioPowerGuardAt) <
      kAudioPowerGuardIntervalMs) {
    return;
  }
  lastAudioPowerGuardAt = now;
  forceAudioPowerRailsOff();
}

void loadUiPreferences() {
  Preferences prefs;
  if (prefs.begin("m5dash-ui", true)) {
    brightnessPercent = prefs.getUChar("brightness", 50);
    notificationVolumePercent = prefs.getUChar("volume", 40);
    lastAudibleVolumePercent = prefs.getUChar("lastvol", 40);
    notificationMuted = prefs.getBool("muted", false);
    prefs.end();
  }
  brightnessPercent = max(kMinimumBrightnessPercent, min(100, brightnessPercent));
  notificationVolumePercent = max(0, min(100, notificationVolumePercent));
  lastAudibleVolumePercent = max(kControlStepPercent, min(100, lastAudibleVolumePercent));
  if (notificationVolumePercent > 0) lastAudibleVolumePercent = notificationVolumePercent;
  applyDisplayBrightness();
  applySpeakerVolume();
}

void saveUiPreferences() {
  Preferences prefs;
  if (!prefs.begin("m5dash-ui", false)) return;
  prefs.putUChar("brightness", brightnessPercent);
  prefs.putUChar("volume", notificationVolumePercent);
  prefs.putUChar("lastvol", lastAudibleVolumePercent);
  prefs.putBool("muted", notificationMuted);
  prefs.end();
}

void startVibration(uint8_t strength, uint16_t durationMs) {
  M5.Power.setVibration(strength);
  vibrationStopAt = millis() + durationMs;
}

void updateVibration() {
  if (vibrationStopAt != 0 && static_cast<int32_t>(millis() - vibrationStopAt) >= 0) {
    M5.Power.setVibration(0);
    vibrationStopAt = 0;
    lastVibrationPowerGuardAt = millis();
  }
  if (vibrationStopAt == 0 &&
      static_cast<uint32_t>(millis() - lastVibrationPowerGuardAt) >=
          kAudioPowerGuardIntervalMs) {
    // The StopWatch vibration PWM disable is a single unchecked I2C write.
    // Repeat it while idle so a lost write cannot leave the motor buzzing.
    M5.Power.setVibration(0);
    lastVibrationPowerGuardAt = millis();
  }
}

void stopVibration() {
  M5.Power.setVibration(0);
  vibrationStopAt = 0;
  lastVibrationPowerGuardAt = millis();
}

void startCompletionAnimation(char provider, const String &source, size_t count) {
  if (screenLocked || configMode) return;
  uint32_t now = millis();
  completionProvider = provider;
  completionSource = source;
  completionCount = static_cast<uint8_t>(max(static_cast<size_t>(1), count));
  completionAnimationStartedAt = now;
  lastCompletionAnimationFrameAt = 0;
  completionAnimationRunning = true;
  requireHighPerformance();
}

void stopTonePattern() {
  activeTonePattern = nullptr;
  activeToneCount = 0;
  activeToneIndex = 0;
  nextToneAt = 0;
  // While the microphone is running, the shared ES8311 rail belongs to the
  // capture path. Only shut it down here when this tone path enabled it.
  if (speakerOutputEnabled) disableSpeakerOutput();
}

void startTonePattern(const ToneStep *pattern, size_t count) {
  if (voiceCaptureActive || notificationMuted || notificationVolumePercent == 0 ||
      pattern == nullptr || count == 0) {
    return;
  }
  activeTonePattern = pattern;
  activeToneCount = count;
  activeToneIndex = 0;
  nextToneAt = millis();
}

void updateTonePattern() {
  if (voiceCaptureActive) return;
  if (activeTonePattern == nullptr || static_cast<int32_t>(millis() - nextToneAt) < 0) return;
  if (activeToneIndex >= activeToneCount) {
    activeTonePattern = nullptr;
    activeToneCount = 0;
    activeToneIndex = 0;
    nextToneAt = 0;
    disableSpeakerOutput();
    return;
  }
  if (!enableSpeakerOutput()) {
    activeTonePattern = nullptr;
    activeToneCount = 0;
    activeToneIndex = 0;
    nextToneAt = 0;
    return;
  }
  const ToneStep &step = activeTonePattern[activeToneIndex++];
  M5.Speaker.tone(step.frequency, step.durationMs, 0, true);
  const bool isFinalStep = activeToneIndex >= activeToneCount;
  nextToneAt = millis() + step.durationMs + step.gapMs +
               (isFinalStep ? kSpeakerReleaseTailMs : 0);
}

bool readPowerButtonPressed() {
  return (M5.In_I2C.readRegister8(kM5Pm1Address, kM5Pm1ButtonStatusRegister,
                                  kM5Pm1I2cFrequency) &
          0x01) != 0;
}

void disableBottomLed() {
  // Disable the NeoPixel engine, clear LED_EN, and make LED_EN open-drain so it
  // cannot source current while the dashboard is running or in standby.
  M5.In_I2C.writeRegister8(kM5Pm1Address, kM5Pm1NeoConfigRegister, 0x00,
                           kM5Pm1I2cFrequency);
  uint8_t powerConfig = M5.In_I2C.readRegister8(
      kM5Pm1Address, kM5Pm1PowerConfigRegister, kM5Pm1I2cFrequency);
  powerConfig &= ~kM5Pm1LedDefaultMask;
  M5.In_I2C.writeRegister8(kM5Pm1Address, kM5Pm1PowerConfigRegister, powerConfig,
                           kM5Pm1I2cFrequency);
  uint8_t gpioDrive = M5.In_I2C.readRegister8(
      kM5Pm1Address, kM5Pm1GpioDriveRegister, kM5Pm1I2cFrequency);
  gpioDrive |= kM5Pm1LedOpenDrainMask;
  M5.In_I2C.writeRegister8(kM5Pm1Address, kM5Pm1GpioDriveRegister, gpioDrive,
                           kM5Pm1I2cFrequency);
}

void configurePowerButtonPolicy() {
  uint8_t config1 = M5.In_I2C.readRegister8(
      kM5Pm1Address, kM5Pm1ButtonConfig1Register, kM5Pm1I2cFrequency);
  config1 &= ~0x80;                    // Keep the official USB download action enabled.
  config1 = (config1 & ~0x60) | 0x40;  // Use the PMIC's 500 ms double-click window.
  config1 = (config1 & ~0x18) | 0x08;  // USB + 2-second hold enters download mode.
  config1 |= 0x01;                     // Single click belongs to dashboard standby.
  M5.In_I2C.writeRegister8(kM5Pm1Address, kM5Pm1ButtonConfig1Register, config1,
                           kM5Pm1I2cFrequency);

  uint8_t config2 = M5.In_I2C.readRegister8(
      kM5Pm1Address, kM5Pm1ButtonConfig2Register, kM5Pm1I2cFrequency);
  config2 &= ~0x01;  // Restore the PMIC's official double-click shutdown.
  M5.In_I2C.writeRegister8(kM5Pm1Address, kM5Pm1ButtonConfig2Register, config2,
                           kM5Pm1I2cFrequency);
}

void setAmoledHardwareSleep(bool sleeping) {
  // StopWatch exposes the framebuffer panel to M5Unified, whose setSleep() is
  // intentionally empty. Send the CO5300 QSPI sleep command to its physical bus.
  auto *panel = M5.Display.panel();
  auto *bus = panel == nullptr ? nullptr : panel->getBus();
  if (bus == nullptr) return;
  const uint8_t command[] = {0x02, 0x00, sleeping ? uint8_t{0x10} : uint8_t{0x11}, 0x00};
  bus->beginTransaction();
  bus->wait();
  digitalWrite(kDisplayChipSelectPin, HIGH);
  digitalWrite(kDisplayChipSelectPin, LOW);
  for (uint8_t value : command) bus->writeCommand(value, 8);
  bus->wait();
  digitalWrite(kDisplayChipSelectPin, HIGH);
  bus->endTransaction();
  if (!sleeping) delay(150);
}

void stopVoiceForStandby() {
  voiceSessionActive = false;
  voiceButtonTracking = false;
  voiceButtonConsumed = false;
#if defined(M5DASH_USB_AUDIO)
  stopVoiceCaptureHardware();
#else
  voiceCaptureActive = false;
  disableSpeakerOutput();
#endif
}

void setScreenLocked(bool locked) {
  if (screenLocked == locked) return;
  screenLocked = locked;
  if (locked) {
    stopVibration();
    stopTonePattern();
    stopVoiceForStandby();
    aButtonTracking = false;
    aButtonConsumed = false;
    aButtonLongTriggered = false;
    aButtonPressedAt = 0;
    overlayMode = OverlayMode::none;
    completionAnimationRunning = false;
    completionBaselineReady = false;
    activeGesture = DashboardGesture::none;
    touchPending = false;
    if (discoveryUdpStarted) discoveryUdp.stop();
    discoveryUdpStarted = false;
    WiFi.disconnect(true, false);
    WiFi.mode(WIFI_OFF);
    wifiAttemptInProgress = false;
    wifiManualProfile = -1;
    wifiManualSwitchPending = false;
    wifiReconnectPaused = false;
    wifiPickerMessage = "";
    wifiSearchStartedAt = 0;
    connectedSsid = "";
    bridgeOnline = false;
    usbBridgeOnline = false;
    lastUsbRequestAt = 0;
    disableBottomLed();
    M5.Display.setBrightness(0);
    M5.Display.waitDisplay();
    setAmoledHardwareSleep(true);
    M5.getIOExpander(0).digitalWrite(kTouchResetIoExpanderPin, false);
    enterCpuLowPower();
    return;
  }

  requireHighPerformance();
  M5.getIOExpander(0).digitalWrite(kTouchResetIoExpanderPin, true);
  delay(12);
  setAmoledHardwareSleep(false);
  applyDisplayBrightness();
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false);
  lastFetchAt = 0;
  lastWifiAttemptAt = 0;
  wifiAttemptStartedAt = 0;
  lastUsbRequestAt = 0;
  lastUsbStateAt = 0;
  if (configMode) {
    ESP.restart();
  } else {
    drawCurrentPage();
  }
}

void updatePowerButton() {
  bool pressed = readPowerButtonPressed();
  DashboardPowerAction action = updateDashboardPowerButton(
      powerButtonState, pressed, millis(), kPowerButtonDoubleClickMs,
      kPowerButtonShortPressMaxMs);
  if (action == DashboardPowerAction::toggleStandby) {
    setScreenLocked(!screenLocked);
  } else if (action == DashboardPowerAction::powerOff) {
    if (!screenLocked) setScreenLocked(true);
    disableBottomLed();
    M5.Power.powerOff();
  }
}

void updateDevicePower(bool force = false) {
  constexpr uint32_t refreshMs = 15000;
  if (!force && lastBatteryReadAt != 0 && millis() - lastBatteryReadAt < refreshMs) return;
  lastBatteryReadAt = millis();
  int level = M5.Power.getBatteryLevel();
  deviceBatteryLevel = level >= 0 ? max(0, min(100, level)) : -1;
  deviceCharging =
      M5.Power.isCharging() == m5::Power_Class::is_charging_t::is_charging;
}

void drawBatteryStatusAt(uint16_t background, uint16_t normalColor,
                         int iconX, int iconY) {
  constexpr int iconWidth = 24;
  constexpr int iconHeight = 13;
  uint16_t color = normalColor;
  if (deviceCharging) {
    color = rgb(58, 222, 126);
  } else if (deviceBatteryLevel >= 0 && deviceBatteryLevel <= 15) {
    color = rgb(255, 91, 91);
  } else if (deviceBatteryLevel >= 0 && deviceBatteryLevel <= 30) {
    color = rgb(255, 190, 75);
  }

  canvas.drawRoundRect(iconX, iconY, iconWidth, iconHeight, 3, color);
  canvas.fillRoundRect(iconX + iconWidth, iconY + 4, 3, 6, 1, color);
  if (deviceBatteryLevel >= 0) {
    int fillWidth = (iconWidth - 4) * deviceBatteryLevel / 100;
    if (fillWidth > 0) {
      canvas.fillRoundRect(iconX + 2, iconY + 2, fillWidth, iconHeight - 4, 2, color);
    }
  }
  if (deviceCharging) {
    canvas.drawLine(iconX + 14, iconY + 2, iconX + 10, iconY + 7, background);
    canvas.drawLine(iconX + 10, iconY + 7, iconX + 15, iconY + 7, background);
    canvas.drawLine(iconX + 15, iconY + 7, iconX + 11, iconY + 12, background);
  }

  canvas.setTextDatum(middle_left);
  canvas.setTextColor(color);
  useChinese16();
  canvas.drawString(deviceBatteryLevel >= 0 ? String(deviceBatteryLevel) + "%" : "--",
                    iconX + 32, iconY + iconHeight / 2 + 1);
}

void drawBatteryStatus(uint16_t background, uint16_t normalColor) {
  // Keep the power indicator visually attached to the central app icon.
  drawBatteryStatusAt(background, normalColor, 190, 135);
}

String formatDurationCN(int minutes) {
  if (minutes < 0) return "--";
  if (minutes < 60) return String(minutes) + "分钟";
  if (minutes < 1440) {
    int hours = minutes / 60;
    int rest = minutes % 60;
    return rest > 0 ? String(hours) + "时" + String(rest) + "分" : String(hours) + "小时";
  }
  int days = minutes / 1440;
  int hours = (minutes % 1440) / 60;
  return hours > 0 ? String(days) + "天" + String(hours) + "时" : String(days) + "天";
}

String formatCount(int64_t value) {
  char buffer[24];
  if (value >= 100000000) {
    snprintf(buffer, sizeof(buffer), "%.0fM", static_cast<double>(value) / 1000000.0);
  } else if (value >= 1000000) {
    snprintf(buffer, sizeof(buffer), "%.1fM", static_cast<double>(value) / 1000000.0);
  } else if (value >= 1000) {
    snprintf(buffer, sizeof(buffer), "%.1fK", static_cast<double>(value) / 1000.0);
  } else {
    snprintf(buffer, sizeof(buffer), "%lld", static_cast<long long>(value));
  }
  return String(buffer);
}

String formatThousands(int64_t value) {
  char digits[32];
  snprintf(digits, sizeof(digits), "%lld", static_cast<long long>(value));
  int length = strlen(digits);
  int firstDigit = digits[0] == '-' ? 1 : 0;
  String formatted;
  formatted.reserve(length + length / 3);
  for (int index = 0; index < length; ++index) {
    if (index > firstDigit && (length - index) % 3 == 0) formatted += ',';
    formatted += digits[index];
  }
  return formatted;
}

String formatLifetimeUsage(int64_t value) {
  if (value >= 100000000) return String(value / 100000000) + "亿";
  return formatThousands(value);
}

String printerStatusCN() {
  if (!printer.connected) return "打印机离线";
  if (printer.state == "PRINTING" || printer.state == "RUNNING") return "正在打印";
  if (printer.state == "PREPARING" || printer.state == "PREPARE") return "正在准备";
  if (printer.state == "PAUSED" || printer.state == "PAUSE") return "打印暂停";
  if (printer.state == "ERROR" || printer.state == "FAILED") return "打印异常";
  if (printer.state == "FINISHED" || printer.state == "FINISH") return "打印完成";
  if (printer.state == "IDLE") return "当前空闲";
  return printer.state;
}

String codexStatusCN() {
  if (!codex.connected) return "Codex离线";
  if (codex.waiting > 0) return "等待确认";
  if (codex.active > 0) return "正在工作";
  if (codex.errors > 0) return "需要检查";
  return "当前空闲";
}

String claudeStatusCN() {
  if (!claude.connected) return "Claude离线";
  if (claude.waiting > 0) return "等待确认";
  if (claude.active > 0) return "正在工作";
  if (claude.errors > 0) return "需要检查";
  return "当前空闲";
}

uint16_t printerColor() {
  if (!printer.connected) return rgb(95, 103, 100);
  if (printer.state == "PRINTING" || printer.state == "RUNNING" ||
      printer.state == "PREPARING" || printer.state == "PREPARE") {
    return rgb(0, 174, 66);
  }
  if (printer.state == "PAUSED" || printer.state == "PAUSE") return rgb(255, 184, 77);
  if (printer.state == "ERROR" || printer.state == "FAILED") return rgb(255, 82, 82);
  if (printer.state == "FINISHED" || printer.state == "FINISH") return rgb(0, 174, 66);
  return rgb(142, 148, 160);
}

uint16_t codexStatusColor() {
  if (!codex.connected) return rgb(96, 99, 111);
  if (codex.errors > 0) return rgb(255, 92, 92);
  if (codex.waiting > 0) return rgb(255, 184, 77);
  return rgb(141, 145, 255);
}

uint16_t claudeStatusColor() {
  if (!claude.connected) return rgb(96, 93, 88);
  if (claude.errors > 0) return rgb(225, 87, 89);
  if (claude.waiting > 0) return rgb(237, 177, 32);
  return rgb(217, 119, 87);
}

void drawRoundScreenBase(uint16_t background, uint16_t track, int percent, uint16_t active) {
  canvas.fillScreen(background);
  canvas.fillArc(kDashboardRingCenterX, kDashboardRingCenterY,
                 kDashboardRingOuterRadius, kDashboardRingInnerRadius,
                 0, 360, track);
  int safePercent = max(0, min(100, percent));
  if (safePercent > 0) {
    int endAngle = -90 + static_cast<int>(3.6f * safePercent);
    canvas.fillArc(kDashboardRingCenterX, kDashboardRingCenterY,
                   kDashboardRingOuterRadius, kDashboardRingInnerRadius,
                   -90, endAngle, active);
  }
  canvas.fillCircle(kDashboardRingCenterX, 17, 6, rgb(235, 246, 239));
  canvas.fillCircle(kDashboardRingCenterX, 17, 3, active);
}

void maskRoundedImageCorners(int x, int y, int width, int height, int radius, uint16_t background) {
  for (int row = 0; row < radius; ++row) {
    float dy = static_cast<float>(radius - row);
    int cut = radius - static_cast<int>(sqrtf(radius * radius - dy * dy));
    if (cut <= 0) continue;
    canvas.fillRect(x, y + row, cut, 1, background);
    canvas.fillRect(x + width - cut, y + row, cut, 1, background);
    canvas.fillRect(x, y + height - 1 - row, cut, 1, background);
    canvas.fillRect(x + width - cut, y + height - 1 - row, cut, 1, background);
  }
}

void drawBambuLogo(uint16_t background) {
  canvas.drawPng(
    bambu_logo_png, bambu_logo_png_len,
    177, 170, 96, 96,
    0, 0, 1.0f, 1.0f, datum_t::top_left
  );
  maskRoundedImageCorners(177, 170, 96, 96, 22, background);
}

DashboardCodexIconMode currentCodexIconMode(uint32_t now) {
  return selectDashboardCodexIconMode(
      codex.connected, codex.active, codex.waiting, codex.errors,
      dashboardDeadlinePending(now, codexDoneAnimationUntilAt));
}

size_t codexIconFrameCount(DashboardCodexIconMode mode) {
  switch (mode) {
    case DashboardCodexIconMode::working:
      return sizeof(codex_pet_work_frames) / sizeof(codex_pet_work_frames[0]);
    case DashboardCodexIconMode::waiting:
      return sizeof(codex_pet_waiting_frames) / sizeof(codex_pet_waiting_frames[0]);
    case DashboardCodexIconMode::done:
      return sizeof(codex_pet_done_frames) / sizeof(codex_pet_done_frames[0]);
    case DashboardCodexIconMode::failed:
      return sizeof(codex_pet_failed_frames) / sizeof(codex_pet_failed_frames[0]);
    case DashboardCodexIconMode::idle:
      return 1;
  }
  return 1;
}

uint32_t codexIconFrameInterval(DashboardCodexIconMode mode) {
  switch (mode) {
    case DashboardCodexIconMode::working:
      return 120;
    case DashboardCodexIconMode::waiting:
    case DashboardCodexIconMode::done:
      return 150;
    case DashboardCodexIconMode::failed:
      return 140;
    case DashboardCodexIconMode::idle:
      return 1;
  }
  return 1;
}

const DashboardPngFrame &codexIconFrame(DashboardCodexIconMode mode, size_t index) {
  switch (mode) {
    case DashboardCodexIconMode::working:
      return codex_pet_work_frames[index];
    case DashboardCodexIconMode::waiting:
      return codex_pet_waiting_frames[index];
    case DashboardCodexIconMode::done:
      return codex_pet_done_frames[index];
    case DashboardCodexIconMode::failed:
      return codex_pet_failed_frames[index];
    case DashboardCodexIconMode::idle:
      return codex_pet_idle_frames[0];
  }
  return codex_pet_idle_frames[0];
}

size_t currentCodexIconFrame(DashboardCodexIconMode mode, uint32_t now) {
  return dashboardAnimationFrame(now, codexIconFrameInterval(mode),
                                 codexIconFrameCount(mode));
}

uint8_t currentClaudeScalePercent(uint32_t now) {
  if (!claude.connected || claude.active <= 0) return 100;
  return dashboardClaudeScalePercent(
      dashboardAnimationFrame(now, 110, 8));
}

void copyIconCanvasToPage(bool pushToDisplay) {
  iconCanvas.pushSprite(&canvas, kCenterIconX, kCenterIconY);
  if (!pushToDisplay) return;

  int designOffset = designFrameOffset();
  int frameX = kCenterIconX + designOffset;
  int frameY = kCenterIconY + designOffset;
  if (frameCanvasReady) iconCanvas.pushSprite(&frameCanvas, frameX, frameY);
  iconCanvas.pushSprite(frameX + displayFrameOffsetX(),
                        frameY + displayFrameOffsetY());
}

void composeCodexIcon(uint16_t background, uint32_t now) {
  DashboardCodexIconMode mode = currentCodexIconMode(now);
  size_t frameIndex = currentCodexIconFrame(mode, now);
  const DashboardPngFrame &frame = codexIconFrame(mode, frameIndex);
  iconCanvas.fillSprite(background);
  iconCanvas.drawPng(frame.data, frame.length, 0, 0, kCenterIconSize, kCenterIconSize,
                     0, 0, 1.0f, 1.0f, datum_t::top_left);
}

void composeClaudeIcon(uint16_t background, uint32_t now) {
  iconCanvas.fillSprite(background);
  iconCanvas.fillRoundRect(0, 0, kCenterIconSize, kCenterIconSize, 22,
                           rgb(217, 119, 87));
  float scale = static_cast<float>(currentClaudeScalePercent(now)) / 100.0f;
  iconCanvas.drawPng(claude_mark_png, claude_mark_png_len,
                     0, 0, kCenterIconSize, kCenterIconSize,
                     0, 0, scale, scale, datum_t::middle_center);
}

void drawCodexIcon(uint16_t background) {
  if (iconCanvasReady) {
    composeCodexIcon(background, millis());
    copyIconCanvasToPage(false);
    return;
  }
  canvas.drawPng(
    codex_icon_png, codex_icon_png_len,
    177, 170, 96, 96,
    0, 0, 1.0f, 1.0f, datum_t::top_left
  );
  maskRoundedImageCorners(177, 170, 96, 96, 22, background);
}

void drawClaudeIcon(uint16_t background) {
  if (iconCanvasReady) {
    composeClaudeIcon(background, millis());
    copyIconCanvasToPage(false);
    return;
  }
  canvas.drawPng(
    claude_icon_png, claude_icon_png_len,
    177, 170, 96, 96,
    0, 0, 1.0f, 1.0f, datum_t::top_left
  );
  maskRoundedImageCorners(177, 170, 96, 96, 22, background);
}

void drawMetric(const String &label, const String &value, int x, int labelY, int valueY,
                int lineLeft, int lineRight, uint16_t muted, uint16_t foreground,
                bool useChineseValue = false, uint16_t lineColor = 0) {
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(muted);
  useChinese16();
  canvas.drawString(label, x, labelY);
  canvas.setTextColor(foreground);
  if (useChineseValue) {
    useChinese24();
  } else if (value.length() > 8) {
    canvas.setFont(&fonts::Font2);
    canvas.setTextSize(1);
  } else {
    useNumberFont();
  }
  canvas.drawString(value, x, valueY);
  canvas.drawFastHLine(lineLeft, valueY + 22, lineRight - lineLeft,
                       lineColor != 0 ? lineColor : rgb(38, 55, 47));
}

void drawStatusPill(const String &text, uint16_t dotColor, uint16_t fill, uint16_t border,
                    uint16_t foreground) {
  constexpr int x = 167;
  constexpr int y = 288;
  constexpr int width = 116;
  constexpr int height = 31;
  canvas.fillRoundRect(x, y, width, height, 16, fill);
  canvas.drawRoundRect(x, y, width, height, 16, border);
  canvas.fillCircle(x + 20, y + height / 2, 5, dotColor);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(foreground);
  useChinese16();
  canvas.drawString(text, x + 72, y + height / 2 + 1);
}

void drawFooterPill(const String &label, const String &value, uint16_t fill, uint16_t border,
                    uint16_t muted, uint16_t foreground) {
  constexpr int x = 132;
  constexpr int y = 350;
  constexpr int width = 186;
  constexpr int height = 44;
  canvas.fillRoundRect(x, y, width, height, 22, fill);
  canvas.drawRoundRect(x, y, width, height, 22, border);
  canvas.drawFastVLine(216, 362, 20, rgb(55, 62, 59));
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(muted);
  useChinese16();
  canvas.drawString(label, 174, 372);
  canvas.setTextColor(foreground);
  useChinese16();
  canvas.drawString(value, 267, 372);
}

void drawPageIndicator(uint16_t active, uint16_t inactive) {
  int firstX = 225 - ((pageCount - 1) * 11) / 2;
  for (int page = 0; page < pageCount; ++page) {
    canvas.fillCircle(firstX + page * 11, kPageIndicatorY,
                      page == currentPage ? kPageIndicatorActiveRadius : 2,
                      page == currentPage ? active : inactive);
  }
}

bool overlayVisible() {
  if (overlayMode == OverlayMode::none) return false;
  if (overlayMode == OverlayMode::transcript || overlayMode == OverlayMode::orbit ||
      overlayMode == OverlayMode::results) {
    return true;
  }
  if (overlayMode == OverlayMode::voice && voiceCaptureActive) return true;
  if (activeGesture == DashboardGesture::brightness ||
      activeGesture == DashboardGesture::volume) {
    return true;
  }
  return static_cast<int32_t>(overlayUntilAt - millis()) > 0;
}

void drawSunIcon(int x, int y, uint16_t color) {
  canvas.fillCircle(x, y, 10, color);
  for (int angle = 0; angle < 360; angle += 45) {
    float radians = angle * PI / 180.0f;
    int innerX = x + static_cast<int>(cosf(radians) * 16);
    int innerY = y + static_cast<int>(sinf(radians) * 16);
    int outerX = x + static_cast<int>(cosf(radians) * 23);
    int outerY = y + static_cast<int>(sinf(radians) * 23);
    canvas.drawLine(innerX, innerY, outerX, outerY, color);
  }
}

void drawSpeakerIcon(int x, int y, uint16_t color) {
  canvas.fillRect(x - 22, y - 8, 10, 16, color);
  canvas.fillTriangle(x - 12, y - 8, x + 2, y - 20, x + 2, y + 20, color);
  if (notificationMuted || notificationVolumePercent == 0) {
    canvas.drawLine(x + 10, y - 11, x + 28, y + 11, color);
    canvas.drawLine(x + 28, y - 11, x + 10, y + 11, color);
  } else {
    canvas.drawLine(x + 10, y - 12, x + 18, y - 5, color);
    canvas.drawLine(x + 18, y - 5, x + 18, y + 5, color);
    canvas.drawLine(x + 18, y + 5, x + 10, y + 12, color);
    canvas.drawLine(x + 21, y - 18, x + 29, y - 10, color);
    canvas.drawLine(x + 29, y - 10, x + 29, y + 10, color);
    canvas.drawLine(x + 29, y + 10, x + 21, y + 18, color);
  }
}

void drawMicrophoneIcon(int x, int y, uint16_t color) {
  const uint16_t foreground = rgb(247, 243, 241);
  canvas.drawRoundRect(x - 17, y - 32, 34, 58, 17, foreground);
  canvas.drawRoundRect(x - 16, y - 31, 32, 56, 16, foreground);

  int previousX = x - 32;
  int previousY = y - 2;
  for (int step = 1; step <= 18; ++step) {
    float radians = step * PI / 18.0f;
    int currentX = x - 32 + static_cast<int>(64.0f * step / 18.0f);
    int currentY = y - 2 + static_cast<int>(32.0f * sinf(radians));
    canvas.drawLine(previousX, previousY, currentX, currentY, color);
    canvas.drawLine(previousX, previousY + 1, currentX, currentY + 1, color);
    previousX = currentX;
    previousY = currentY;
  }
  canvas.drawFastVLine(x - 32, y - 8, 7, color);
  canvas.drawFastVLine(x - 31, y - 8, 7, color);
  canvas.drawFastVLine(x + 31, y - 8, 7, color);
  canvas.drawFastVLine(x + 32, y - 8, 7, color);
  canvas.fillRoundRect(x - 2, y + 29, 4, 17, 2, foreground);
  canvas.fillRoundRect(x - 16, y + 44, 32, 4, 2, foreground);
}

void drawControlOverlay() {
  constexpr int x = 95;
  constexpr int y = 137;
  constexpr int width = 260;
  constexpr int height = 176;
  const bool isBrightness = overlayMode == OverlayMode::brightness;
  const bool muted = !isBrightness && (notificationMuted || notificationVolumePercent == 0);
  const int percent = isBrightness ? brightnessPercent : notificationVolumePercent;
  const uint16_t accent = isBrightness ? rgb(242, 142, 43)
                                       : muted ? rgb(186, 176, 172) : rgb(78, 121, 167);

  canvas.fillRoundRect(x, y, width, height, 28, rgb(17, 19, 28));
  canvas.drawRoundRect(x, y, width, height, 28, rgb(67, 70, 82));
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(218, 220, 229));
  useChinese16();
  canvas.drawString(isBrightness ? "亮度" : "通知音量", 225, 166);

  if (isBrightness) {
    drawSunIcon(157, 218, accent);
  } else {
    drawSpeakerIcon(159, 218, accent);
  }
  canvas.setTextColor(accent);
  if (muted) {
    useChinese24();
    canvas.drawString("已静音", 258, 219);
  } else {
    useNumberFont();
    canvas.drawString(String(percent) + "%", 258, 219);
  }

  constexpr int trackX = 130;
  constexpr int trackY = 268;
  constexpr int trackWidth = 190;
  canvas.fillRoundRect(trackX, trackY, trackWidth, 10, 5, rgb(53, 56, 68));
  int fillWidth = percent * trackWidth / 100;
  if (fillWidth > 0) canvas.fillRoundRect(trackX, trackY, fillWidth, 10, 5, accent);
  int thumbX = trackX + fillWidth;
  thumbX = max(trackX + 5, min(trackX + trackWidth - 5, thumbX));
  canvas.fillCircle(thumbX, trackY + 5, 8, accent);
  canvas.drawCircle(thumbX, trackY + 5, 9, rgb(225, 226, 233));
  canvas.setTextColor(rgb(132, 136, 150));
  useChinese16();
  canvas.drawString("上滑增加 · 下滑减少", 225, 294);
}

String lastUpdateText() {
  if (lastStateAppliedAt == 0) return "尚未收到";
  uint32_t seconds = (millis() - lastStateAppliedAt) / 1000;
  if (seconds < 2) return "刚刚";
  if (seconds < 60) return String(seconds) + "秒前";
  return String(seconds / 60) + "分钟前";
}

void drawConnectionOverlay() {
  constexpr int x = 70;
  constexpr int y = 118;
  constexpr int width = 310;
  constexpr int height = 214;
  bool online = usbBridgeOnline || bridgeOnline;
  uint16_t accent = online ? rgb(89, 161, 79) : rgb(225, 87, 89);
  String channel = usbBridgeOnline ? "USB直连"
                                   : WiFi.status() == WL_CONNECTED ? "无线网络" : "未连接";

  canvas.fillRoundRect(x, y, width, height, 30, rgb(17, 19, 28));
  canvas.drawRoundRect(x, y, width, height, 30, rgb(67, 70, 82));
  canvas.fillCircle(116, 153, 7, accent);
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(rgb(238, 239, 244));
  useChinese24();
  canvas.drawString("连接状态", 137, 153);

  canvas.setTextColor(rgb(139, 143, 157));
  useChinese16();
  canvas.drawString("数据通道", 105, 202);
  canvas.drawString("桥接服务", 105, 242);
  canvas.drawString("最近更新", 105, 282);
  canvas.setTextDatum(middle_right);
  canvas.setTextColor(rgb(232, 233, 240));
  canvas.drawString(channel, 345, 202);
  canvas.setTextColor(accent);
  canvas.drawString(online ? "在线" : "离线", 345, 242);
  canvas.setTextColor(rgb(232, 233, 240));
  canvas.drawString(lastUpdateText(), 345, 282);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(112, 117, 132));
  canvas.drawString("A键短按刷新", 225, 312);
}

String fitTextToWidth(const String &text, int maxWidth) {
  if (canvas.textWidth(text) <= maxWidth) return text;
  String fitted = text;
  constexpr char suffix[] = "...";
  while (fitted.length() > 0 && canvas.textWidth(fitted + suffix) > maxWidth) {
    int characterStart = static_cast<int>(fitted.length()) - 1;
    while (characterStart > 0 &&
           (static_cast<uint8_t>(fitted[characterStart]) & 0xC0) == 0x80) {
      --characterStart;
    }
    fitted.remove(characterStart);
  }
  return fitted + suffix;
}

void drawWifiPickerRow(int y, const String &title, const String &detail, bool configured,
                       bool current, bool automatic) {
  constexpr int x = 55;
  constexpr int width = 340;
  constexpr int height = 52;
  const uint16_t active = current ? rgb(89, 161, 79) : rgb(111, 117, 255);
  const uint16_t border = current ? rgb(69, 130, 67)
                                  : automatic ? rgb(73, 77, 133) : rgb(55, 58, 72);
  const uint16_t fill = current ? rgb(20, 40, 31)
                                : automatic ? rgb(24, 25, 48) : rgb(17, 19, 28);

  canvas.fillRoundRect(x, y, width, height, 16, fill);
  canvas.drawRoundRect(x, y, width, height, 16, border);
  canvas.fillCircle(79, y + height / 2, 5,
                    configured || automatic ? active : rgb(72, 75, 87));
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(configured || automatic ? rgb(238, 239, 244)
                                               : rgb(112, 116, 129));
  useChinese16();
  canvas.drawString(title, 97, y + 17);

  canvas.setTextColor(current ? rgb(124, 205, 119) : rgb(132, 136, 151));
  String fittedDetail = fitTextToWidth(detail, 215);
  canvas.drawString(fittedDetail, 97, y + 36);

  if (current) {
    canvas.setTextDatum(middle_center);
    canvas.setTextColor(rgb(124, 205, 119));
    canvas.drawString("当前", 355, y + height / 2);
  }
}

void drawWifiPickerOverlay() {
  const uint16_t background = rgb(7, 8, 14);
  const uint16_t track = rgb(25, 27, 42);
  canvas.fillScreen(background);
  canvas.fillArc(kDashboardRingCenterX, kDashboardRingCenterY,
                 kDashboardRingOuterRadius, kDashboardRingInnerRadius,
                 0, 360, track);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(238, 239, 244));
  useChinese24();
  canvas.drawString("连接中心", 225, 43);
  canvas.setTextColor(wifiPickerMessage.length() > 0 ? rgb(225, 87, 89)
                                                     : rgb(132, 136, 151));
  useChinese16();
  String currentNetwork = WiFi.status() == WL_CONNECTED
                              ? "当前网络  " + WiFi.SSID()
                              : "无线网络未连接";
  String statusText = wifiPickerMessage.length() > 0 ? wifiPickerMessage : currentNetwork;
  canvas.drawString(fitTextToWidth(statusText, 330), 225, 73);

  const bool homeConfigured = settings.ssid.length() > 0;
  const bool workConfigured = settings.ssid2.length() > 0;
  const String currentSsid = WiFi.status() == WL_CONNECTED ? WiFi.SSID() : "";
  drawWifiPickerRow(96, "自动选择", "家庭和公司网络自动切换", true,
                    false, true);
  drawWifiPickerRow(154, "家庭网络", homeConfigured ? settings.ssid : "未配置",
                    homeConfigured, homeConfigured && currentSsid == settings.ssid, false);
  drawWifiPickerRow(212, "公司网络", workConfigured ? settings.ssid2 : "未配置",
                    workConfigured, workConfigured && currentSsid == settings.ssid2, false);
  drawWifiPickerRow(270, "添加或修改网络", "扫描附近 Wi-Fi 并更新密码", true,
                    false, true);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(163, 166, 179));
  canvas.drawString("点击选择 · 连接失败会留在此页", 225, 349);
  canvas.setTextColor(rgb(104, 109, 124));
  canvas.drawString("长按 A+B 仍可直接进入配网", 225, 378);
}

void drawVoiceOverlay() {
  const uint16_t background = rgb(9, 9, 10);
  const uint16_t coral = rgb(255, 117, 106);
  const uint16_t coralSoft = rgb(255, 151, 141);
  const uint16_t coralDim = rgb(116, 58, 61);
  const uint16_t amber = rgb(255, 180, 91);
  const uint16_t red = rgb(255, 76, 99);
  const uint16_t inactive = rgb(139, 130, 134);
  const uint16_t foreground = rgb(247, 243, 241);
  const uint16_t muted = rgb(141, 135, 138);
  bool voiceButtonArmed = voiceButtonTracking && !voiceSessionActive;
  uint16_t accent = voiceCaptureFailed ? red
                                       : voiceCaptureActive ? coral
                                                            : voiceButtonArmed ? amber : inactive;

  int16_t waveform[kVoiceWaveformPoints];
  int levelPercent = 0;
  portENTER_CRITICAL(&voiceVisualMux);
  memcpy(waveform, voiceWaveform, sizeof(waveform));
  levelPercent = voiceLevelPercent;
  portEXIT_CRITICAL(&voiceVisualMux);

  int peakMagnitude = 0;
  for (size_t index = 0; index < kVoiceWaveformPoints; ++index) {
    peakMagnitude = max(peakMagnitude, abs(static_cast<int>(waveform[index])));
  }
  int peakDb = peakMagnitude > 0
                   ? constrain(static_cast<int>(lroundf(
                                   20.0f * log10f(peakMagnitude / 32767.0f))),
                               -60, 0)
                   : -60;
  int meterPercent = constrain((peakDb + 60) * 100 / 60, 0, 100);

  canvas.fillScreen(background);

  String title = voiceCaptureFailed ? "麦克风启动失败"
                                    : voiceCaptureActive ? "正在收音"
                                                         : voiceButtonArmed ? "松开开启麦克风"
                                                                              : "麦克风已关闭";
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(voiceCaptureFailed ? red : foreground);
  useChinese16();
  canvas.setTextSize(1.15f);
  int titleWidth = canvas.textWidth(title);
  canvas.fillCircle(225 - titleWidth / 2 - 14, 50, voiceCaptureActive ? 5 : 4, accent);
  canvas.drawString(title, 225, 50);
#if !defined(M5DASH_USB_AUDIO)
  canvas.setTextColor(red);
  useChinese16();
  canvas.drawString("USB 麦克风未启用", 225, 50);
#endif

  canvas.setTextColor(rgb(119, 113, 116));
  useChinese16();
  canvas.setTextSize(0.75f);
  canvas.drawString("48 KHZ · USB", 225, 74);

  drawMicrophoneIcon(225, 132, accent);

  constexpr int waveLeft = 62;
  constexpr int waveRight = 388;
  constexpr int waveCenterY = 234;
  constexpr int waveHalfHeight = 37;
  canvas.drawFastHLine(waveLeft, waveCenterY, waveRight - waveLeft,
                       rgb(56, 41, 43));

  int previousX = waveLeft;
  int previousY = waveCenterY;
  for (size_t index = 0; index < kVoiceWaveformPoints; ++index) {
    int currentX = waveLeft + static_cast<int>(index) * (waveRight - waveLeft) /
                                  static_cast<int>(kVoiceWaveformPoints - 1);
    int scaled = constrain(static_cast<int>(waveform[index]) * waveHalfHeight / 10000,
                           -waveHalfHeight, waveHalfHeight);
    int currentY = waveCenterY - scaled;
    if (index > 0) {
      canvas.drawLine(previousX, previousY, currentX, currentY,
                      voiceCaptureActive ? coralSoft : coralDim);
      if (voiceCaptureActive) {
        canvas.drawLine(previousX, previousY + 1, currentX, currentY + 1, coralDim);
      }
    }
    previousX = currentX;
    previousY = currentY;
  }

  canvas.setTextDatum(middle_left);
  canvas.setTextColor(muted);
  useChinese16();
  canvas.setTextSize(0.9f);
  canvas.drawString("实时峰值", 74, 294);
  canvas.setTextDatum(middle_right);
  canvas.setTextColor(foreground);
  canvas.setFont(&fonts::Font2);
  canvas.setTextSize(1);
  canvas.drawString(String(peakDb) + " dBFS", 376, 294);

  constexpr int meterX = 74;
  constexpr int meterY = 314;
  constexpr int meterWidth = 302;
  canvas.fillRoundRect(meterX, meterY, meterWidth, 4, 2, rgb(44, 36, 38));
  int meterFill = meterWidth * meterPercent / 100;
  if (voiceCaptureActive && meterFill > 0) {
    canvas.fillRoundRect(meterX, meterY, meterFill, 4, 2, coral);
  }
  int levelX = meterX + meterWidth * constrain(levelPercent, 0, 100) / 100;
  canvas.fillRect(constrain(levelX, meterX, meterX + meterWidth - 2), meterY - 5, 2, 14,
                  voiceCaptureActive ? foreground : coralDim);

  canvas.drawFastHLine(166, 366, 118, rgb(38, 33, 36));
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(muted);
  useChinese16();
  canvas.setTextSize(0.86f);
  String hint = voiceCaptureFailed ? "再按一次重试"
                                   : voiceCaptureActive ? "再按一次关闭麦克风"
                                                        : voiceButtonArmed ? "松开即可开启麦克风"
                                                                             : "麦克风已经关闭";
  canvas.drawString(hint, 225, 393);
}

TranscriptCollection &activeTranscriptCollection() {
  return transcriptClaude ? claudeTranscripts : codexTranscripts;
}

void drawTranscriptCollapse(uint16_t color) {
  canvas.fillCircle(225, 30, 16, rgb(28, 29, 34));
  canvas.drawCircle(225, 30, 16, rgb(42, 43, 49));
  canvas.drawLine(217, 27, 225, 35, color);
  canvas.drawLine(225, 35, 233, 27, color);
  canvas.drawLine(217, 28, 225, 36, color);
  canvas.drawLine(225, 36, 233, 28, color);
}

void drawTranscriptHeader(uint16_t accent, const String &subtitle) {
  drawTranscriptCollapse(rgb(211, 209, 216));
  canvas.fillCircle(190, 72, 15, accent);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(255, 255, 255));
  useChinese16();
  canvas.setTextSize(0.92f);
  canvas.drawString(transcriptClaude ? "A" : "C", 190, 72);
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(rgb(246, 245, 248));
  useChinese16();
  canvas.setTextSize(1.2f);
  canvas.drawString(transcriptClaude ? "Claude" : "Codex", 214, 72);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(138, 137, 146));
  useChinese16();
  canvas.setTextSize(0.84f);
  canvas.drawString(fitTextToWidth(subtitle, 300), 225, 104);
  canvas.drawFastHLine(82, 119, 286, rgb(29, 31, 37));
}

void transcriptTextLines(const String &source, int maxWidth, String (&lines)[2]) {
  lines[0] = "";
  lines[1] = "";
  String text = source;
  text.replace("\n", " ");
  size_t offset = 0;
  for (int lineIndex = 0; lineIndex < 2 && offset < text.length(); ++lineIndex) {
    while (offset < text.length()) {
      size_t next = offset + 1;
      while (next < text.length() &&
             (static_cast<uint8_t>(text[next]) & 0xC0) == 0x80) {
        ++next;
      }
      String candidate = lines[lineIndex] + text.substring(offset, next);
      if (lines[lineIndex].length() > 0 && canvas.textWidth(candidate) > maxWidth) break;
      lines[lineIndex] = candidate;
      offset = next;
    }
  }
  if (offset < text.length()) lines[1] = fitTextToWidth(lines[1] + "…", maxWidth);
}

void drawTranscriptTaskRow(const TranscriptTask &task, int y, uint16_t accent,
                           uint16_t fill, uint16_t border) {
  canvas.fillRoundRect(55, y, 340, 64, 20, fill);
  canvas.drawRoundRect(55, y, 340, 64, 20, border);
  canvas.fillCircle(82, y + 32, 16, accent);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(255, 255, 255));
  useChinese16();
  canvas.setTextSize(0.82f);
  canvas.drawString(transcriptClaude ? "A" : "C", 82, y + 32);
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(rgb(246, 243, 243));
  useChinese16();
  canvas.drawString(fitTextToWidth(task.title, 235), 108, y + 23);
  canvas.setTextColor(rgb(151, 147, 156));
  canvas.setTextSize(0.76f);
  canvas.drawString(String(task.messageCount) + " 条可见消息", 108, y + 45);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(128, 127, 136));
  canvas.setTextSize(1);
  canvas.drawString("›", 368, y + 32);
}

int drawTranscriptMessage(const TranscriptMessage &message, int y,
                          uint16_t assistantFill, uint16_t userFill) {
  constexpr int maximumTextWidth = 266;
  String lines[2];
  useChinese16();
  transcriptTextLines(message.text, maximumTextWidth, lines);
  int textWidth = max(canvas.textWidth(lines[0]), canvas.textWidth(lines[1]));
  int width = constrain(textWidth + 30, 74, 296);
  int height = lines[1].length() > 0 ? 58 : 42;
  int x = message.user ? 388 - width : 62;
  uint16_t fill = message.user ? userFill : assistantFill;
  canvas.fillRoundRect(x, y, width, height, 20, fill);
  if (message.user) {
    canvas.fillTriangle(x + width - 18, y + height - 13,
                        x + width + 7, y + height - 4,
                        x + width - 5, y + height - 23, fill);
  } else {
    canvas.fillTriangle(x + 18, y + height - 13,
                        x - 7, y + height - 4,
                        x + 5, y + height - 23, fill);
  }
  canvas.setTextDatum(top_left);
  canvas.setTextColor(message.user ? rgb(255, 255, 255) : rgb(240, 239, 243));
  useChinese16();
  canvas.drawString(lines[0], x + 15, y + 8);
  if (lines[1].length() > 0) canvas.drawString(lines[1], x + 15, y + 31);
  return height;
}

void drawTranscriptTyping(uint16_t accent, int centerY) {
  canvas.fillCircle(95, centerY, 14, accent);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(255, 255, 255));
  useChinese16();
  canvas.setTextSize(0.75f);
  canvas.drawString(transcriptClaude ? "A" : "C", 95, centerY);
  canvas.fillRoundRect(117, centerY - 20, 76, 40, 20, rgb(36, 37, 42));
  int phase = (millis() / 150) % 8;
  for (int index = 0; index < 3; ++index) {
    int distance = abs(phase - (index * 2 + 1));
    int lift = distance == 0 ? 3 : distance == 1 ? 1 : 0;
    uint16_t dot = distance <= 1 ? rgb(210, 210, 217) : rgb(126, 126, 136);
    canvas.fillCircle(138 + index * 17, centerY - lift, 4, dot);
  }
}

void drawTranscriptOverlay() {
  const uint16_t background = rgb(8, 9, 12);
  const uint16_t accent = transcriptClaude ? rgb(217, 119, 87) : rgb(111, 117, 255);
  const uint16_t assistantFill = transcriptClaude ? rgb(42, 34, 31) : rgb(36, 37, 42);
  const uint16_t userFill = rgb(10, 126, 245);
  const uint16_t border = transcriptClaude ? rgb(73, 55, 48) : rgb(56, 57, 65);
  TranscriptCollection &collection = activeTranscriptCollection();

  canvas.fillScreen(background);

  if (collection.taskCount == 0) {
    drawTranscriptHeader(accent, "正在同步对话");
    canvas.setTextDatum(middle_center);
    canvas.setTextColor(rgb(166, 163, 174));
    useChinese16();
    canvas.drawString("仅显示当前电脑上的运行任务", 225, 224);
    return;
  }

  if (transcriptTaskIndex < 0 && collection.taskCount > 1) {
    drawTranscriptHeader(accent, "选择运行中的任务");
    for (size_t index = 0; index < collection.taskCount; ++index) {
      drawTranscriptTaskRow(collection.tasks[index], 142 + static_cast<int>(index) * 76,
                            accent, assistantFill, border);
    }
    return;
  }

  int selected = transcriptTaskIndex < 0 ? 0 : transcriptTaskIndex;
  if (selected >= static_cast<int>(collection.taskCount)) selected = 0;
  TranscriptTask &task = collection.tasks[selected];
  drawTranscriptHeader(accent, task.title);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(151, 147, 156));
  useChinese16();
  canvas.setTextSize(0.72f);
  canvas.drawString("刚刚", 225, 135);

  int maximumOffset = task.messageCount > kVisibleTranscriptMessages
                          ? static_cast<int>(task.messageCount - kVisibleTranscriptMessages)
                          : 0;
  transcriptOffsetFromNewest = constrain(transcriptOffsetFromNewest, 0, maximumOffset);
  int visible = min(static_cast<int>(kVisibleTranscriptMessages),
                    static_cast<int>(task.messageCount));
  int start = static_cast<int>(task.messageCount) - visible - transcriptOffsetFromNewest;
  start = max(0, start);
  int messageY = 151;
  for (int row = 0; row < visible; ++row) {
    int height = drawTranscriptMessage(task.messages[start + row], messageY,
                                       assistantFill, userFill);
    messageY += height + 10;
  }
  if (visible == 0) {
    canvas.setTextDatum(middle_center);
    canvas.setTextColor(rgb(151, 147, 156));
    canvas.drawString("正在等待第一条可见消息", 225, 220);
  }
  bool latestMessages = transcriptOffsetFromNewest == 0;
  bool taskWorking = task.status.length() == 0 || task.status == "working" ||
                     task.status == "active" || task.status == "running";
  if (latestMessages && taskWorking) {
    drawTranscriptTyping(accent, min(374, max(350, messageY + 14)));
  }
}

struct OrbitTaskItem {
  char provider = 'C';
  int transcriptIndex = -1;
  String title;
};

bool printerTaskActive() {
  return printer.connected &&
         (printer.state == "PRINTING" || printer.state == "RUNNING" ||
          printer.state == "PREPARING" || printer.state == "PREPARE" ||
          printer.state == "PAUSED" || printer.state == "PAUSE");
}

size_t buildOrbitTasks(OrbitTaskItem (&items)[5]) {
  size_t count = 0;
  if (printerTaskActive() && count < 5) {
    items[count++] = {'P', -1, printer.file.length() > 0 ? printer.file : "当前打印任务"};
  }
  for (size_t index = 0; index < codexTranscripts.taskCount && count < 5; ++index) {
    items[count++] = {'C', static_cast<int>(index), codexTranscripts.tasks[index].title};
  }
  for (size_t index = 0; index < claudeTranscripts.taskCount && count < 5; ++index) {
    items[count++] = {'A', static_cast<int>(index), claudeTranscripts.tasks[index].title};
  }
  return count;
}

void orbitTaskPosition(size_t index, size_t count, int &x, int &y) {
  static const int positions[5][5][2] = {
      {{225, 240}},
      {{145, 245}, {305, 245}},
      {{225, 120}, {315, 285}, {135, 285}},
      {{150, 160}, {300, 160}, {150, 325}, {300, 325}},
      {{225, 105}, {368, 209}, {313, 377}, {137, 377}, {82, 209}},
  };
  size_t safeCount = count < 1 ? 1 : count > 5 ? 5 : count;
  size_t safeIndex = index < safeCount ? index : safeCount - 1;
  x = positions[safeCount - 1][safeIndex][0];
  y = positions[safeCount - 1][safeIndex][1];
}

uint16_t providerAccent(char provider) {
  if (provider == 'P') return rgb(66, 207, 145);
  if (provider == 'A') return rgb(240, 162, 125);
  return rgb(155, 158, 255);
}

void drawDetailReturnHandle() {
  canvas.fillRoundRect(191, 7, 68, 27, 14, rgb(34, 35, 42));
  canvas.drawLine(219, 17, 225, 23, rgb(216, 216, 221));
  canvas.drawLine(225, 23, 231, 17, rgb(216, 216, 221));
}

void drawTaskOrbitOverlay() {
  const uint16_t background = rgb(8, 9, 12);
  canvas.fillScreen(background);
  drawDetailReturnHandle();
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(245, 245, 247));
  useChinese16();
  canvas.drawString("任务星盘", 225, 57);

  OrbitTaskItem items[5];
  size_t count = buildOrbitTasks(items);
  if (count == 0) {
    canvas.setTextColor(rgb(142, 143, 154));
    canvas.drawString("暂无运行任务", 225, 230);
    canvas.drawString("任务开始后会自动出现在这里", 225, 262);
    return;
  }

  for (size_t index = 0; index < count; ++index) {
    int x = 0;
    int y = 0;
    orbitTaskPosition(index, count, x, y);
    canvas.drawLine(225, 244, x, y, rgb(48, 49, 58));
  }
  for (size_t index = 0; index < count; ++index) {
    int x = 0;
    int y = 0;
    orbitTaskPosition(index, count, x, y);
    uint16_t accent = providerAccent(items[index].provider);
    canvas.fillCircle(x, y, 38, rgb(25, 26, 32));
    canvas.drawCircle(x, y, 38, rgb(66, 67, 76));
    canvas.drawCircle(x, y, 34, accent);
    canvas.fillCircle(x, y, 25, rgb(15, 16, 21));
    canvas.setTextColor(accent);
    useNumberFont();
    String shortLabel = String(items[index].provider);
    if (items[index].provider != 'P') shortLabel += String(items[index].transcriptIndex + 1);
    canvas.drawString(shortLabel, x, y + 1);
  }
  canvas.setTextColor(rgb(112, 113, 124));
  useChinese16();
  canvas.drawString("轻点任务查看详情", 225, 416);
}

void resultBallPosition(size_t index, size_t count, int &x, int &y) {
  static const int positions[6][6][2] = {
      {{225, 235}},
      {{160, 235}, {290, 235}},
      {{225, 150}, {310, 285}, {140, 285}},
      {{150, 175}, {300, 175}, {150, 320}, {300, 320}},
      {{225, 128}, {334, 207}, {292, 338}, {158, 338}, {116, 207}},
      {{160, 145}, {290, 145}, {350, 255}, {290, 355}, {160, 355}, {100, 255}},
  };
  size_t safeCount = count < 1 ? 1 : count > 6 ? 6 : count;
  size_t safeIndex = index < safeCount ? index : safeCount - 1;
  x = positions[safeCount - 1][safeIndex][0];
  y = positions[safeCount - 1][safeIndex][1];
}

int resultBallRadius(size_t index) {
  return 27 + static_cast<int>((index * 5) % 9);
}

void resetResultBallMotion(size_t count) {
  resultBallMotionCount = min(count, kMaxDashboardResults);
  for (size_t index = 0; index < resultBallMotionCount; ++index) {
    int x = 0;
    int y = 0;
    resultBallPosition(index, resultBallMotionCount, x, y);
    resultBallMotion[index].x = static_cast<float>(x);
    resultBallMotion[index].y = static_cast<float>(y);
    resultBallMotion[index].velocityX = 0.0f;
    resultBallMotion[index].velocityY = 0.0f;
  }
  resultBallMotionReady = resultBallMotionCount > 0;
  resultBallPreviousAccelReady = false;
  lastResultBallPhysicsAt = 0;
  lastResultBallFrameAt = 0;
  lastResultBallShakeAt = 0;
}

void currentResultBallPosition(size_t index, size_t count, int &x, int &y) {
  if (resultBallMotionReady && resultBallMotionCount == count && index < count) {
    x = static_cast<int>(resultBallMotion[index].x + 0.5f);
    y = static_cast<int>(resultBallMotion[index].y + 0.5f);
    return;
  }
  resultBallPosition(index, count, x, y);
}

void constrainResultBall(size_t index) {
  constexpr float centerX = 225.0f;
  constexpr float centerY = 245.0f;
  constexpr float physicsRadius = 170.0f;
  ResultBallMotion &ball = resultBallMotion[index];
  float limit = physicsRadius - static_cast<float>(resultBallRadius(index) + 7);
  float dx = ball.x - centerX;
  float dy = ball.y - centerY;
  float distanceSquared = dx * dx + dy * dy;
  if (distanceSquared <= limit * limit || distanceSquared < 0.0001f) return;
  float distance = sqrtf(distanceSquared);
  float normalX = dx / distance;
  float normalY = dy / distance;
  ball.x = centerX + normalX * limit;
  ball.y = centerY + normalY * limit;
  float outwardSpeed = ball.velocityX * normalX + ball.velocityY * normalY;
  if (outwardSpeed > 0.0f) {
    constexpr float bounce = 0.42f;
    ball.velocityX -= (1.0f + bounce) * outwardSpeed * normalX;
    ball.velocityY -= (1.0f + bounce) * outwardSpeed * normalY;
  }
}

void resolveResultBallCollisions() {
  for (size_t left = 0; left < resultBallMotionCount; ++left) {
    for (size_t right = left + 1; right < resultBallMotionCount; ++right) {
      ResultBallMotion &first = resultBallMotion[left];
      ResultBallMotion &second = resultBallMotion[right];
      float dx = second.x - first.x;
      float dy = second.y - first.y;
      float minimumDistance = static_cast<float>(resultBallRadius(left) +
                                                  resultBallRadius(right) + 8);
      float distanceSquared = dx * dx + dy * dy;
      if (distanceSquared >= minimumDistance * minimumDistance) continue;

      float distance = distanceSquared > 0.0001f ? sqrtf(distanceSquared) : 0.0f;
      float normalX = distance > 0.0f ? dx / distance : 1.0f;
      float normalY = distance > 0.0f ? dy / distance : 0.0f;
      float overlap = minimumDistance - distance;
      first.x -= normalX * overlap * 0.5f;
      first.y -= normalY * overlap * 0.5f;
      second.x += normalX * overlap * 0.5f;
      second.y += normalY * overlap * 0.5f;

      float relativeSpeed = (second.velocityX - first.velocityX) * normalX +
                            (second.velocityY - first.velocityY) * normalY;
      if (relativeSpeed < 0.0f) {
        constexpr float restitution = 0.55f;
        float impulse = -(1.0f + restitution) * relativeSpeed * 0.5f;
        first.velocityX -= impulse * normalX;
        first.velocityY -= impulse * normalY;
        second.velocityX += impulse * normalX;
        second.velocityY += impulse * normalY;
      }
      constrainResultBall(left);
      constrainResultBall(right);
    }
  }
}

void stepResultBallPhysics(float accelX, float accelY, float accelZ,
                           float elapsedSeconds, uint32_t now) {
  constexpr float tiltAcceleration = 820.0f;
  constexpr float dampingPerStep = 0.982f;
  constexpr float maximumSpeed = 520.0f;
  float screenAccelerationX = -accelX * tiltAcceleration;
  float screenAccelerationY = accelY * tiltAcceleration;

  if (resultBallPreviousAccelReady) {
    float deltaX = accelX - resultBallPreviousAccelX;
    float deltaY = accelY - resultBallPreviousAccelY;
    float deltaZ = accelZ - resultBallPreviousAccelZ;
    float jerk = sqrtf(deltaX * deltaX + deltaY * deltaY + deltaZ * deltaZ);
    if (jerk >= 0.72f && now - lastResultBallShakeAt >= kResultBallShakeCooldownMs) {
      lastResultBallShakeAt = now;
      float planarLength = sqrtf(deltaX * deltaX + deltaY * deltaY);
      float baseImpulse = min(280.0f, 95.0f + jerk * 105.0f);
      for (size_t index = 0; index < resultBallMotionCount; ++index) {
        float directionX = 0.0f;
        float directionY = 0.0f;
        if (planarLength >= 0.12f) {
          directionX = -deltaX / planarLength;
          directionY = deltaY / planarLength;
        } else {
          float angle = (static_cast<float>((now / 7 + index * 137) % 360)) * PI / 180.0f;
          directionX = cosf(angle);
          directionY = sinf(angle);
        }
        resultBallMotion[index].velocityX += directionX * baseImpulse;
        resultBallMotion[index].velocityY += directionY * baseImpulse;
      }
    }
  }
  resultBallPreviousAccelX = accelX;
  resultBallPreviousAccelY = accelY;
  resultBallPreviousAccelZ = accelZ;
  resultBallPreviousAccelReady = true;

  for (size_t index = 0; index < resultBallMotionCount; ++index) {
    ResultBallMotion &ball = resultBallMotion[index];
    ball.velocityX += screenAccelerationX * elapsedSeconds;
    ball.velocityY += screenAccelerationY * elapsedSeconds;
    ball.velocityX *= dampingPerStep;
    ball.velocityY *= dampingPerStep;
    float speed = sqrtf(ball.velocityX * ball.velocityX + ball.velocityY * ball.velocityY);
    if (speed > maximumSpeed) {
      float scale = maximumSpeed / speed;
      ball.velocityX *= scale;
      ball.velocityY *= scale;
    }
    ball.x += ball.velocityX * elapsedSeconds;
    ball.y += ball.velocityY * elapsedSeconds;
    constrainResultBall(index);
  }
  resolveResultBallCollisions();
}

void updateResultBallImuAnimation() {
  if (overlayMode != OverlayMode::results) {
    if (resultBallMotionReady) resetResultBallMotion(0);
    return;
  }
  if (selectedResult >= 0) return;

  size_t count = visibleDashboardResultCount();
  if (count == 0) return;
  if (!resultBallMotionReady || resultBallMotionCount != count) resetResultBallMotion(count);
  if (!M5.Imu.isEnabled()) return;

  uint32_t now = millis();
  if (lastResultBallPhysicsAt != 0 &&
      now - lastResultBallPhysicsAt < kResultBallPhysicsIntervalMs) {
    return;
  }
  float elapsedSeconds = lastResultBallPhysicsAt == 0
                             ? kResultBallPhysicsIntervalMs / 1000.0f
                             : min(0.05f, (now - lastResultBallPhysicsAt) / 1000.0f);
  lastResultBallPhysicsAt = now;

  M5.Imu.update();
  float accelX = 0.0f;
  float accelY = 0.0f;
  float accelZ = 0.0f;
  if (!M5.Imu.getAccel(&accelX, &accelY, &accelZ)) return;
  requireHighPerformance();
  stepResultBallPhysics(accelX, accelY, accelZ, elapsedSeconds, now);
  if (lastResultBallFrameAt == 0 ||
      now - lastResultBallFrameAt >= kResultBallFrameIntervalMs) {
    lastResultBallFrameAt = now;
    drawCurrentPage();
  }
}

size_t visibleDashboardResultCount() {
  size_t count = dashboardResults.count;
  bool printerFinished = printer.connected &&
                         (printer.state == "FINISHED" || printer.state == "FINISH");
  if (printerFinished && count < kMaxDashboardResults) ++count;
  return count;
}

void drawResultsOverlay() {
  const uint16_t background = rgb(8, 9, 12);
  canvas.fillScreen(background);
  drawDetailReturnHandle();
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(245, 245, 247));
  useChinese16();
  canvas.drawString("今日成果", 225, 57);

  size_t count = dashboardResults.count;
  bool printerFinished = printer.connected &&
                         (printer.state == "FINISHED" || printer.state == "FINISH");
  if (count == 0 && !printerFinished) {
    canvas.setTextColor(rgb(142, 143, 154));
    canvas.drawString("今天还没有可展示的成果", 225, 230);
    canvas.drawString("完成任务后会自动汇聚成星球", 225, 262);
    return;
  }

  DashboardResult visible[kMaxDashboardResults];
  size_t visibleCount = 0;
  for (size_t index = 0; index < dashboardResults.count && visibleCount < kMaxDashboardResults;
       ++index) {
    visible[visibleCount++] = dashboardResults.items[index];
  }
  if (visibleCount < kMaxDashboardResults && printerFinished) {
    visible[visibleCount++] = {'P', printer.file.length() > 0 ? printer.file : "打印任务完成", 0};
  }

  if (selectedResult >= static_cast<int>(visibleCount)) selectedResult = -1;
  if (selectedResult >= 0) {
    const DashboardResult &item = visible[selectedResult];
    uint16_t accent = providerAccent(item.provider);
    canvas.fillRoundRect(72, 146, 306, 170, 34, rgb(30, 31, 37));
    canvas.fillCircle(225, 183, 10, accent);
    canvas.setTextColor(accent);
    useChinese16();
    canvas.drawString(item.provider == 'A' ? "Claude" : item.provider == 'P' ? "P2S" : "Codex",
                      225, 211);
    canvas.setTextColor(rgb(245, 245, 247));
    useChinese16();
    canvas.drawString(fitTextToWidth(item.title, 250), 225, 247);
    canvas.setTextColor(rgb(126, 127, 137));
    canvas.drawString("再点一次关闭摘要", 225, 287);
    return;
  }

  for (size_t index = 0; index < visibleCount; ++index) {
    int x = 0;
    int y = 0;
    currentResultBallPosition(index, visibleCount, x, y);
    uint16_t accent = providerAccent(visible[index].provider);
    int radius = resultBallRadius(index);
    canvas.fillCircle(x, y, radius + 7, rgb(18, 19, 24));
    canvas.fillCircle(x, y, radius + 3, rgb(39, 40, 47));
    canvas.fillCircle(x, y, radius, accent);
    canvas.fillCircle(x - radius / 3, y - radius / 3, max(3, radius / 5), rgb(237, 237, 242));
    canvas.setTextColor(rgb(12, 13, 17));
    useNumberFont();
    canvas.drawString(String(visible[index].provider), x, y + 3);
  }
  canvas.setTextColor(rgb(112, 113, 124));
  useChinese16();
  canvas.drawString("轻点成果球查看摘要", 225, 416);
}

void openTranscriptFor(bool claudeProvider, int taskIndex) {
  transcriptClaude = claudeProvider;
  TranscriptCollection &collection = activeTranscriptCollection();
  transcriptTaskIndex = taskIndex >= 0 ? taskIndex : collection.taskCount == 1 ? 0 : -1;
  transcriptOffsetFromNewest = 0;
  overlayMode = OverlayMode::transcript;
  overlayUntilAt = 0;
  requireHighPerformance();
  startVibration(70, 35);
  drawCurrentPage();
}

void openTranscript() {
  if (currentPage != 2 && currentPage != 3) return;
  openTranscriptFor(currentPage == 3, -1);
}

void drawOverlay() {
  if (!overlayVisible()) return;
  if (overlayMode == OverlayMode::connection) {
    drawConnectionOverlay();
  } else if (overlayMode == OverlayMode::wifiPicker) {
    drawWifiPickerOverlay();
  } else if (overlayMode == OverlayMode::voice) {
    drawVoiceOverlay();
  } else if (overlayMode == OverlayMode::transcript) {
    drawTranscriptOverlay();
  } else if (overlayMode == OverlayMode::orbit) {
    drawTaskOrbitOverlay();
  } else if (overlayMode == OverlayMode::results) {
    drawResultsOverlay();
  } else {
    drawControlOverlay();
  }
}

uint16_t completionMixedColor(uint8_t fromR, uint8_t fromG, uint8_t fromB,
                              uint8_t toR, uint8_t toG, uint8_t toB,
                              uint8_t percent) {
  int safePercent = min(100, static_cast<int>(percent));
  return rgb(
      static_cast<uint8_t>(fromR + (static_cast<int>(toR) - fromR) * safePercent / 100),
      static_cast<uint8_t>(fromG + (static_cast<int>(toG) - fromG) * safePercent / 100),
      static_cast<uint8_t>(fromB + (static_cast<int>(toB) - fromB) * safePercent / 100));
}

void drawCompletionThickLine(int x0, int y0, int x1, int y1, int width,
                             uint16_t color) {
  float dx = static_cast<float>(x1 - x0);
  float dy = static_cast<float>(y1 - y0);
  float length = sqrtf(dx * dx + dy * dy);
  if (length < 1.0f) return;

  float half = static_cast<float>(width) / 2.0f;
  int offsetX = static_cast<int>(roundf(-dy * half / length));
  int offsetY = static_cast<int>(roundf(dx * half / length));
  canvas.fillTriangle(x0 + offsetX, y0 + offsetY,
                      x1 + offsetX, y1 + offsetY,
                      x1 - offsetX, y1 - offsetY, color);
  canvas.fillTriangle(x0 + offsetX, y0 + offsetY,
                      x1 - offsetX, y1 - offsetY,
                      x0 - offsetX, y0 - offsetY, color);
  int capRadius = max(1, width / 2);
  canvas.fillCircle(x0, y0, capRadius, color);
  canvas.fillCircle(x1, y1, capRadius, color);
}

void drawCompletionCheck(int radius, uint16_t color) {
  if (radius < 6) return;
  int centerX = kDashboardRingCenterX;
  int centerY = kDashboardRingCenterY;
  int startX = centerX - radius * 55 / 100;
  int startY = centerY;
  int jointX = centerX - radius * 17 / 100;
  int jointY = centerY + radius * 36 / 100;
  int endX = centerX + radius * 57 / 100;
  int endY = centerY - radius * 43 / 100;
  int width = max(3, radius * 22 / 100);
  drawCompletionThickLine(startX, startY, jointX, jointY, width, color);
  drawCompletionThickLine(jointX, jointY, endX, endY, width, color);
}

void drawCompletionOverlay(uint32_t now) {
  if (!completionAnimationActive(now)) return;
  uint32_t elapsed = static_cast<uint32_t>(now - completionAnimationStartedAt);
  DashboardCompletionAnimationFrame frame = dashboardCompletionAnimationFrame(elapsed);
  if (!frame.visible) return;

  bool claudeProvider = completionProvider == 'A';
  uint8_t backgroundR = claudeProvider ? 15 : 7;
  uint8_t backgroundG = claudeProvider ? 11 : 8;
  uint8_t backgroundB = claudeProvider ? 9 : 17;
  uint8_t accentR = claudeProvider ? 217 : 95;
  uint8_t accentG = claudeProvider ? 119 : 103;
  uint8_t accentB = claudeProvider ? 87 : 255;
  uint16_t background = rgb(backgroundR, backgroundG, backgroundB);
  uint16_t track = claudeProvider ? rgb(54, 42, 37) : rgb(34, 37, 57);
  uint16_t accent = rgb(accentR, accentG, accentB);

  canvas.fillScreen(background);
  canvas.fillArc(kDashboardRingCenterX, kDashboardRingCenterY,
                 kDashboardRingOuterRadius, kDashboardRingInnerRadius,
                 0, 360, track);
  if (frame.ringDegrees > 0) {
    canvas.fillArc(kDashboardRingCenterX, kDashboardRingCenterY,
                   kDashboardRingOuterRadius, kDashboardRingInnerRadius,
                   -90, -90 + frame.ringDegrees, accent);
  }

  constexpr int completionIconCenterY = 208;
  int iconSize = claudeProvider
                     ? kCenterIconSize * frame.claudeIconScalePercent / 100
                     : kCenterIconSize * 3 / 2;
  int iconX = kDashboardRingCenterX - iconSize / 2;
  int iconY = completionIconCenterY - iconSize / 2;
  float iconScale = static_cast<float>(iconSize) / kCenterIconSize;
  if (claudeProvider) {
    canvas.fillRoundRect(iconX, iconY, iconSize, iconSize,
                         iconSize * 22 / kCenterIconSize, accent);
    canvas.drawPng(claude_mark_png, claude_mark_png_len,
                   iconX, iconY, iconSize, iconSize,
                   0, 0, iconScale, iconScale, datum_t::top_left);
  } else {
    const DashboardPngFrame &iconFrame =
        codex_pet_done_frames[frame.codexFrameIndex];
    canvas.drawPng(iconFrame.data, iconFrame.length,
                   iconX, iconY, iconSize, iconSize,
                   0, 0, iconScale, iconScale, datum_t::top_left);
  }

  if (frame.successRadius <= 0) return;
  uint16_t burstColor = completionMixedColor(
      backgroundR, backgroundG, backgroundB,
      accentR, accentG, accentB, frame.intensityPercent);
  uint16_t checkColor = completionMixedColor(
      backgroundR, backgroundG, backgroundB,
      255, 255, 255, frame.intensityPercent);
  if (frame.successRadius >= kDashboardCompletionFullRadius) {
    canvas.fillScreen(burstColor);
  } else {
    canvas.fillCircle(kDashboardRingCenterX, kDashboardRingCenterY,
                      frame.successRadius, burstColor);
  }
  drawCompletionCheck(frame.successRadius, checkColor);
}

void updateCompletionAnimation() {
  if (!completionAnimationRunning) return;
  uint32_t now = millis();
  if (!completionAnimationActive(now)) {
    completionAnimationRunning = false;
    drawCurrentPage();
    return;
  }
  if (lastCompletionAnimationFrameAt != 0 &&
      static_cast<uint32_t>(now - lastCompletionAnimationFrameAt) <
          kCompletionAnimationRefreshMs) {
    return;
  }
  lastCompletionAnimationFrameAt = now;
  requireHighPerformance();
  drawCurrentPage();
}

bool clockLocalTime(struct tm &local) {
  if (dashboardServerTime <= 0 || dashboardServerTimeAt == 0) return false;
  time_t localEpoch = static_cast<time_t>(
      dashboardServerTime + static_cast<int64_t>((millis() - dashboardServerTimeAt) / 1000) +
      8 * 60 * 60);
  return gmtime_r(&localEpoch, &local) != nullptr;
}

void drawParticleDigit(int value, int x, int y, uint16_t color, uint32_t now) {
  static const uint8_t rows[10][7] = {
      {0x1F, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1F},
      {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E},
      {0x1F, 0x01, 0x01, 0x1F, 0x10, 0x10, 0x1F},
      {0x1F, 0x01, 0x01, 0x1F, 0x01, 0x01, 0x1F},
      {0x11, 0x11, 0x11, 0x1F, 0x01, 0x01, 0x01},
      {0x1F, 0x10, 0x10, 0x1F, 0x01, 0x01, 0x1F},
      {0x1F, 0x10, 0x10, 0x1F, 0x11, 0x11, 0x1F},
      {0x1F, 0x01, 0x01, 0x02, 0x04, 0x04, 0x04},
      {0x1F, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x1F},
      {0x1F, 0x11, 0x11, 0x1F, 0x01, 0x01, 0x1F},
  };
  (void)now;
  if (value < 0 || value > 9) return;
  for (int row = 0; row < 7; ++row) {
    for (int column = 0; column < 5; ++column) {
      if ((rows[value][row] & (1 << (4 - column))) == 0) continue;
      canvas.fillCircle(x + column * 12, y + row * 12, 3, color);
    }
  }
}

void drawParticleTime(const struct tm &local, uint32_t now) {
  int hour = local.tm_hour;
  int minute = local.tm_min;
  const uint16_t white = rgb(245, 245, 247);
  constexpr int top = 116;
  drawParticleDigit(hour / 10, 81, top, white, now);
  drawParticleDigit(hour % 10, 151, top, white, now);
  canvas.fillCircle(225, top + 24, 3, white);
  canvas.fillCircle(225, top + 48, 3, white);
  drawParticleDigit(minute / 10, 249, top, white, now);
  drawParticleDigit(minute % 10, 319, top, white, now);
}

void drawClockWeatherIcon(int x, int y, int code, uint16_t color) {
  bool rain = code >= 51 && code <= 99;
  bool sun = code >= 0 && code <= 1;
  if (sun) {
    canvas.fillCircle(x, y, 7, color);
    for (int angle = 0; angle < 360; angle += 45) {
      float radians = angle * PI / 180.0f;
      canvas.drawLine(x + static_cast<int>(cosf(radians) * 10),
                      y + static_cast<int>(sinf(radians) * 10),
                      x + static_cast<int>(cosf(radians) * 14),
                      y + static_cast<int>(sinf(radians) * 14), color);
    }
    return;
  }
  canvas.fillCircle(x - 6, y + 1, 7, color);
  canvas.fillCircle(x + 2, y - 4, 9, color);
  canvas.fillCircle(x + 10, y + 2, 6, color);
  canvas.fillRect(x - 7, y + 1, 18, 8, color);
  if (rain) {
    canvas.drawLine(x - 5, y + 12, x - 8, y + 18, color);
    canvas.drawLine(x + 3, y + 12, x, y + 18, color);
    canvas.drawLine(x + 11, y + 12, x + 8, y + 18, color);
  }
}

void drawClockCalendarIcon(int left, int top, uint16_t color) {
  canvas.drawRoundRect(left, top + 3, 22, 20, 4, color);
  canvas.drawFastHLine(left + 1, top + 9, 20, color);
  canvas.drawFastVLine(left + 5, top, 6, color);
  canvas.drawFastVLine(left + 17, top, 6, color);
  canvas.fillCircle(left + 7, top + 14, 1, color);
  canvas.fillCircle(left + 12, top + 14, 1, color);
  canvas.fillCircle(left + 17, top + 14, 1, color);
}

void drawClockShortcutDock() {
  constexpr int y = 332;
  constexpr int width = 120;
  constexpr int height = 50;
  constexpr int leftX = 97;
  constexpr int rightX = 233;
  const uint16_t surface = rgb(25, 29, 49);
  const uint16_t foreground = rgb(245, 245, 247);
  const uint16_t codexAccent = rgb(141, 130, 255);
  const uint16_t resultAccent = rgb(255, 181, 83);
  canvas.fillRoundRect(leftX, y, width, height, 18, surface);
  canvas.fillRoundRect(rightX, y, width, height, 18, surface);

  constexpr int iconY = y + height / 2;
  constexpr int orbitX = 120;
  canvas.drawLine(orbitX, iconY - 10, orbitX, iconY + 10, codexAccent);
  canvas.drawLine(orbitX - 10, iconY, orbitX + 10, iconY, codexAccent);
  canvas.drawLine(orbitX - 7, iconY - 7, orbitX + 7, iconY + 7, codexAccent);
  canvas.drawLine(orbitX + 7, iconY - 7, orbitX - 7, iconY + 7, codexAccent);
  canvas.fillCircle(orbitX, iconY, 3, surface);

  constexpr int planetX = 256;
  canvas.drawCircle(planetX, iconY, 8, resultAccent);
  canvas.drawEllipse(planetX, iconY, 13, 5, resultAccent);
  canvas.fillCircle(planetX + 10, iconY - 8, 2, resultAccent);

  canvas.setTextDatum(middle_left);
  canvas.setTextColor(foreground);
  useChinese16();
  canvas.setTextSize(1.25f);
  canvas.drawString("星盘", 143, iconY + 1);
  canvas.drawString("成果", 279, iconY + 1);
  canvas.setTextSize(1);
}

int clockUsagePercent(const CodexData &provider) {
  int value = provider.weekUsedPercent >= 0 ? provider.weekUsedPercent
                                            : provider.shortUsedPercent;
  return value >= 0 ? dashboardRemainingPercent(value) : 0;
}

void drawClockProgressSegment(int startAngle, int endAngle, int percent,
                              uint16_t track, uint16_t active) {
  canvas.fillArc(225, 225, 216, 207, startAngle, endAngle, track);
  int safePercent = max(0, min(100, percent));
  if (safePercent <= 0) return;
  int activeEnd = startAngle +
                  static_cast<int>((endAngle - startAngle) * safePercent / 100.0f + 0.5f);
  canvas.fillArc(225, 225, 216, 207, startAngle, activeEnd, active);
}

void drawClockPage() {
  const uint16_t background = rgb(8, 9, 12);
  canvas.fillScreen(background);
  drawClockProgressSegment(-95, 21, printer.connected ? printer.progress : 0,
                           rgb(22, 36, 30), printerColor());
  drawClockProgressSegment(25, 141, clockUsagePercent(claude),
                           rgb(59, 40, 37), rgb(255, 123, 84));
  drawClockProgressSegment(145, 261, clockUsagePercent(codex),
                           rgb(33, 41, 71), rgb(83, 104, 255));

  struct tm local = {};
  uint32_t now = millis();
  bool timeReady = clockLocalTime(local);
  if (timeReady) {
    drawParticleTime(local, now);
  } else {
    canvas.setTextDatum(middle_center);
    canvas.setTextColor(rgb(245, 245, 247));
    useNumberFont();
    canvas.drawString("--:--", 225, 157);
  }
  drawBatteryStatusAt(background, rgb(142, 145, 160), 190, 72);

  String weatherText = weather.available
                           ? weather.label + " · " + String(weather.temperatureC, 0) + "℃"
                           : "天气暂不可用 · --℃";
  canvas.setTextColor(rgb(245, 245, 247));
  useChinese16();
  canvas.setTextSize(1.35f);
  int weatherTextWidth = canvas.textWidth(weatherText);
  int weatherLeft = 225 - (28 + 10 + weatherTextWidth) / 2;
  drawClockWeatherIcon(weatherLeft + 14, 286, weather.available ? weather.code : 3,
                       weather.available ? rgb(240, 189, 99) : rgb(112, 113, 124));
  canvas.setTextDatum(middle_left);
  canvas.drawString(weatherText, weatherLeft + 38, 286);

  canvas.setTextColor(rgb(200, 204, 218));
  canvas.setTextSize(1.15f);
  String date;
  if (timeReady) {
    static const char *weekdays[] = {"日", "一", "二", "三", "四", "五", "六"};
    date = "周" + String(weekdays[local.tm_wday]) + " · " +
           String(local.tm_mon + 1) + "月" + String(local.tm_mday) + "日";
  } else {
    date = "等待校时";
  }
  int dateTextWidth = canvas.textWidth(date);
  int dateLeft = 225 - (22 + 10 + dateTextWidth) / 2;
  drawClockCalendarIcon(dateLeft, 210, rgb(174, 180, 199));
  canvas.setTextDatum(middle_left);
  canvas.drawString(date, dateLeft + 32, 221);
  canvas.setTextSize(1);
  drawClockShortcutDock();
  drawPageIndicator(rgb(245, 245, 247), rgb(70, 71, 80));
}

void drawPrinterPage() {
  const uint16_t background = rgb(5, 14, 10);
  const uint16_t foreground = rgb(240, 248, 244);
  const uint16_t muted = rgb(130, 148, 140);
  const uint16_t track = rgb(22, 36, 30);
  const uint16_t active = printerColor();

  drawRoundScreenBase(background, track, printer.progress, active);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(168, 183, 176));
  useChinese16();
  canvas.drawString("打印进度", 225, 48);

  canvas.setTextColor(foreground);
  useNumberFont();
  canvas.drawString(String(printer.progress) + "%", 225, 78);
  drawBatteryStatus(background, muted);

  drawMetric("喷嘴", String(printer.nozzle, 0) + "℃", 104, 136, 169, 78, 130,
             muted, foreground, true);
  drawMetric("热床", String(printer.bed, 0) + "℃", 346, 136, 169, 320, 372,
             muted, foreground, true);
  drawMetric("打印层数",
             printer.totalLayers > 0 ? String(printer.layer) + "/" + String(printer.totalLayers)
                                     : String(printer.layer),
             112, 267, 301, 81, 143, muted, foreground);
  drawMetric("机舱", printer.chamber > 0 ? String(printer.chamber, 0) + "℃" : "--",
             338, 267, 301, 312, 364, muted, foreground, true);

  drawBambuLogo(background);
  drawStatusPill(printerStatusCN(), active, rgb(13, 34, 23), rgb(31, 84, 50),
                 rgb(175, 243, 195));
  drawFooterPill("预计剩余", formatDurationCN(printer.remainingMin), rgb(12, 29, 22),
                 rgb(39, 65, 54), muted, rgb(222, 255, 235));
  drawPageIndicator(active, rgb(63, 80, 72));
}

void drawCodexPage() {
  const uint16_t background = rgb(7, 8, 17);
  const uint16_t foreground = rgb(243, 243, 248);
  const uint16_t muted = rgb(142, 145, 160);
  const uint16_t track = rgb(34, 37, 57);
  const uint16_t active = rgb(95, 103, 255);

  bool showWeek = codex.weekUsedPercent >= 0;
  int mainUsedPercent = showWeek ? codex.weekUsedPercent : codex.shortUsedPercent;
  int mainPercent = dashboardRemainingPercent(mainUsedPercent);
  int mainReset = showWeek ? codex.weekResetInMin : codex.shortResetInMin;
  String mainLabel = showWeek ? "本周额度" : "五小时额度";

  drawRoundScreenBase(background, track, mainPercent, active);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(163, 166, 188));
  useChinese16();
  canvas.drawString(mainLabel, 225, 48);

  canvas.setTextColor(rgb(245, 244, 255));
  useNumberFont();
  canvas.drawString((mainPercent >= 0 ? String(mainPercent) + "%" : "--"), 225, 78);
  drawBatteryStatus(background, muted);

  drawMetric("活动任务", String(codex.active), 104, 136, 169, 78, 130, muted, foreground);
  drawMetric("等待确认", String(codex.waiting), 346, 136, 169, 320, 372, muted, foreground);
  drawMetric("今日用量", formatCount(codex.todayTokens), 112, 267, 301, 81, 143, muted, foreground);

  if (showWeek && codex.shortUsedPercent >= 0) {
    drawMetric("五时剩余", String(dashboardRemainingPercent(codex.shortUsedPercent)) + "%", 338, 267, 301,
               312, 364, muted, foreground);
  } else {
    drawMetric("累计", formatLifetimeUsage(codex.lifetimeTokens), 338, 267, 301, 312, 364,
               muted, foreground, true);
  }

  drawCodexIcon(background);
  drawStatusPill(codexStatusCN(), codexStatusColor(), rgb(22, 24, 39), rgb(66, 70, 96),
                 rgb(224, 225, 241));
  drawFooterPill(showWeek ? "周额重置" : "额度重置", formatDurationCN(mainReset),
                 rgb(22, 23, 29), rgb(58, 60, 67), muted, foreground);
  drawPageIndicator(active, rgb(66, 69, 88));
}

void drawClaudePage() {
  const uint16_t background = rgb(15, 11, 9);
  const uint16_t foreground = rgb(250, 249, 245);
  const uint16_t muted = rgb(176, 174, 165);
  const uint16_t track = rgb(54, 42, 37);
  const uint16_t active = rgb(217, 119, 87);
  const uint16_t metricLine = rgb(71, 52, 44);

  int mainPercent = dashboardRemainingPercent(claude.weekUsedPercent);

  drawRoundScreenBase(background, track, mainPercent, active);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(185, 173, 167));
  useChinese16();
  canvas.drawString("本周额度", 225, 48);

  canvas.setTextColor(foreground);
  useNumberFont();
  canvas.drawString((mainPercent >= 0 ? String(mainPercent) + "%" : "--"), 225, 78);
  drawBatteryStatus(background, muted);

  drawMetric("活动任务", String(claude.active), 104, 136, 169, 78, 130,
             muted, foreground, false, metricLine);
  drawMetric("等待确认", String(claude.waiting), 346, 136, 169, 320, 372,
             muted, foreground, false, metricLine);
  drawMetric("今日用量", formatCount(claude.todayTokens), 112, 267, 301, 81, 143,
             muted, foreground, false, metricLine);
  drawMetric("累计", formatLifetimeUsage(claude.lifetimeTokens), 338, 267, 301, 312, 364,
             muted, foreground, true, metricLine);

  drawClaudeIcon(background);
  drawStatusPill(claudeStatusCN(), claudeStatusColor(), rgb(40, 31, 27), rgb(105, 64, 51),
                 rgb(241, 234, 230));
  drawFooterPill("周额重置", formatDurationCN(claude.weekResetInMin), rgb(33, 27, 24),
                 rgb(75, 57, 49), muted, foreground);
  drawPageIndicator(active, rgb(81, 68, 62));
}

void drawConnectingPage() {
  const uint16_t background = rgb(7, 8, 14);
  canvas.fillScreen(background);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(111, 117, 255));
  useChinese24();
  canvas.drawString("监控屏", 225, 178);
  canvas.setTextColor(rgb(235, 236, 241));
  useChinese16();
  String message = "正在自动选择无线网络";
  String detail = "家庭和公司网络都会自动尝试";
  if (WiFi.status() == WL_CONNECTED &&
      (lastBridgeHttpStatus == HTTP_CODE_UNAUTHORIZED ||
       lastBridgeHttpStatus == HTTP_CODE_FORBIDDEN)) {
    message = "电脑令牌不匹配";
    detail = "请在配网页更新这台 Mac 的令牌";
  } else if (WiFi.status() == WL_CONNECTED && activeBridgeHost.length() == 0) {
    message = "未发现电脑";
    detail = "请确认 Mac 桥接已运行且允许设备互访";
  } else if (WiFi.status() == WL_CONNECTED && lastBridgeHttpStatus < 0) {
    message = "电脑暂时不可达";
    detail = "当前网络可能禁止局域网设备互访";
  } else if (WiFi.status() == WL_CONNECTED) {
    message = "正在连接电脑";
    detail = connectedSsid.length() > 0 ? "已连接 " + connectedSsid : "正在验证桥接服务";
  }
  canvas.drawString(message, 225, 232);
  canvas.setTextColor(rgb(132, 136, 151));
  canvas.drawString(detail, 225, 270);
  canvas.drawString("长按 A+B 可重新配网", 225, 307);
}

void drawProvisioningPage(const String &apName, bool ready) {
  const uint16_t background = rgb(7, 8, 14);
  canvas.fillScreen(background);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(111, 117, 255));
  useChinese24();
  canvas.drawString("配网模式", 225, 118);
  canvas.setTextColor(rgb(235, 236, 241));
  useChinese16();
  if (!ready) {
    canvas.drawString("正在扫描附近网络", 225, 186);
  } else {
    canvas.drawString("手机连接热点", 225, 175);
    canvas.setTextColor(rgb(166, 170, 185));
    canvas.drawString(apName, 225, 210);
    canvas.drawString("密码 m5dashboard", 225, 242);
    canvas.setTextColor(rgb(235, 236, 241));
    canvas.drawString("打开 192.168.4.1", 225, 286);
    canvas.setTextColor(rgb(133, 137, 151));
    canvas.drawString("保存后设备会自动重启", 225, 316);
    canvas.drawString("再次长按 A+B 取消", 225, 342);
    if (settings.ssid.length() > 0 || settings.ssid2.length() > 0) {
      canvas.fillRoundRect(112, 365, 226, 44, 18, rgb(24, 25, 48));
      canvas.drawRoundRect(112, 365, 226, 44, 18, rgb(73, 77, 133));
      canvas.setTextColor(rgb(220, 222, 255));
      canvas.drawString("选择已保存网络", 225, 387);
    }
  }
  composeRenderedFrame(background);
  pushRenderedFrame(background);
}

String provisioningAccessPointName() {
  uint32_t suffix = static_cast<uint32_t>(ESP.getEfuseMac() & 0xFFFF);
  char buffer[24];
  snprintf(buffer, sizeof(buffer), "M5-Dashboard-%04X", suffix);
  return String(buffer);
}

void startProvisioning() {
  // Network scanning can block for several seconds, so never carry a timed
  // dashboard alert into provisioning mode.
  if (voiceSessionActive) {
    endVoiceCapture();
    voiceSessionActive = false;
  }
  stopVibration();
  stopTonePattern();
  requireHighPerformance();
  configMode = true;
  provisioningTouchPending = false;
  bridgeOnline = false;
  discoveryUdp.stop();
  discoveryUdpStarted = false;
  String apName = provisioningAccessPointName();
  drawProvisioningPage(apName, false);
  bool ready = provisioning.begin(settings, apName);
  drawProvisioningPage(apName, ready);
  if (!ready) {
    delay(1500);
    ESP.restart();
  }
}

void renderCurrentPage() {
  if (!haveData) {
    drawConnectingPage();
  } else if (currentPage == 0) {
    drawClockPage();
  } else if (currentPage == 1) {
    drawPrinterPage();
  } else if (currentPage == 2) {
    drawCodexPage();
  } else {
    drawClaudePage();
  }
  drawOverlay();
  drawCompletionOverlay(millis());
  composeRenderedFrame(currentRenderedBackground());
}

void drawCurrentPage() {
  renderCurrentPage();
  pushRenderedFrame(currentRenderedBackground());
}

void updateCenterIconAnimation() {
  if (!iconCanvasReady || !haveData || configMode || screenLocked ||
      completionAnimationRunning || overlayMode != OverlayMode::none ||
      activeGesture != DashboardGesture::none) {
    return;
  }

  uint32_t now = millis();
  if (static_cast<uint32_t>(now - lastIconAnimationAt) < kIconAnimationRefreshMs) return;
  lastIconAnimationAt = now;

  if (currentPage == 2) {
    DashboardCodexIconMode mode = currentCodexIconMode(now);
    size_t frame = currentCodexIconFrame(mode, now);
    int modeValue = static_cast<int>(mode);
    if (lastAnimatedIconPage == currentPage && lastAnimatedIconMode == modeValue &&
        lastAnimatedIconFrame == frame) {
      return;
    }
    if (mode != DashboardCodexIconMode::idle) requireHighPerformance();
    composeCodexIcon(rgb(7, 8, 17), now);
    copyIconCanvasToPage(true);
    lastAnimatedIconPage = currentPage;
    lastAnimatedIconMode = modeValue;
    lastAnimatedIconFrame = frame;
    return;
  }

  if (currentPage == 3) {
    uint8_t scale = currentClaudeScalePercent(now);
    int modeValue = claude.connected && claude.active > 0 ? 1 : 0;
    if (lastAnimatedIconPage == currentPage && lastAnimatedIconMode == modeValue &&
        lastAnimatedIconFrame == scale) {
      return;
    }
    if (modeValue != 0) requireHighPerformance();
    composeClaudeIcon(rgb(15, 11, 9), now);
    copyIconCanvasToPage(true);
    lastAnimatedIconPage = currentPage;
    lastAnimatedIconMode = modeValue;
    lastAnimatedIconFrame = scale;
  }
}

void notifyTransitions(const PrinterData &oldPrinter, const CodexData &oldCodex, bool hadData,
                       bool completionStarted) {
  if (!hadData) return;
  if (oldPrinter.state != printer.state &&
      (printer.state == "FINISHED" || printer.state == "ERROR")) {
    startVibration(printer.state == "ERROR" ? 230 : 170,
                   printer.state == "ERROR" ? 500 : 220);
    if (printer.state == "ERROR") {
      startTonePattern(kPrinterErrorTones,
                       sizeof(kPrinterErrorTones) / sizeof(kPrinterErrorTones[0]));
    } else {
      startTonePattern(kPrinterDoneTones,
                       sizeof(kPrinterDoneTones) / sizeof(kPrinterDoneTones[0]));
    }
  } else if (codex.waiting > oldCodex.waiting) {
    // A task can complete and immediately enter the next waiting turn in the
    // same state update. Do not make that task-complete update vibrate.
    if (!completionStarted) startVibration(190, 300);
    startTonePattern(kCodexWaitingTones,
                     sizeof(kCodexWaitingTones) / sizeof(kCodexWaitingTones[0]));
  }
}

void updateLimitSlot(int &percentSlot, int &resetSlot, JsonObject limit, int64_t serverTime) {
  percentSlot = limit["used_percent"] | -1;
  int64_t resetsAt = limit["resets_at"] | 0LL;
  resetSlot = resetsAt > serverTime ? static_cast<int>((resetsAt - serverTime + 59) / 60) : -1;
}

void applyTranscriptState(JsonObject source, TranscriptCollection &destination) {
  destination.taskCount = 0;
  for (size_t taskIndex = 0; taskIndex < kMaxTranscriptTasks; ++taskIndex) {
    destination.tasks[taskIndex] = TranscriptTask();
  }

  JsonArray tasks = source["transcripts"].as<JsonArray>();
  if (tasks.isNull()) return;
  for (JsonObject taskSource : tasks) {
    if (destination.taskCount >= kMaxTranscriptTasks) break;
    TranscriptTask &task = destination.tasks[destination.taskCount++];
    task.id = String(static_cast<const char *>(taskSource["id"] | ""));
    task.title = String(static_cast<const char *>(taskSource["title"] | "当前任务"));
    task.status = String(static_cast<const char *>(taskSource["status"] | "working"));
    JsonArray messages = taskSource["messages"].as<JsonArray>();
    if (messages.isNull()) continue;
    for (JsonObject messageSource : messages) {
      if (task.messageCount >= kMaxTranscriptMessages) break;
      TranscriptMessage &message = task.messages[task.messageCount++];
      String role = String(static_cast<const char *>(messageSource["role"] | "assistant"));
      message.user = role == "user";
      message.text = String(static_cast<const char *>(messageSource["text"] | ""));
    }
  }
}

void appendDashboardResults(JsonObject source, char provider) {
  JsonArray results = source["results"].as<JsonArray>();
  if (results.isNull()) return;
  for (JsonObject result : results) {
    if (dashboardResults.count >= kMaxDashboardResults) break;
    DashboardResult &destination = dashboardResults.items[dashboardResults.count++];
    destination.provider = provider;
    destination.title = String(static_cast<const char *>(result["title"] | "已完成任务"));
    destination.completedAt = result["completed_at"] | 0LL;
  }
}

void sortDashboardResults() {
  for (size_t left = 0; left < dashboardResults.count; ++left) {
    for (size_t right = left + 1; right < dashboardResults.count; ++right) {
      if (dashboardResults.items[right].completedAt <=
          dashboardResults.items[left].completedAt) {
        continue;
      }
      DashboardResult temporary = dashboardResults.items[left];
      dashboardResults.items[left] = dashboardResults.items[right];
      dashboardResults.items[right] = temporary;
    }
  }
}

String dashboardResultSource(const DashboardResult &result) {
  int separator = result.title.indexOf(" · ");
  if (separator > 0 && separator <= 12) return result.title.substring(0, separator);
  return "本机";
}

bool updateCompletionResults() {
  int64_t nextCodexWatermark = lastSeenCodexCompletionAt;
  int64_t nextClaudeWatermark = lastSeenClaudeCompletionAt;
  size_t newCount = 0;
  const DashboardResult *newest = nullptr;

  for (size_t index = 0; index < dashboardResults.count; ++index) {
    const DashboardResult &result = dashboardResults.items[index];
    int64_t previousWatermark = result.provider == 'A'
                                    ? lastSeenClaudeCompletionAt
                                    : lastSeenCodexCompletionAt;
    if (result.provider == 'A') {
      nextClaudeWatermark = max(nextClaudeWatermark, result.completedAt);
    } else {
      nextCodexWatermark = max(nextCodexWatermark, result.completedAt);
    }
    if (!completionBaselineReady || result.completedAt <= previousWatermark ||
        result.completedAt <= 0) {
      continue;
    }
    ++newCount;
    if (newest == nullptr || result.completedAt > newest->completedAt) newest = &result;
  }

  lastSeenCodexCompletionAt = nextCodexWatermark;
  lastSeenClaudeCompletionAt = nextClaudeWatermark;
  if (!completionBaselineReady) {
    completionBaselineReady = true;
    return false;
  }
  if (newest != nullptr) {
    startCompletionAnimation(newest->provider, dashboardResultSource(*newest), newCount);
    return true;
  }
  return false;
}

bool applyDashboardState(JsonDocument &doc) {
  PrinterData oldPrinter = printer;
  CodexData oldCodex = codex;
  bool hadData = haveData;
  if (hadData && lastStateAppliedAt != 0 &&
      static_cast<uint32_t>(millis() - lastStateAppliedAt) > kCompletionStateGapMs) {
    completionBaselineReady = false;
  }

  JsonObject p = doc["printer"];
  printer.connected = p["connected"] | false;
  printer.progress = p["progress"] | 0;
  printer.remainingMin = p["remaining_min"] | 0;
  printer.nozzle = p["nozzle_temp"] | 0.0f;
  printer.bed = p["bed_temp"] | 0.0f;
  printer.chamber = p["chamber_temp"] | 0.0f;
  printer.layer = p["layer"] | 0;
  printer.totalLayers = p["total_layers"] | 0;
  printer.state = String(static_cast<const char *>(p["state_label"] | "UNKNOWN"));
  printer.file = String(static_cast<const char *>(p["file"] | ""));

  JsonObject c = doc["codex"];
  codex.connected = c["connected"] | false;
  codex.active = c["active_count"] | 0;
  codex.waiting = c["waiting_count"] | 0;
  codex.errors = c["error_count"] | 0;
  codex.weekUsedPercent = -1;
  codex.weekResetInMin = -1;
  codex.shortUsedPercent = -1;
  codex.shortResetInMin = -1;

  int64_t serverTime = doc["server_time"] | 0LL;
  if (serverTime > 0) {
    dashboardServerTime = serverTime;
    dashboardServerTimeAt = millis();
  }
  for (JsonObject limit : c["limits"].as<JsonArray>()) {
    String id = String(static_cast<const char *>(limit["id"] | ""));
    String name = String(static_cast<const char *>(limit["name"] | ""));
    String lowerId = id;
    String lowerName = name;
    lowerId.toLowerCase();
    lowerName.toLowerCase();
    if (lowerId.indexOf("bengalfox") >= 0 || lowerName.indexOf("spark") >= 0) continue;

    int windowMinutes = limit["window_minutes"] | 0;
    if (windowMinutes > 0 && windowMinutes <= 360) {
      if (codex.shortUsedPercent < 0 || id == "codex" || id.startsWith("codex:")) {
        updateLimitSlot(codex.shortUsedPercent, codex.shortResetInMin, limit, serverTime);
      }
    } else if (windowMinutes >= 1440 || codex.weekUsedPercent < 0) {
      if (codex.weekUsedPercent < 0 || id == "codex" || id.startsWith("codex:")) {
        updateLimitSlot(codex.weekUsedPercent, codex.weekResetInMin, limit, serverTime);
      }
    }
  }

  codex.todayTokens = c["usage"]["today_tokens"] | 0LL;
  codex.lifetimeTokens = c["usage"]["lifetime_tokens"] | 0LL;
  codex.firstTitle = "";
  codex.firstStatus = "";
  JsonArray sessions = c["sessions"].as<JsonArray>();
  if (!sessions.isNull() && sessions.size() > 0) {
    codex.firstTitle = String(static_cast<const char *>(sessions[0]["title"] | ""));
    codex.firstStatus = String(static_cast<const char *>(sessions[0]["status"] | ""));
  }
  applyTranscriptState(c, codexTranscripts);

  JsonObject a = doc["claude"];
  claude.connected = a["connected"] | false;
  claude.active = a["active_count"] | 0;
  claude.waiting = a["waiting_count"] | 0;
  claude.errors = a["error_count"] | 0;
  claude.weekUsedPercent = a["week_used_percent"] | -1;
  claude.shortUsedPercent = a["short_used_percent"] | -1;
  int64_t weekResetsAt = a["week_resets_at"] | 0LL;
  int64_t shortResetsAt = a["short_resets_at"] | 0LL;
  claude.weekResetInMin = weekResetsAt > serverTime
                              ? static_cast<int>((weekResetsAt - serverTime + 59) / 60)
                              : -1;
  claude.shortResetInMin = shortResetsAt > serverTime
                               ? static_cast<int>((shortResetsAt - serverTime + 59) / 60)
                               : -1;
  claude.todayTokens = a["today_tokens"] | 0LL;
  claude.lifetimeTokens = a["lifetime_tokens"] | 0LL;
  claude.firstTitle = "";
  claude.firstStatus = "";
  applyTranscriptState(a, claudeTranscripts);

  dashboardResults = DashboardResultCollection();
  appendDashboardResults(c, 'C');
  appendDashboardResults(a, 'A');
  sortDashboardResults();
  bool completionStarted = updateCompletionResults();

  JsonObject w = doc["weather"];
  weather.available = w["available"] | false;
  weather.city = String(static_cast<const char *>(w["city"] | "苏州"));
  weather.temperatureC = w["temperature_c"] | 0.0f;
  weather.code = w["weather_code"] | -1;
  weather.label = String(static_cast<const char *>(w["label"] | ""));
  weather.updatedAt = w["updated_at"] | 0LL;

  if (hadData && oldCodex.active > 0 && codex.active == 0 && codex.connected &&
      codex.waiting == 0 && codex.errors == 0) {
    codexDoneAnimationUntilAt = millis() + kCodexDoneAnimationMs;
  }

  haveData = true;
  lastStateAppliedAt = millis();
  notifyTransitions(oldPrinter, oldCodex, hadData, completionStarted);
  return true;
}

bool fetchState() {
  if (WiFi.status() != WL_CONNECTED) return false;
  if (activeBridgeHost.length() == 0 || activeBridgePort == 0 ||
      (settings.token.length() == 0 && settings.token2.length() == 0)) {
    return false;
  }
  String url = "http://" + activeBridgeHost + ":" + String(activeBridgePort) + "/api/state";

  String tokens[2] = {settings.token, settings.token2};
  int tokenOrder[2] = {0, 1};
  if (activeTokenSlot == 1) {
    tokenOrder[0] = 1;
    tokenOrder[1] = 0;
  }
  JsonDocument doc;
  bool received = false;
  lastBridgeHttpStatus = 0;
  for (int orderIndex = 0; orderIndex < 2; ++orderIndex) {
    int tokenIndex = tokenOrder[orderIndex];
    if (tokens[tokenIndex].length() == 0 ||
        (orderIndex > 0 && tokens[tokenIndex] == tokens[tokenOrder[0]])) {
      continue;
    }
    HTTPClient http;
    http.setTimeout(2500);
    if (!http.begin(url)) {
      lastBridgeHttpStatus = -1;
      return false;
    }
    http.addHeader("X-Dashboard-Token", tokens[tokenIndex]);
    int statusCode = http.GET();
    lastBridgeHttpStatus = statusCode;
    if (statusCode == HTTP_CODE_OK) {
      DeserializationError parseError = deserializeJson(doc, http.getStream());
      http.end();
      if (parseError) {
        lastBridgeHttpStatus = -2;
        return false;
      }
      activeTokenSlot = tokenIndex;
      received = true;
      break;
    }
    http.end();
    if (statusCode != HTTP_CODE_UNAUTHORIZED && statusCode != HTTP_CODE_FORBIDDEN) break;
  }
  if (!received) return false;
  bridgeOnline = true;
  return applyDashboardState(doc);
}

void sendUsbStateRequest() {
  String tokens[2] = {settings.token, settings.token2};
  int tokenSlot = activeUsbTokenSlot;
  if (tokenSlot < 0) {
    tokenSlot = pendingUsbTokenSlot == 1 ? 0 : 1;
  }
  if (tokens[tokenSlot].length() == 0) tokenSlot = 1 - tokenSlot;
  if (tokens[tokenSlot].length() == 0) return;
  pendingUsbTokenSlot = tokenSlot;
  dashboardBridgeSerial.print(kUsbRequestPrefix);
  dashboardBridgeSerial.println(tokens[tokenSlot]);
  lastUsbRequestAt = millis();
}

void handleUsbResponse(const String &line) {
  if (line.startsWith(kUsbErrorPrefix)) {
    activeUsbTokenSlot = -1;
    lastUsbRequestAt = 0;
    return;
  }
  if (!line.startsWith(kUsbResponsePrefix)) return;
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, line.substring(strlen(kUsbResponsePrefix)));
  if (error || !applyDashboardState(doc)) return;
  activeUsbTokenSlot = pendingUsbTokenSlot;
  usbBridgeOnline = true;
  lastUsbStateAt = millis();
}

uint32_t dashboardStateRefreshInterval() {
  return overlayMode == OverlayMode::transcript ? kTranscriptRefreshMs
                                                : kUsbRequestIntervalMs;
}

void updateUsbBridge() {
  while (dashboardBridgeSerial.available() > 0) {
    char value = static_cast<char>(dashboardBridgeSerial.read());
    if (value == '\n') {
      usbResponseLine.trim();
      handleUsbResponse(usbResponseLine);
      usbResponseLine = "";
    } else if (value != '\r') {
      if (usbResponseLine.length() < kUsbMaxLineBytes) {
        usbResponseLine += value;
      } else {
        usbResponseLine = "";
      }
    }
  }
  if (usbBridgeOnline && millis() - lastUsbStateAt >= kUsbStateStaleMs) {
    usbBridgeOnline = false;
  }
  if (lastUsbRequestAt == 0 ||
      millis() - lastUsbRequestAt >= dashboardStateRefreshInterval()) {
    sendUsbStateRequest();
  }
}

IPAddress subnetBroadcastAddress() {
  IPAddress local = WiFi.localIP();
  IPAddress mask = WiFi.subnetMask();
  IPAddress broadcast;
  for (int index = 0; index < 4; ++index) {
    broadcast[index] = local[index] | static_cast<uint8_t>(~mask[index]);
  }
  return broadcast;
}

void sendDiscoveryQuery() {
  const char query[] = "M5DASH_DISCOVER_V1";
  IPAddress broadcast = subnetBroadcastAddress();
  discoveryUdp.beginPacket(broadcast, kDiscoveryPort);
  discoveryUdp.write(reinterpret_cast<const uint8_t *>(query), strlen(query));
  discoveryUdp.endPacket();
}

void processDiscoveryResponses() {
  int packetSize = discoveryUdp.parsePacket();
  while (packetSize > 0) {
    char buffer[96];
    int length = discoveryUdp.read(buffer, sizeof(buffer) - 1);
    if (length > 0) {
      buffer[length] = '\0';
      const char prefix[] = "M5DASH_BRIDGE_V1|";
      if (strncmp(buffer, prefix, strlen(prefix)) == 0) {
        long discoveredPort = String(buffer + strlen(prefix)).toInt();
        if (discoveredPort >= 1 && discoveredPort <= 65535) {
          String candidate = discoveryUdp.remoteIP().toString();
          if (candidate.length() > 0 &&
              (!bridgeOnline || activeBridgeHost.length() == 0 || settings.host.length() == 0)) {
            activeBridgeHost = candidate;
            activeBridgePort = static_cast<uint16_t>(discoveredPort);
          }
        }
      }
    }
    packetSize = discoveryUdp.parsePacket();
  }
}

void updateBridgeDiscovery() {
  if (WiFi.status() != WL_CONNECTED) {
    if (discoveryUdpStarted) discoveryUdp.stop();
    discoveryUdpStarted = false;
    return;
  }
  if (!discoveryUdpStarted) {
    discoveryUdpStarted = discoveryUdp.begin(kDiscoveryLocalPort) == 1;
    lastDiscoveryAt = 0;
  }
  if (!discoveryUdpStarted) return;

  processDiscoveryResponses();
  if (!bridgeOnline && (lastDiscoveryAt == 0 || millis() - lastDiscoveryAt >= 5000)) {
    lastDiscoveryAt = millis();
    sendDiscoveryQuery();
  }
}

void resetBridgeForNetworkChange() {
  bridgeOnline = false;
  haveData = false;
  activeTokenSlot = -1;
  lastBridgeHttpStatus = 0;
  // A fixed address is a work-network fallback. Home must keep using discovery
  // so the temporary company address never breaks the original installation.
  activeBridgeHost = connectedSsid == settings.ssid ? "" : settings.host;
  activeBridgePort = settings.port;
  if (discoveryUdpStarted) discoveryUdp.stop();
  discoveryUdpStarted = false;
  lastDiscoveryAt = 0;
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    String currentSsid = WiFi.SSID();
    if (wifiManualSwitchPending) {
      const String targetSsid = wifiManualProfile == 0 ? settings.ssid : settings.ssid2;
      if (currentSsid != targetSsid) {
        WiFi.disconnect(false, false);
        connectedSsid = "";
        resetBridgeForNetworkChange();
        wifiAttemptInProgress = false;
        lastWifiAttemptAt = 0;
        return;
      }
    }
    wifiSearchStartedAt = 0;
    wifiAttemptInProgress = false;
    if (currentSsid != connectedSsid) {
      connectedSsid = currentSsid;
      resetBridgeForNetworkChange();
    }
    if (wifiManualSwitchPending) {
      wifiManualSwitchPending = false;
      wifiManualProfile = -1;
      wifiReconnectPaused = false;
      wifiPickerMessage = "";
      showConnectionStatus();
    }
    return;
  }

  if (connectedSsid.length() > 0) {
    connectedSsid = "";
    resetBridgeForNetworkChange();
    wifiAttemptProfile = -1;
    wifiAttemptInProgress = false;
    lastWifiAttemptAt = 0;
  }
  if (wifiReconnectPaused) return;
  bool homeConfigured = settings.ssid.length() > 0;
  bool workConfigured = settings.ssid2.length() > 0;
  if (!homeConfigured && !workConfigured) {
    startProvisioning();
    return;
  }
  if (wifiSearchStartedAt == 0) wifiSearchStartedAt = millis();
  // USB is a data-path fallback, not a reason to turn the Wi-Fi radio off.
  // Without USB, stop after a full automatic search and ask the user what to
  // do next. Never enter the credential-editing portal unexpectedly.
  if (!usbBridgeOnline && millis() - wifiSearchStartedAt >= kAutoWifiSearchTimeoutMs) {
    WiFi.disconnect(false, false);
    wifiAttemptInProgress = false;
    wifiReconnectPaused = true;
    wifiPickerMessage = "未找到可用的已保存网络";
    openWifiPicker();
    return;
  }

  if (wifiAttemptInProgress) {
    if (millis() - wifiAttemptStartedAt < kWifiConnectAttemptMs) return;
    WiFi.disconnect(false, false);
    wifiAttemptInProgress = false;
    lastWifiAttemptAt = millis();
    if (wifiManualSwitchPending) {
      String failedSsid = wifiManualProfile == 0 ? settings.ssid : settings.ssid2;
      wifiManualSwitchPending = false;
      wifiManualProfile = -1;
      wifiReconnectPaused = true;
      wifiPickerMessage = "无法连接  " + failedSsid;
      openWifiPicker();
    }
    return;
  }
  if (lastWifiAttemptAt != 0 && millis() - lastWifiAttemptAt < kWifiRetryIntervalMs) return;

  if (wifiManualSwitchPending && wifiManualProfile >= 0) {
    wifiAttemptProfile = wifiManualProfile;
  } else {
    wifiAttemptProfile = nextConfiguredWifiProfile(wifiAttemptProfile, homeConfigured,
                                                   workConfigured);
  }
  if (wifiAttemptProfile < 0) return;
  const String &ssid = wifiAttemptProfile == 0 ? settings.ssid : settings.ssid2;
  const String &password = wifiAttemptProfile == 0 ? settings.password : settings.password2;

  lastWifiAttemptAt = millis();
  wifiAttemptStartedAt = lastWifiAttemptAt;
  wifiAttemptInProgress = true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), password.c_str());
}

bool requestWifiProfile(int profile) {
  if (profile < -1 || profile > 1) return false;
  if ((profile == 0 && settings.ssid.length() == 0) ||
      (profile == 1 && settings.ssid2.length() == 0)) {
    startVibration(45, 35);
    wifiPickerMessage = profile == 0 ? "家庭网络尚未配置" : "公司网络尚未配置";
    overlayUntilAt = millis() + kWifiPickerOverlayMs;
    drawCurrentPage();
    return false;
  }

  const String targetSsid = profile == 0 ? settings.ssid
                            : profile == 1 ? settings.ssid2
                                           : "";
  if (profile == -1 && WiFi.status() == WL_CONNECTED) {
    wifiManualSwitchPending = false;
    wifiManualProfile = -1;
    wifiReconnectPaused = false;
    wifiPickerMessage = "";
    showConnectionStatus();
    return true;
  }
  if (profile >= 0 && WiFi.status() == WL_CONNECTED && WiFi.SSID() == targetSsid) {
    wifiManualSwitchPending = false;
    wifiManualProfile = -1;
    wifiReconnectPaused = false;
    wifiPickerMessage = "";
    showConnectionStatus();
    return true;
  }

  requireHighPerformance();
  wifiManualSwitchPending = profile >= 0;
  wifiManualProfile = profile;
  wifiReconnectPaused = false;
  wifiPickerMessage = "";
  wifiAttemptProfile = -1;
  wifiAttemptInProgress = false;
  lastWifiAttemptAt = 0;
  wifiAttemptStartedAt = 0;
  wifiSearchStartedAt = millis();

  // A manual selection gets one full connection attempt. Failure returns to
  // the connection center instead of unexpectedly opening the captive portal.
  if (WiFi.status() != WL_DISCONNECTED || connectedSsid.length() > 0) {
    WiFi.disconnect(false, false);
  }
  connectedSsid = "";
  resetBridgeForNetworkChange();
  showConnectionStatus();
  return true;
}

void changePage(int delta) {
  int nextPage = (currentPage + delta + pageCount) % pageCount;
  if (nextPage == currentPage) return;
  requireHighPerformance();

  if (!frameCanvasReady || !transitionCanvasReady || frameCanvas.getBuffer() == nullptr ||
      transitionCanvas.getBuffer() == nullptr) {
    currentPage = nextPage;
    overlayMode = OverlayMode::none;
    drawCurrentPage();
    startVibration(65, 30);
    return;
  }

  size_t pixelBytes = static_cast<size_t>(kUiFrameSize) * kUiFrameSize * 2;
  memcpy(transitionCanvas.getBuffer(), frameCanvas.getBuffer(), pixelBytes);
  currentPage = nextPage;
  overlayMode = OverlayMode::none;
  renderCurrentPage();

  constexpr int frameCount = 10;
  constexpr int frameDurationMs = 14;
  int displayWidth = kUiFrameSize;
  int displayOffsetX = displayFrameOffsetX();
  int displayOffsetY = displayFrameOffsetY();
  int direction = delta > 0 ? 1 : -1;
  for (int frame = 1; frame <= frameCount; ++frame) {
    int numerator = frame * frame * (3 * frameCount - 2 * frame);
    int offset = displayWidth * numerator / (frameCount * frameCount * frameCount);
    M5.Display.startWrite();
    fillDisplayFrameMargins(currentRenderedBackground());
    if (direction > 0) {
      transitionCanvas.pushSprite(displayOffsetX - offset, displayOffsetY);
      frameCanvas.pushSprite(displayOffsetX + displayWidth - offset, displayOffsetY);
    } else {
      transitionCanvas.pushSprite(displayOffsetX + offset, displayOffsetY);
      frameCanvas.pushSprite(displayOffsetX - displayWidth + offset, displayOffsetY);
    }
    M5.Display.endWrite();
    delay(frameDurationMs);
  }
  pushRenderedFrame(currentRenderedBackground());
  startVibration(65, 30);
}

void updateControlHaptic(int percent) {
  int step = percent / 10;
  if (step == lastControlHapticStep) return;
  lastControlHapticStep = step;
  startVibration(75, 24);
}

void updateGestureControl(const m5::touch_detail_t &touch) {
  if (activeGesture == DashboardGesture::brightness) {
    int value = adjustedDashboardPercent(gestureStartBrightness, touch.distanceY(),
                                         kMinimumBrightnessPercent, kControlTravelPixels,
                                         kControlStepPercent);
    overlayMode = OverlayMode::brightness;
    if (value == brightnessPercent) return;
    brightnessPercent = value;
    applyDisplayBrightness();
    updateControlHaptic(value);
    drawCurrentPage();
    return;
  }
  if (activeGesture == DashboardGesture::volume) {
    int value = adjustedDashboardPercent(gestureStartVolume, touch.distanceY(), 0,
                                         kControlTravelPixels, kControlStepPercent);
    overlayMode = OverlayMode::volume;
    if (value == notificationVolumePercent && notificationMuted == (value == 0)) return;
    notificationVolumePercent = value;
    notificationMuted = value == 0;
    if (value > 0) lastAudibleVolumePercent = value;
    applySpeakerVolume();
    if (notificationMuted) stopTonePattern();
    updateControlHaptic(value);
    drawCurrentPage();
  }
}

void finishTouchGesture(const m5::touch_detail_t &touch) {
  DashboardGesture finishedGesture = activeGesture;
  if (finishedGesture == DashboardGesture::page &&
      abs(touch.distanceX()) >= kSwipeThreshold) {
    changePage(touch.distanceX() < 0 ? 1 : -1);
  } else if (finishedGesture == DashboardGesture::brightness ||
             finishedGesture == DashboardGesture::volume) {
    overlayUntilAt = millis() + kControlOverlayMs;
    saveUiPreferences();
    if (finishedGesture == DashboardGesture::volume && !notificationMuted) {
      startTonePattern(kVolumePreviewTone,
                       sizeof(kVolumePreviewTone) / sizeof(kVolumePreviewTone[0]));
    }
    drawCurrentPage();
  } else if (finishedGesture == DashboardGesture::none &&
             abs(touch.distanceX()) < kGestureLockThreshold &&
             abs(touch.distanceY()) < kGestureLockThreshold) {
    int designX = touch.base_x - displayFrameOffsetX() - designFrameOffset();
    int designY = touch.base_y - displayFrameOffsetY() - designFrameOffset();
    if (currentPage == 0 && designY >= 326 && designY <= 390) {
      if (designX >= 89 && designX < 225) {
        overlayMode = OverlayMode::orbit;
        startVibration(55, 28);
        drawCurrentPage();
        activeGesture = DashboardGesture::none;
        touchPending = false;
        return;
      }
      if (designX >= 225 && designX <= 361) {
        selectedResult = -1;
        overlayMode = OverlayMode::results;
        startVibration(55, 28);
        drawCurrentPage();
        activeGesture = DashboardGesture::none;
        touchPending = false;
        return;
      }
    }
    bool running = currentPage == 2 ? codex.active > 0
                                    : currentPage == 3 ? claude.active > 0 : false;
    if (running && dashboardPointInExpandedRect(
                       designX, designY, kCenterIconX, kCenterIconY,
                       kCenterIconSize, kCenterIconSize, 14)) {
      activeGesture = DashboardGesture::none;
      touchPending = false;
      openTranscript();
      return;
    }
  }
  activeGesture = DashboardGesture::none;
  touchPending = false;
}

void updateTouchInteraction(const m5::touch_detail_t &touch) {
  if (completionAnimationRunning) {
    if (touch.wasReleased()) {
      completionAnimationRunning = false;
      drawCurrentPage();
    }
    return;
  }
  if (overlayMode == OverlayMode::orbit || overlayMode == OverlayMode::results) {
    if (touch.wasPressed()) {
      requireHighPerformance();
      touchPending = true;
      activeGesture = DashboardGesture::none;
    }
    if (touchPending && touch.wasReleased()) {
      int designX = touch.base_x - displayFrameOffsetX() - designFrameOffset();
      int designY = touch.base_y - displayFrameOffsetY() - designFrameOffset();
      bool isTap = abs(touch.distanceX()) < kGestureLockThreshold &&
                   abs(touch.distanceY()) < kGestureLockThreshold;
      touchPending = false;
      if (!isTap) return;

      if (designX >= 182 && designX <= 268 && designY >= 0 && designY <= 48) {
        overlayMode = OverlayMode::none;
        selectedResult = -1;
        startVibration(50, 25);
        drawCurrentPage();
        return;
      }

      if (overlayMode == OverlayMode::orbit) {
        OrbitTaskItem items[5];
        size_t count = buildOrbitTasks(items);
        for (size_t index = 0; index < count; ++index) {
          int x = 0;
          int y = 0;
          orbitTaskPosition(index, count, x, y);
          if (!dashboardPointInExpandedRect(designX, designY, x - 38, y - 38, 76, 76, 8)) {
            continue;
          }
          if (items[index].provider == 'P') {
            overlayMode = OverlayMode::none;
            currentPage = 1;
            startVibration(60, 30);
            drawCurrentPage();
          } else {
            openTranscriptFor(items[index].provider == 'A', items[index].transcriptIndex);
          }
          return;
        }
        return;
      }

      if (selectedResult >= 0) {
        selectedResult = -1;
        startVibration(45, 24);
        drawCurrentPage();
        return;
      }
      size_t count = visibleDashboardResultCount();
      for (size_t index = 0; index < count; ++index) {
        int x = 0;
        int y = 0;
        currentResultBallPosition(index, count, x, y);
        if (!dashboardPointInExpandedRect(designX, designY, x - 40, y - 40, 80, 80, 4)) {
          continue;
        }
        selectedResult = static_cast<int>(index);
        startVibration(45, 24);
        drawCurrentPage();
        return;
      }
    }
    return;
  }

  if (overlayMode == OverlayMode::transcript) {
    if (touch.wasPressed()) {
      requireHighPerformance();
      touchPending = true;
      activeGesture = DashboardGesture::none;
    }
    if (touchPending && touch.wasReleased()) {
      int designX = touch.base_x - displayFrameOffsetX() - designFrameOffset();
      int designY = touch.base_y - displayFrameOffsetY() - designFrameOffset();
      bool isTap = abs(touch.distanceX()) < kGestureLockThreshold &&
                   abs(touch.distanceY()) < kGestureLockThreshold;
      touchPending = false;
      TranscriptCollection &collection = activeTranscriptCollection();

      if (isTap && designX >= 192 && designX <= 258 && designY >= 4 && designY <= 67) {
        if (transcriptTaskIndex >= 0 && collection.taskCount > 1) {
          transcriptTaskIndex = -1;
          transcriptOffsetFromNewest = 0;
        } else {
          overlayMode = OverlayMode::none;
        }
        startVibration(55, 28);
        drawCurrentPage();
        return;
      }

      if (isTap && transcriptTaskIndex < 0 && collection.taskCount > 1 &&
          designX >= 55 && designX <= 395) {
        for (size_t index = 0; index < collection.taskCount; ++index) {
          int rowY = 142 + static_cast<int>(index) * 76;
          if (designY >= rowY && designY <= rowY + 64) {
            transcriptTaskIndex = static_cast<int>(index);
            transcriptOffsetFromNewest = 0;
            startVibration(60, 30);
            drawCurrentPage();
            return;
          }
        }
      }

      if (transcriptTaskIndex >= 0 && abs(touch.distanceY()) >= 45 &&
          abs(touch.distanceY()) > abs(touch.distanceX())) {
        int selected = min(transcriptTaskIndex,
                           max(0, static_cast<int>(collection.taskCount) - 1));
        int messageCount = collection.taskCount > 0
                               ? static_cast<int>(collection.tasks[selected].messageCount)
                               : 0;
        int delta = touch.distanceY() > 0 ? 1 : -1;
        transcriptOffsetFromNewest = dashboardTranscriptOffset(
            transcriptOffsetFromNewest, delta, messageCount,
            static_cast<int>(kVisibleTranscriptMessages));
        startVibration(45, 24);
        drawCurrentPage();
      }
    }
    return;
  }

  if (overlayMode == OverlayMode::wifiPicker && overlayVisible()) {
    if (touch.wasPressed()) {
      requireHighPerformance();
      touchPending = true;
      activeGesture = DashboardGesture::none;
    }
    if (touchPending && touch.wasReleased()) {
      int designX = touch.base_x - displayFrameOffsetX() - designFrameOffset();
      int designY = touch.base_y - displayFrameOffsetY() - designFrameOffset();
      bool isTap = abs(touch.distanceX()) < kGestureLockThreshold &&
                   abs(touch.distanceY()) < kGestureLockThreshold;
      touchPending = false;
      if (isTap && designX >= 55 && designX <= 395) {
        if (designY >= 96 && designY <= 148) {
          requestWifiProfile(-1);
        } else if (designY >= 154 && designY <= 206) {
          requestWifiProfile(0);
        } else if (designY >= 212 && designY <= 264) {
          requestWifiProfile(1);
        } else if (designY >= 270 && designY <= 322) {
          startProvisioning();
        }
      }
    }
    return;
  }

  if (touch.wasPressed()) {
    requireHighPerformance();
    touchPending = true;
    activeGesture = DashboardGesture::none;
    gestureStartBrightness = brightnessPercent;
    gestureStartVolume = notificationVolumePercent;
    lastControlHapticStep = -1;
    overlayMode = OverlayMode::none;
  }

  if (touchPending && activeGesture == DashboardGesture::none) {
    activeGesture = classifyDashboardGesture(
        touch.distanceX(), touch.distanceY(), touch.base_x, M5.Display.width(),
        kGestureLockThreshold);
  }
  if (activeGesture == DashboardGesture::brightness ||
      activeGesture == DashboardGesture::volume) {
    updateGestureControl(touch);
  }
  if (touchPending && touch.wasReleased()) finishTouchGesture(touch);
}

void updateProvisioningTouch(const m5::touch_detail_t &touch) {
  if (settings.ssid.length() == 0 && settings.ssid2.length() == 0) return;
  if (touch.wasPressed()) provisioningTouchPending = true;
  if (!provisioningTouchPending || !touch.wasReleased()) return;

  int designX = touch.base_x - displayFrameOffsetX() - designFrameOffset();
  int designY = touch.base_y - displayFrameOffsetY() - designFrameOffset();
  bool isTap = abs(touch.distanceX()) < kGestureLockThreshold &&
               abs(touch.distanceY()) < kGestureLockThreshold;
  provisioningTouchPending = false;
  if (!isTap || designX < 112 || designX > 338 || designY < 365 || designY > 409) {
    return;
  }

  // Rebooting cleanly closes the captive portal and restores STA mode. The
  // RTC flag survives this software restart only and opens the saved-network
  // picker without changing any persisted Wi-Fi credentials.
  openWifiPickerAfterRestart = true;
  startVibration(90, 45);
  delay(80);
  ESP.restart();
}

void toggleNotificationMute() {
  requireHighPerformance();
  notificationMuted = !notificationMuted;
  if (!notificationMuted && notificationVolumePercent == 0) {
    notificationVolumePercent = lastAudibleVolumePercent;
  }
  applySpeakerVolume();
  if (notificationMuted) {
    stopTonePattern();
  } else {
    startTonePattern(kVolumePreviewTone,
                     sizeof(kVolumePreviewTone) / sizeof(kVolumePreviewTone[0]));
  }
  saveUiPreferences();
  overlayMode = OverlayMode::volume;
  overlayUntilAt = millis() + kButtonOverlayMs;
  startVibration(90, 45);
  drawCurrentPage();
}

void showConnectionStatus() {
  requireHighPerformance();
  overlayMode = OverlayMode::connection;
  overlayUntilAt = millis() + kConnectionOverlayMs;
  if (usbBridgeOnline) {
    lastUsbRequestAt = 0;
  } else {
    lastFetchAt = 0;
  }
  startVibration(65, 30);
  drawCurrentPage();
}

void openWifiPicker() {
  requireHighPerformance();
  stopTonePattern();
  overlayMode = OverlayMode::wifiPicker;
  overlayUntilAt = millis() + kWifiPickerOverlayMs;
  activeGesture = DashboardGesture::none;
  touchPending = false;
  startVibration(90, 45);
  drawCurrentPage();
}

#if defined(M5DASH_USB_AUDIO)
constexpr uint8_t kEs8311Address = 0x18;
constexpr uint8_t kEs8311AdcPgaRegister = 0x14;
constexpr uint8_t kEs8311AdcScaleRegister = 0x16;
constexpr uint8_t kEs8311AdcVolumeRegister = 0x17;
constexpr uint8_t kEs8311AdcHpfRegister = 0x1C;
constexpr uint8_t kEs8311DifferentialInputPga24Db = 0x18;
constexpr uint8_t kEs8311AdcScale24Db = 0x04;
constexpr uint8_t kEs8311AdcDigitalPlus6Db = 0xCB;
constexpr uint8_t kEs8311AdcDynamicHpf = 0x6A;
constexpr uint32_t kEs8311I2cFrequency = 100000;
constexpr int kEs8311I2cPort = 1;
constexpr int kEs8311SdaPin = 47;
constexpr int kEs8311SclPin = 48;

void clearVoiceAudioQueue() {
  if (voiceAudioQueue == nullptr) return;
  VoiceAudioBlock dropped = {};
  while (xQueueReceive(voiceAudioQueue, &dropped, 0) == pdTRUE) {}
}

bool configureEs8311SpeechProfile() {
  m5gfx::i2c::i2c_temporary_switcher_t codecBus(
      kEs8311I2cPort, kEs8311SdaPin, kEs8311SclPin);

  // Shift 6 dB from the analog PGA into the ADC's digital stage. The overall
  // speech level stays nominally unchanged, while loud syllables gain analog
  // headroom and clip less readily. Keep the ES8311 dynamic HPF enabled.
  const bool pgaWritten = M5.In_I2C.writeRegister8(
      kEs8311Address, kEs8311AdcPgaRegister,
      kEs8311DifferentialInputPga24Db, kEs8311I2cFrequency);
  const bool scaleWritten = M5.In_I2C.writeRegister8(
      kEs8311Address, kEs8311AdcScaleRegister,
      kEs8311AdcScale24Db, kEs8311I2cFrequency);
  const bool volumeWritten = M5.In_I2C.writeRegister8(
      kEs8311Address, kEs8311AdcVolumeRegister,
      kEs8311AdcDigitalPlus6Db, kEs8311I2cFrequency);
  const bool hpfWritten = M5.In_I2C.writeRegister8(
      kEs8311Address, kEs8311AdcHpfRegister,
      kEs8311AdcDynamicHpf, kEs8311I2cFrequency);

  uint8_t pga = 0;
  uint8_t scale = 0;
  uint8_t volume = 0;
  uint8_t hpf = 0;
  const bool pgaRead = M5.In_I2C.readRegister(
      kEs8311Address, kEs8311AdcPgaRegister, &pga, sizeof(pga),
      kEs8311I2cFrequency);
  const bool scaleRead = M5.In_I2C.readRegister(
      kEs8311Address, kEs8311AdcScaleRegister, &scale, sizeof(scale),
      kEs8311I2cFrequency);
  const bool volumeRead = M5.In_I2C.readRegister(
      kEs8311Address, kEs8311AdcVolumeRegister, &volume, sizeof(volume),
      kEs8311I2cFrequency);
  const bool hpfRead = M5.In_I2C.readRegister(
      kEs8311Address, kEs8311AdcHpfRegister, &hpf, sizeof(hpf),
      kEs8311I2cFrequency);
  codecBus.restore();

  return pgaWritten && scaleWritten && volumeWritten && hpfWritten &&
         pgaRead && scaleRead && volumeRead && hpfRead &&
         pga == kEs8311DifferentialInputPga24Db &&
         scale == kEs8311AdcScale24Db &&
         volume == kEs8311AdcDigitalPlus6Db &&
         hpf == kEs8311AdcDynamicHpf;
}

bool startAndTuneMicrophone() {
  auto micConfig = M5.Mic.config();
  micConfig.sample_rate = kVoiceSampleRate;
  micConfig.input_channel = m5::input_only_right;
  micConfig.dma_buf_len = kVoiceBlockSamples;
  micConfig.dma_buf_count = 4;
  micConfig.over_sampling = 1;
  // M5Unified divides magnification by (over_sampling * 2); 2 is unity here.
  micConfig.magnification = 2;
  micConfig.task_priority = kVoiceCaptureTaskPriority;
  M5.Mic.config(micConfig);
  if (!M5.Mic.begin()) return false;

  // The first record() at a new rate can make M5Unified restart and reapply
  // its default codec registers. Prime and discard one 10 ms block, restart
  // cleanly, then apply and read back the ES8311 speech profile last.
  if (!M5.Mic.record(voiceCaptureBuffers[0], kVoiceBlockSamples,
                     kVoiceSampleRate)) {
    M5.Mic.end();
    return false;
  }
  uint32_t primeStartedAt = millis();
  while (M5.Mic.isRecording() != 0 && millis() - primeStartedAt < 120) {
    vTaskDelay(1);
  }
  if (M5.Mic.isRecording() != 0) {
    M5.Mic.end();
    return false;
  }
  M5.Mic.end();
  if (!M5.Mic.begin()) return false;
  for (uint8_t attempt = 0; attempt < 2; ++attempt) {
    if (configureEs8311SpeechProfile()) return true;
    vTaskDelay(1);
  }
  M5.Mic.end();
  return false;
}

void updateVoiceVisuals(const int16_t *samples) {
  int64_t absoluteTotal = 0;
  int peakMagnitude = 0;
  int16_t signedPeak = 0;
  for (size_t sample = 0; sample < kVoiceBlockSamples; ++sample) {
    int value = static_cast<int>(samples[sample]);
    int magnitude = abs(value);
    absoluteTotal += magnitude;
    if (magnitude > peakMagnitude) {
      peakMagnitude = magnitude;
      signedPeak = static_cast<int16_t>(value);
    }
  }
  int rawLevel = min(
      100, static_cast<int>(absoluteTotal / kVoiceBlockSamples) * 100 / 5000);
  portENTER_CRITICAL(&voiceVisualMux);
  voiceLevelPercent = (voiceLevelPercent * 7 + rawLevel) / 8;
  memmove(voiceWaveform, voiceWaveform + 1,
          sizeof(voiceWaveform) - sizeof(voiceWaveform[0]));
  voiceWaveform[kVoiceWaveformPoints - 1] = signedPeak;
  portEXIT_CRITICAL(&voiceVisualMux);
}

void enqueueLatestVoiceBlock(const int16_t *samples, uint32_t voiceGeneration,
                             uint32_t streamGeneration) {
  if (voiceAudioQueue == nullptr) return;
  voiceEnqueueBlock.voiceGeneration = voiceGeneration;
  voiceEnqueueBlock.streamGeneration = streamGeneration;
  memcpy(voiceEnqueueBlock.samples, samples, sizeof(voiceEnqueueBlock.samples));
  while (xQueueSend(voiceAudioQueue, &voiceEnqueueBlock, 0) != pdTRUE) {
    if (xQueueReceive(voiceAudioQueue, &voiceProducerDropBlock, 0) != pdTRUE) {
      taskYIELD();
    }
  }
}

void voiceCaptureTask(void *) {
  const uint32_t sessionGeneration =
      voiceCaptureGeneration.load(std::memory_order_acquire);
  size_t nextBuffer = 0;
  bool captureOk = true;

  while (M5.Mic.isRecording() < 2 && voiceCaptureActive &&
         voiceCaptureGeneration.load(std::memory_order_acquire) ==
             sessionGeneration) {
    if (!M5.Mic.record(voiceCaptureBuffers[nextBuffer], kVoiceBlockSamples,
                       kVoiceSampleRate)) {
      captureOk = false;
      break;
    }
    nextBuffer ^= 1;
  }

  while (captureOk && voiceCaptureActive &&
         voiceCaptureGeneration.load(std::memory_order_acquire) ==
             sessionGeneration) {
    size_t recordingCount = M5.Mic.isRecording();
    if (recordingCount >= 2) {
      vTaskDelay(1);
      continue;
    }

    updateVoiceVisuals(voiceCaptureBuffers[nextBuffer]);
    if (usbAudioStreaming.load(std::memory_order_acquire) &&
        usbLinkUsable.load(std::memory_order_acquire) && !screenLocked) {
      enqueueLatestVoiceBlock(
          voiceCaptureBuffers[nextBuffer], sessionGeneration,
          usbStreamGeneration.load(std::memory_order_acquire));
    }

    if (!voiceCaptureActive ||
        voiceCaptureGeneration.load(std::memory_order_acquire) !=
            sessionGeneration) {
      break;
    }
    if (!M5.Mic.record(voiceCaptureBuffers[nextBuffer], kVoiceBlockSamples,
                       kVoiceSampleRate)) {
      captureOk = false;
      break;
    }
    nextBuffer ^= 1;
  }

  uint32_t drainStartedAt = millis();
  while (M5.Mic.isRecording() != 0 && millis() - drainStartedAt < 120) {
    vTaskDelay(1);
  }
  if (!captureOk) {
    voiceCaptureFailed = true;
    voiceCaptureActive = false;
  }
  voiceCaptureTaskHandle = nullptr;
  vTaskDelete(nullptr);
}

void onUsbAudioEvent(void *, esp_event_base_t eventBase, int32_t eventId,
                     void *eventData) {
  if (eventBase != ARDUINO_USB_AUDIO_CARD_EVENTS ||
      eventId != ARDUINO_USB_AUDIO_CARD_INTERFACE_ENABLE_EVENT || eventData == nullptr) {
    return;
  }
  auto *data = static_cast<arduino_usb_audio_card_event_data_t *>(eventData);
  if (data->interface_enable.interface == UAC_INTERFACE_MIC) {
    usbAudioStreaming.store(data->interface_enable.enable,
                            std::memory_order_release);
    usbStreamGeneration.fetch_add(1, std::memory_order_acq_rel);
    usbStreamResetPending.store(true, std::memory_order_release);
  }
}

void onUsbDeviceEvent(void *, esp_event_base_t eventBase, int32_t eventId,
                      void *) {
  if (eventBase != ARDUINO_USB_EVENTS) return;
  switch (eventId) {
    case ARDUINO_USB_STARTED_EVENT:
    case ARDUINO_USB_RESUME_EVENT:
      usbLinkUsable.store(true, std::memory_order_release);
      break;
    case ARDUINO_USB_STOPPED_EVENT:
      usbAudioStreaming.store(false, std::memory_order_release);
      usbLinkUsable.store(false, std::memory_order_release);
      break;
    case ARDUINO_USB_SUSPEND_EVENT:
      usbLinkUsable.store(false, std::memory_order_release);
      break;
    default:
      return;
  }
  usbStreamGeneration.fetch_add(1, std::memory_order_acq_rel);
  usbStreamResetPending.store(true, std::memory_order_release);
}
#endif

void beginUsbInterfaces() {
#if defined(M5DASH_USB_AUDIO)
  dashboardUsbSerial.setRxBufferSize(kUsbRxQueueBytes);
  dashboardUsbSerial.begin();
  dashboardUsbAudio.onEvent(onUsbAudioEvent);
  USB.onEvent(onUsbDeviceEvent);
  usbAudioReady = dashboardUsbAudio.begin();
  USB.manufacturerName("M5Stack");
  USB.productName("M5 StopWatch Mic");
  // The composite layout changed after HID was removed. Give the CDC + UAC
  // build a fresh identity so CoreAudio does not reuse the old descriptor
  // cache for the earlier CDC + UAC + HID device.
  USB.firmwareVersion(0x0102);
  USB.serialNumber("M5DASHMIC3");
  if (usbAudioReady) usbAudioReady = USB.begin();
  usbLinkUsable.store(usbAudioReady, std::memory_order_release);
  if (usbAudioReady) {
    // Match the UAC1 endpoint's mono/16-bit descriptor exactly: one
    // sample-rate-sized packet per millisecond. TinyUSB otherwise uses a compile-time
    // maximum-rate FIFO threshold that makes CoreAudio repeatedly tear down
    // the input stream before its first correctly sized frame.
    tud_audio_set_ep_in_fifo_threshold(sizeof(int16_t) * kUsbVoicePacketSamples);
  }
#else
  Serial.begin(115200);
#endif
}

#if defined(M5DASH_USB_AUDIO)
bool writeUsbAudioBytes(const int16_t *samples, size_t sampleCount,
                        uint32_t streamGeneration) {
  const uint8_t *cursor = reinterpret_cast<const uint8_t *>(samples);
  size_t remaining = sampleCount * sizeof(int16_t);
  while (remaining != 0) {
    if (!usbAudioReady || screenLocked ||
        !usbAudioStreaming.load(std::memory_order_acquire) ||
        !usbLinkUsable.load(std::memory_order_acquire) ||
        usbStreamGeneration.load(std::memory_order_acquire) != streamGeneration) {
      return false;
    }
    size_t accepted = dashboardUsbAudio.write(cursor, remaining);
    accepted = min(accepted, remaining);
    if (accepted == 0) {
      vTaskDelay(1);
      continue;
    }
    cursor += accepted;
    remaining -= accepted;
  }
  return true;
}

void usbAudioTask(void *) {
  static const int16_t silencePacket[kUsbVoicePacketSamples] = {};
  for (;;) {
    if (!usbAudioReady || screenLocked ||
        !usbLinkUsable.load(std::memory_order_acquire)) {
      vTaskDelay(pdMS_TO_TICKS(screenLocked ? 20 : 4));
      continue;
    }

    if (usbStreamResetPending.exchange(false, std::memory_order_acq_rel)) {
      clearVoiceAudioQueue();
      tud_audio_clear_ep_in_ff();
    }

    if (!usbAudioStreaming.load(std::memory_order_acquire)) {
      vTaskDelay(pdMS_TO_TICKS(4));
      continue;
    }

    const uint32_t streamGeneration =
        usbStreamGeneration.load(std::memory_order_acquire);
    if (!voiceCaptureActive || voiceAudioQueue == nullptr ||
        xQueueReceive(voiceAudioQueue, &voiceUsbTransferBlock,
                      pdMS_TO_TICKS(1)) != pdTRUE) {
      writeUsbAudioBytes(silencePacket, kUsbVoicePacketSamples,
                         streamGeneration);
      taskYIELD();
      continue;
    }

    if (voiceUsbTransferBlock.voiceGeneration !=
            voiceCaptureGeneration.load(std::memory_order_acquire) ||
        voiceUsbTransferBlock.streamGeneration != streamGeneration) {
      continue;
    }
    writeUsbAudioBytes(voiceUsbTransferBlock.samples, kVoiceBlockSamples,
                       streamGeneration);
  }
}

void startUsbAudioTask() {
  voiceAudioQueue = xQueueCreateStatic(
      kVoiceQueuedBlocks, sizeof(VoiceAudioBlock), voiceAudioQueueStorage,
      &voiceAudioQueueControl);
  if (voiceAudioQueue == nullptr) {
    usbAudioReady = false;
    return;
  }
  if (xTaskCreate(usbAudioTask, "m5-uac-tx", kVoiceTaskStackBytes, nullptr,
                  kUsbAudioTaskPriority, &usbAudioTaskHandle) != pdPASS) {
    usbAudioReady = false;
    usbAudioTaskHandle = nullptr;
  }
}
#else
void startUsbAudioTask() {}
#endif

bool beginVoiceCapture() {
  if (voiceCaptureActive) return true;
  requireHighPerformance();
  stopTonePattern();
  voiceCaptureFailed = false;
  overlayMode = OverlayMode::voice;
  overlayUntilAt = 0;
#if defined(M5DASH_USB_AUDIO)
  if (usbAudioReady) {
    disableSpeakerOutput();
    memset(voiceCaptureBuffers, 0, sizeof(voiceCaptureBuffers));
    portENTER_CRITICAL(&voiceVisualMux);
    memset(voiceWaveform, 0, sizeof(voiceWaveform));
    voiceLevelPercent = 0;
    portEXIT_CRITICAL(&voiceVisualMux);
    clearVoiceAudioQueue();

    if (startAndTuneMicrophone()) {
      voiceCaptureGeneration.fetch_add(1, std::memory_order_acq_rel);
      voiceCaptureActive = true;
      TaskHandle_t createdTask = nullptr;
      if (xTaskCreate(voiceCaptureTask, "m5-mic-capture",
                      kVoiceTaskStackBytes, nullptr,
                      kVoiceCaptureTaskPriority, &createdTask) != pdPASS) {
        voiceCaptureTaskHandle = nullptr;
        voiceCaptureActive = false;
        M5.Mic.end();
      } else {
        voiceCaptureTaskHandle = createdTask;
      }
    }
    if (!voiceCaptureActive) {
      voiceCaptureFailed = true;
      // Mic begin failures can leave the shared ES8311 audio rail enabled.
      // Keep both the PA and codec power off until an actual alert is played.
      disableSpeakerOutput();
    } else {
      usbStreamGeneration.fetch_add(1, std::memory_order_acq_rel);
      usbStreamResetPending.store(true, std::memory_order_release);
    }
  } else {
    voiceCaptureFailed = true;
  }
#else
  voiceCaptureFailed = true;
#endif
  startVibration(110, 55);
  drawCurrentPage();
  return voiceCaptureActive;
}

bool deactivateVoiceCaptureStream() {
  bool hadCapture =
      voiceCaptureActive || voiceCaptureTaskHandle != nullptr || voiceCaptureFailed;
  voiceCaptureActive = false;
  voiceCaptureGeneration.fetch_add(1, std::memory_order_acq_rel);
  usbStreamGeneration.fetch_add(1, std::memory_order_acq_rel);
  usbStreamResetPending.store(true, std::memory_order_release);
  clearVoiceAudioQueue();
  return hadCapture;
}

void finishVoiceCaptureHardware(bool hadCapture) {
  uint32_t taskStopStartedAt = millis();
  while (voiceCaptureTaskHandle != nullptr &&
         millis() - taskStopStartedAt < 180) {
    delay(1);
  }
  if (voiceCaptureTaskHandle != nullptr) {
    TaskHandle_t stalledTask = voiceCaptureTaskHandle;
    vTaskDelete(stalledTask);
    voiceCaptureTaskHandle = nullptr;
  }
  if (hadCapture) {
    uint32_t drainStartedAt = millis();
    while (M5.Mic.isRecording() != 0 && millis() - drainStartedAt < 120) {
      delay(1);
    }
    M5.Mic.end();
  }
  // The mic and speaker share the ES8311 power rail. Mic shutdown powers down
  // the codec registers but does not lower that rail; Speaker.end() does both.
  disableSpeakerOutput();
}

void stopVoiceCaptureHardware() {
  finishVoiceCaptureHardware(deactivateVoiceCaptureStream());
}

void endVoiceCapture() {
#if defined(M5DASH_USB_AUDIO)
  // Invalidate the PCM stream first, then leave the microphone UI immediately.
  // I2S/task cleanup can take a few hundred milliseconds, but it no longer
  // blocks the visible response to the B-button release.
  bool hadCapture = deactivateVoiceCaptureStream();
#endif
  voiceCaptureActive = false;
  overlayMode = OverlayMode::none;
  overlayUntilAt = 0;
  startVibration(70, 35);
  drawCurrentPage();
#if defined(M5DASH_USB_AUDIO)
  finishVoiceCaptureHardware(hadCapture);
#endif
}

void toggleVoiceSession() {
  if (!voiceSessionActive) {
    voiceSessionActive = beginVoiceCapture();
    return;
  }

  voiceSessionActive = false;
  endVoiceCapture();
}

void updateVoiceAudio() {
  if (voiceSessionActive && voiceCaptureFailed && !voiceCaptureActive) {
    voiceSessionActive = false;
#if defined(M5DASH_USB_AUDIO)
    stopVoiceCaptureHardware();
#endif
    overlayMode = OverlayMode::voice;
    overlayUntilAt = millis() + kVoiceStoppedOverlayMs;
    drawCurrentPage();
    return;
  }
  if (voiceCaptureActive && millis() - lastVoiceAnimationAt >= 80) {
    lastVoiceAnimationAt = millis();
    drawCurrentPage();
  }
}

void updateOverlayTimeout() {
  if (overlayMode == OverlayMode::none ||
      overlayMode == OverlayMode::transcript ||
      overlayMode == OverlayMode::orbit ||
      overlayMode == OverlayMode::results ||
      (overlayMode == OverlayMode::voice && voiceCaptureActive) ||
      (overlayMode == OverlayMode::wifiPicker &&
       (touchPending || wifiReconnectPaused)) ||
      activeGesture == DashboardGesture::brightness ||
      activeGesture == DashboardGesture::volume ||
      static_cast<int32_t>(millis() - overlayUntilAt) < 0) {
    return;
  }
  if (wifiReconnectPaused) {
    overlayMode = OverlayMode::wifiPicker;
    overlayUntilAt = millis() + kWifiPickerOverlayMs;
    drawCurrentPage();
    return;
  }
  overlayMode = OverlayMode::none;
  drawCurrentPage();
}

bool readVoiceButtonPressed() {
  // M5Unified normally owns button debouncing. The raw KEYB read is an explicit
  // fallback for StopWatch builds where the board-specific button event is lost.
  return M5.BtnB.isPressed() || digitalRead(kVoiceButtonPin) == LOW;
}

void beginVoiceButtonPress() {
  voiceButtonTracking = true;
  voiceButtonConsumed = false;
  voiceButtonPressedAt = millis();
  requireHighPerformance();
  overlayMode = OverlayMode::voice;
  overlayUntilAt = millis() + kButtonOverlayMs;
  drawCurrentPage();
}

void cancelVoiceButtonPress() {
  voiceButtonTracking = false;
  voiceButtonConsumed = false;
  voiceButtonPressedAt = 0;
}

void beginAButtonPress() {
  aButtonTracking = true;
  aButtonConsumed = false;
  aButtonLongTriggered = false;
  aButtonPressedAt = millis();
  requireHighPerformance();
}

void cancelAButtonPress() {
  aButtonTracking = false;
  aButtonConsumed = false;
  aButtonLongTriggered = false;
  aButtonPressedAt = 0;
}

}  // namespace

void setup() {
  bool shouldOpenSavedWifiPicker = openWifiPickerAfterRestart;
  openWifiPickerAfterRestart = false;
  auto config = M5.config();
  config.clear_display = true;
  M5.begin(config);
  pinMode(kVoiceButtonPin, INPUT_PULLUP);
  configurePowerButtonPolicy();
  disableBottomLed();
  M5.Display.setRotation(0);
  loadUiPreferences();
  // M5.begin() initializes the internal speaker by default. The dashboard is
  // silent most of the time, so leave the codec and PA off until a tone starts.
  disableSpeakerOutput();
  canvas.setColorDepth(16);
  canvas.createSprite(kUiDesignSize, kUiDesignSize);
  initializeUiChineseFont();
  frameCanvas.setColorDepth(16);
  frameCanvasReady = frameCanvas.createSprite(kUiFrameSize, kUiFrameSize) != nullptr;
  iconCanvas.setColorDepth(16);
  iconCanvasReady = iconCanvas.createSprite(kCenterIconSize, kCenterIconSize) != nullptr;
  transitionCanvas.setColorDepth(16);
  transitionCanvasReady =
      transitionCanvas.createSprite(kUiFrameSize, kUiFrameSize) != nullptr;
  lastHighPerformanceAt = millis();
  updateDevicePower(true);

  DashboardSettings defaults;
  // Credentials never ship inside firmware images. Existing devices load their
  // saved NVS values; a fresh device opens the provisioning portal.
  defaults.ssid = "";
  defaults.password = "";
  defaults.ssid2 = "";
  defaults.password2 = "";
  defaults.host = "";
  defaults.port = 8765;
  defaults.token = "";
  defaults.token2 = "";
  settings = loadDashboardSettings(defaults);
  shouldOpenSavedWifiPicker =
      shouldOpenSavedWifiPicker && (settings.ssid.length() > 0 || settings.ssid2.length() > 0);
  if (shouldOpenSavedWifiPicker) wifiReconnectPaused = true;
  activeBridgeHost = settings.host;
  activeBridgePort = settings.port;
  beginUsbInterfaces();
  startUsbAudioTask();
  usbResponseLine.reserve(4096);

  WiFi.mode(WIFI_STA);
  // Rotate profiles ourselves so Arduino-ESP32 2.x and 3.x never get stuck
  // retrying a stale SDK-managed profile.
  WiFi.setAutoReconnect(false);
  connectWifi();
  if (!configMode) {
    drawCurrentPage();
    if (shouldOpenSavedWifiPicker) openWifiPicker();
  }
}

void loop() {
  M5.update();
  updatePowerButton();
  if (screenLocked) {
    delay(25);
    return;
  }

  updateVibration();
  updateTonePattern();
  updateVoiceAudio();
  updateAudioPowerGuard();
  updateDevicePower();
  if (usbAudioStreaming) requireHighPerformance();
  updateCpuPolicy();
  updateOverlayTimeout();
  updateCompletionAnimation();
  updateCenterIconAnimation();
  updateResultBallImuAnimation();
  if (configMode) {
    bool bothButtons = M5.BtnA.isPressed() && readVoiceButtonPressed();
    if (!bothButtons) configHoldTriggered = false;
    if (bothButtons && !configHoldTriggered &&
        M5.BtnA.pressedFor(2500) && millis() - voiceButtonPressedAt >= 2500) {
      configHoldTriggered = true;
      stopVibration();
      ESP.restart();
    }
    updateProvisioningTouch(M5.Touch.getDetail());
    provisioning.handle();
    delay(2);
    return;
  }

  bool aButtonPressed = M5.BtnA.isPressed();
  if (aButtonPressed && !aButtonTracking) beginAButtonPress();
  bool voiceButtonPressed = readVoiceButtonPressed();
  if (voiceButtonPressed && !voiceButtonTracking) beginVoiceButtonPress();

  bool bothButtons = aButtonPressed && voiceButtonPressed;
  if (bothButtons) {
    configChordActive = true;
    aButtonConsumed = true;
  }
  if (bothButtons && !configHoldTriggered &&
      M5.BtnA.pressedFor(2500) && millis() - voiceButtonPressedAt >= 2500) {
    configHoldTriggered = true;
    startProvisioning();
    return;
  }
  if (!bothButtons) configHoldTriggered = false;

  if (configChordActive) {
    aButtonConsumed = true;
    voiceButtonConsumed = true;
    if (voiceSessionActive) {
      endVoiceCapture();
      voiceSessionActive = false;
    }
    if (!aButtonPressed && !voiceButtonPressed) {
      configChordActive = false;
      cancelAButtonPress();
      cancelVoiceButtonPress();
    }
  } else {
    if (!voiceButtonPressed && voiceButtonTracking) {
      if (shouldToggleVoiceSessionOnRelease(voiceButtonTracking, voiceButtonConsumed)) {
        toggleVoiceSession();
      }
      cancelVoiceButtonPress();
    }
    if (aButtonPressed && aButtonTracking && !aButtonLongTriggered &&
        static_cast<uint32_t>(millis() - aButtonPressedAt) >= kAButtonLongPressMs) {
      aButtonLongTriggered = true;
      aButtonConsumed = true;
      if (!wifiReconnectPaused) wifiPickerMessage = "";
      openWifiPicker();
    }
    if (!aButtonPressed && aButtonTracking) {
      if (!aButtonConsumed) showConnectionStatus();
      cancelAButtonPress();
    }
  }

  updateUsbBridge();
  connectWifi();
  if (configMode) {
    delay(2);
    return;
  }
  updateBridgeDiscovery();

  auto touch = M5.Touch.getDetail();
  updateTouchInteraction(touch);

  if (millis() - lastFetchAt >= dashboardStateRefreshInterval() &&
      !usbReplyPending(millis(), lastUsbRequestAt, kUsbReplyGraceMs)) {
    lastFetchAt = millis();
    if (!usbBridgeOnline && !fetchState()) bridgeOnline = false;
    drawCurrentPage();
  }
  delay(10);
}
