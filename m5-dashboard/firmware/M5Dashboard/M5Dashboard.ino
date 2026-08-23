#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <M5Unified.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp32-hal-cpu.h>
#include <esp_ota_ops.h>
#include <esp_system.h>
#include <mbedtls/sha256.h>
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
#include "app_shell_logic.h"
#include "claude_icon.h"
#include "feature_assets.h"
#include "icon_animation.h"
#include "icons.h"
#include "interaction_logic.h"
#include "ota_logic.h"
#include "provider_brand_icons.h"
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
M5Canvas stopwatchTimeCanvas(&M5.Display);
M5Canvas clockSecondCanvas(&M5.Display);
M5Canvas aiHotspotBurstCanvas(&M5.Display);

#if M5DASH_HAS_NOTO_UI_FONT
lgfx::VLWfont uiChineseFont;
lgfx::PointerWrapper uiChineseFontData;
lgfx::VLWfont stopwatchDigitFont;
lgfx::PointerWrapper stopwatchDigitFontData;
lgfx::VLWfont editorialMedium14Font;
lgfx::PointerWrapper editorialMedium14FontData;
lgfx::VLWfont editorialBold18Font;
lgfx::PointerWrapper editorialBold18FontData;
lgfx::VLWfont editorialBold24Font;
lgfx::PointerWrapper editorialBold24FontData;
lgfx::VLWfont editorialBold32DigitsFont;
lgfx::PointerWrapper editorialBold32DigitsFontData;
lgfx::VLWfont editorialBold80Font;
lgfx::PointerWrapper editorialBold80FontData;
lgfx::VLWfont editorialBold104Font;
lgfx::PointerWrapper editorialBold104FontData;
#endif
bool uiChineseFontReady = false;
bool stopwatchDigitFontReady = false;
bool editorialMedium14FontReady = false;
bool editorialBold18FontReady = false;
bool editorialBold24FontReady = false;
bool editorialBold32DigitsFontReady = false;
bool editorialBold80FontReady = false;
bool editorialBold104FontReady = false;
bool stopwatchTimeCanvasReady = false;
bool clockSecondCanvasReady = false;
bool aiHotspotBurstCanvasReady = false;

constexpr size_t kMaxTranscriptTasks = 3;
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
  bool contentVisible = false;
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

struct AIHotspotData {
  bool connected = false;
  bool active = false;
  int unreadCount = 0;
  String id;
  String title;
  String source;
  String url;
  int64_t receivedAt = 0;
};

struct ObsidianDiceData {
  bool connected = false;
  int availableCount = 0;
  String title;
  String folder;
  String excerpt;
  String relativePath;
  int64_t rolledAt = 0;
};

struct TickTickData {
  bool connected = false;
  String stopwatchState = "idle";
  int stopwatchElapsed = 0;
  String countdownState = "idle";
  int countdownDuration = 1500;
  int countdownRemaining = 1500;
  int todayFocusSeconds = 0;
  String error;
  uint32_t syncedAt = 0;
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

struct AIUsageData {
  bool connected = false;
  bool complete = false;
  bool approximate = false;
  int64_t todayTotalTokens = 0;
  int64_t todayAuthoritativeTokens = 0;
};

TickTickData ticktick;
CodexData codex;
CodexData claude;
AIUsageData aiUsage;
TranscriptCollection codexTranscripts;
TranscriptCollection claudeTranscripts;
DashboardResultCollection dashboardResults;
WeatherData weather;
AIHotspotData aiHotspot;
ObsidianDiceData obsidianDice;
DashboardSettings settings;
ProvisioningPortal provisioning;
WiFiUDP discoveryUdp;
bool haveData = false;
bool bridgeOnline = false;
bool usbBridgeOnline = false;
bool configMode = false;
bool discoveryUdpStarted = false;
bool completionFetchPending = false;
uint32_t lastCompletionHintAt = 0;
bool configHoldTriggered = false;
int currentPage = 0;
constexpr int pageCount = 7;
// The selected UI source uses #F8F5ED. On the StopWatch's high-brightness
// RGB565 panel that value reads as neutral white, so use a slightly warmer
// hardware-calibrated paper tone. The first #F7F1E2 calibration was still too
// subtle in hand, so Owner selected one warmer step: #F5EAD6.
constexpr uint8_t kEditorialPaperR = 245;
constexpr uint8_t kEditorialPaperG = 234;
constexpr uint8_t kEditorialPaperB = 214;
// Temporary real-device regression boundary: the original provider renderer
// was confirmed enterable before the editorial quota/reset UI batch. Keep the
// new Bridge data contract, but use that proven renderer until the PANIC is
// isolated inside the new provider presentation layer.
constexpr bool kProviderRegressionSafeRenderer = false;
DashboardAppMode appMode = DashboardAppMode::launcher;
int launcherSelection = 0;
LocalStopwatchModel localStopwatch;
std::size_t localStopwatchLapOffset = 0;
bool shellBButtonWasPressed = false;
uint32_t lastLocalStopwatchDrawAt = 0;
constexpr uint16_t kDiscoveryPort = 8766;
constexpr uint16_t kDiscoveryLocalPort = 42101;
String activeBridgeHost;
uint16_t activeBridgePort = 8765;
uint32_t lastFetchAt = 0;
uint32_t lastOtaCheckAt = 0;
constexpr uint32_t kOtaCheckIntervalMs = 60000;
bool otaUpdateRunning = false;
String installedOtaSha;
String rejectedOtaSha;
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
uint8_t usbUnauthorizedCount = 0;
String connectedSsid;
String usbResponseLine;
uint32_t lastUsbRequestAt = 0;
uint32_t lastUsbStateAt = 0;
uint32_t vibrationStopAt = 0;
uint32_t lastBatteryReadAt = 0;
uint32_t lastUsbConnectionReadAt = 0;
int deviceBatteryLevel = -1;
bool deviceCharging = false;
bool deviceUsbConnected = false;
volatile bool screenLocked = false;
bool pendingAiHotspotWake = false;
DashboardPowerButtonState powerButtonState;
bool transitionCanvasReady = false;
bool frameCanvasReady = false;
bool editorialFrameAccentActive = false;
uint16_t editorialFrameAccent = 0;
bool editorialFrameBurstActive = false;
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
DashboardTypelessMode voiceSessionMode = DashboardTypelessMode::unavailable;
bool aButtonTracking = false;
bool aButtonConsumed = false;
bool aButtonLongTriggered = false;
uint32_t aButtonPressedAt = 0;
bool bButtonTracking = false;
bool bButtonConsumed = false;
bool bButtonLongTriggered = false;
uint32_t bButtonPressedAt = 0;
DashboardClickButtonState aClickState;
DashboardClickButtonState bClickState;
uint32_t lastTickTickDrawSecond = 0;
int lastClockDrawSecond = -1;
int lastClockDrawMinute = -1;
bool provisioningTouchPending = false;
RTC_DATA_ATTR bool openWifiPickerAfterRestart = false;
constexpr uint32_t kRenderDiagnosticMagic = 0x4D354447;
RTC_DATA_ATTR uint32_t renderDiagnosticMagic = kRenderDiagnosticMagic;
RTC_DATA_ATTR uint16_t renderDiagnosticStage = 0;
RTC_DATA_ATTR uint8_t renderDiagnosticPage = 7;
uint16_t previousRenderDiagnosticStage = 0;
uint8_t previousRenderDiagnosticPage = 7;
uint8_t bootResetReason = 0;
bool bootDiagnosticAcknowledged = false;
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
bool obsidianShakePreviousReady = false;
float obsidianShakePreviousX = 0.0f;
float obsidianShakePreviousY = 0.0f;
float obsidianShakePreviousZ = 0.0f;
uint32_t lastObsidianShakeAt = 0;
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

constexpr ToneStep kFocusDoneTones[] = {{880, 80, 35}, {1175, 140, 0}};
constexpr ToneStep kCodexWaitingTones[] = {{1047, 120, 0}};
constexpr ToneStep kAiScreamTones[] = {
    {988, 70, 18}, {1319, 70, 18}, {1760, 180, 30}, {2093, 220, 0}};
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
constexpr uint32_t kPowerButtonShortPressMaxMs = 1500;
constexpr uint32_t kPowerButtonDoubleClickMs = 500;
constexpr uint32_t kPowerButtonLongPressMs = 1600;
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
constexpr uint32_t kBButtonLongPressMs = 800;
constexpr uint32_t kCpuIdleDelayMs = 15000;
constexpr uint32_t kVoiceStoppedOverlayMs = 900;
constexpr uint32_t kTranscriptRefreshMs = 1000;
constexpr int kUiDesignSize = 450;
constexpr int kUiFrameSize = 466;
constexpr int kStopwatchTimeX = 45;
constexpr int kStopwatchTimeY = 166;
constexpr int kStopwatchTimeWidth = 360;
constexpr int kStopwatchTimeHeight = 78;
constexpr int kStopwatchTimeBaselineY = 226;
constexpr int kClockSecondPatchX = 308;
constexpr int kClockSecondPatchY = 190;
constexpr int kClockSecondPatchWidth = 70;
constexpr int kClockSecondPatchHeight = 70;
constexpr int kClockSecondTextX = 342;
constexpr int kClockSecondTextY = 225;
constexpr int kClockSecondUnderlineX = 316;
constexpr int kClockSecondUnderlineY = 253;
constexpr int kClockSecondUnderlineWidth = 52;
constexpr int kClockSecondUnderlineHeight = 5;
constexpr int kStopwatchFooterY = 408;
constexpr uint32_t kStopwatchFrameIntervalMs = 20;
constexpr int kDashboardRingCenterX = 225;
constexpr int kDashboardRingCenterY = 225;
constexpr int kDashboardRingOuterRadius = 216;
constexpr int kDashboardRingInnerRadius = 201;
constexpr int kClockQuotaArcOuterRadius = 222;
constexpr int kClockQuotaArcInnerRadius = 208;
constexpr float kClockQuotaArcCenterRadius = 215.0f;
constexpr int kClockQuotaArcCapRadius = 7;
constexpr int kPageIndicatorY = 418;
constexpr int kPageIndicatorActiveRadius = 3;
static_assert(kPageIndicatorY + kPageIndicatorActiveRadius <
                  kDashboardRingCenterY + kDashboardRingInnerRadius,
              "page indicator must not overlap the dashboard ring");
constexpr int kCenterIconX = kProviderIconX;
constexpr int kCenterIconY = kProviderIconY;
constexpr int kCenterIconSize = kProviderIconSize;
constexpr uint32_t kIconAnimationRefreshMs = 100;
constexpr uint32_t kCodexDoneAnimationMs = kDashboardCompletionDurationMs;
constexpr uint32_t kCompletionAnimationRefreshMs = 40;
constexpr uint32_t kCompletionStateGapMs = 15000;
constexpr uint32_t kResultBallPhysicsIntervalMs = 20;
constexpr uint32_t kResultBallFrameIntervalMs = 33;
constexpr uint32_t kResultBallShakeCooldownMs = 180;
constexpr uint8_t kBButtonPin = 1;  // StopWatch KEYB (blue), active low.
constexpr uint32_t kFocusDoubleClickMs = 360;
constexpr uint32_t kCpuHighFrequencyMhz = 240;
constexpr uint32_t kCpuLowFrequencyMhz = 80;
constexpr uint32_t kWifiRetryIntervalMs = 750;
constexpr uint32_t kWifiConnectAttemptMs = 12000;
constexpr uint32_t kAutoWifiSearchTimeoutMs = 60000;
constexpr uint32_t kUsbRequestIntervalMs = 2000;
constexpr uint32_t kUsbReplyGraceMs = 500;
constexpr uint32_t kUsbStateStaleMs = 6000;
// A cold Typeless launch may use the Bridge's 5 second helper timeout plus
// its readiness delay. Generic dashboard actions remain at 3 seconds, while
// this one must not report ERROR after the Mac has already started dictation.
constexpr uint16_t kTypelessHttpActionTimeoutMs = 8000;
constexpr size_t kUsbRxQueueBytes = 4096;
constexpr size_t kUsbMaxLineBytes = 32768 + 64;
constexpr char kUsbRequestPrefix[] = "M5DASH_USB_V1|GET|";
constexpr char kUsbActionPrefix[] = "M5DASH_USB_V1|POST|";
constexpr char kUsbPairRequestPrefix[] = "M5DASH_USB_V1|PAIR|";
constexpr char kUsbPairResponsePrefix[] = "M5DASH_USB_V1|PAIRED|";
constexpr char kUsbResponsePrefix[] = "M5DASH_USB_V1|OK|";
constexpr char kUsbErrorPrefix[] = "M5DASH_USB_V1|ERR|";
constexpr char kUsbDiagnosticPrefix[] = "M5DASH_USB_V1|DIAG|";

void markRenderDiagnostic(uint16_t stage, int page = -1) {
  renderDiagnosticMagic = kRenderDiagnosticMagic;
  renderDiagnosticStage = stage;
  renderDiagnosticPage = static_cast<uint8_t>(page >= 0 && page < pageCount ? page : 7);
}

void markProviderLoopDiagnostic(uint16_t stage) {
  if (appMode == DashboardAppMode::dashboard &&
      (currentPage == 2 || currentPage == 3)) {
    markRenderDiagnostic(stage, currentPage);
  }
}

void drawCurrentPage();
void enterAppLauncher();
bool readBButtonPressed();
size_t visibleDashboardResultCount();
void drawProvisioningPage(const String &apName, bool ready);
void showConnectionStatus();
void openWifiPicker();
void openTranscript();
void performObsidianAction(const String &action);
bool performTypelessAction(const String &action, DashboardTypelessMode mode);
bool overlayVisible();
bool completionAnimationActive(uint32_t now);
bool beginVoiceCapture();
void endVoiceCapture();
void toggleVoiceSession();
void drawEditorialBackdrop(uint16_t accent);
void drawEditorialHeader(const String &primary, const String &secondary,
                         uint16_t ink);
void drawEditorialHero(const String &value, int x, int y, int maxWidth,
                       uint16_t ink, float maxScale);
void drawAIHotspotBurst(M5Canvas &target, int frameOffset);
#if defined(M5DASH_USB_AUDIO)
void stopVoiceCaptureHardware();
#endif

uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return canvas.color565(r, g, b);
}

uint16_t editorialPaperColor() {
  return rgb(kEditorialPaperR, kEditorialPaperG, kEditorialPaperB);
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

uint16_t currentRenderedBackground(uint32_t now) {
  if (appMode == DashboardAppMode::stopwatch) return rgb(0, 0, 0);
  if (appMode == DashboardAppMode::launcher) return editorialPaperColor();
  if (completionAnimationActive(now)) {
    DashboardCompletionAnimationFrame frame = dashboardCompletionAnimationFrame(
        static_cast<uint32_t>(now - completionAnimationStartedAt));
    if (frame.visible) {
      bool claudeProvider = completionProvider == 'A';
      uint8_t backgroundR = claudeProvider ? 15 : 7;
      uint8_t backgroundG = claudeProvider ? 11 : 8;
      uint8_t backgroundB = claudeProvider ? 9 : 17;
      // The completion compositor replaces the 450 px design canvas with a
      // dark provider animation. Keep the surrounding 8 px of the 466 px
      // physical frame on that same background from the very first visible
      // frame; otherwise the round panel exposes four paper-coloured points at
      // its top, right, bottom, and left edges.
      if (frame.successRadius < kDashboardCompletionFullRadius) {
        return rgb(backgroundR, backgroundG, backgroundB);
      }
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
  if (kProviderRegressionSafeRenderer && haveData &&
      overlayMode == OverlayMode::none && (currentPage == 2 || currentPage == 3)) {
    return currentPage == 2 ? rgb(7, 8, 17) : rgb(15, 11, 9);
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
    // Typeless LIVE is still the light editorial page, not a dark full-screen
    // overlay. Its 466 px frame must use the same paper colour as the 450 px
    // design canvas or the outer 8 px appears as black clipping.
    if (overlayMode == OverlayMode::voice) return editorialPaperColor();
    return rgb(7, 8, 14);
  }
  return editorialPaperColor();
}

void composeRenderedFrame(uint16_t background) {
  if (!frameCanvasReady) return;
  frameCanvas.fillSprite(background);
  int offset = designFrameOffset();
  if (editorialFrameBurstActive) {
    // The design canvas is 450 px inside the 466 px physical frame. Repeat the
    // same raster in the outer frame before compositing the design canvas so
    // the burst reaches the bezel instead of ending in an 8 px paper seam.
    drawAIHotspotBurst(frameCanvas, offset);
  }
  if (editorialFrameAccentActive) {
    frameCanvas.fillSmoothCircle(364 + offset, 130 + offset, 164,
                                 editorialFrameAccent);
  }
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

bool initializeStopwatchDigitFont() {
#if M5DASH_HAS_NOTO_UI_FONT
  static_assert(kStopwatchFontGlyphCount == 12,
                "The Stopwatch font must contain 0-9, colon, and period");
  if (reinterpret_cast<const volatile char *>(kStopwatchFontIdentity)[0] != 'M') {
    return false;
  }
  stopwatchDigitFontData.set(kStopwatchFontVlw, kStopwatchFontVlwSize);
  stopwatchDigitFontReady = stopwatchDigitFont.loadFont(&stopwatchDigitFontData);
  return stopwatchDigitFontReady;
#else
  return false;
#endif
}

bool initializeEditorialFonts() {
#if M5DASH_HAS_NOTO_UI_FONT
  editorialMedium14FontData.set(kEditorialMedium14Vlw, kEditorialMedium14VlwSize);
  editorialBold18FontData.set(kEditorialBold18Vlw, kEditorialBold18VlwSize);
  editorialBold24FontData.set(kEditorialBold24Vlw, kEditorialBold24VlwSize);
  editorialBold32DigitsFontData.set(kEditorialBold32DigitsVlw,
                                    kEditorialBold32DigitsVlwSize);
  editorialBold80FontData.set(kEditorialBold80Vlw, kEditorialBold80VlwSize);
  editorialBold104FontData.set(kEditorialBold104Vlw, kEditorialBold104VlwSize);
  editorialMedium14FontReady = editorialMedium14Font.loadFont(&editorialMedium14FontData);
  editorialBold18FontReady = editorialBold18Font.loadFont(&editorialBold18FontData);
  editorialBold24FontReady = editorialBold24Font.loadFont(&editorialBold24FontData);
  editorialBold32DigitsFontReady =
      editorialBold32DigitsFont.loadFont(&editorialBold32DigitsFontData);
  editorialBold80FontReady = editorialBold80Font.loadFont(&editorialBold80FontData);
  editorialBold104FontReady = editorialBold104Font.loadFont(&editorialBold104FontData);
  return editorialMedium14FontReady && editorialBold18FontReady &&
         editorialBold24FontReady && editorialBold32DigitsFontReady &&
         editorialBold80FontReady &&
         editorialBold104FontReady;
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

void useEditorialMicro14() {
#if M5DASH_HAS_NOTO_UI_FONT
  canvas.setFont(editorialMedium14FontReady ? &editorialMedium14Font : &uiChineseFont);
#else
  canvas.setFont(&fonts::efontCN_16);
#endif
  canvas.setTextSize(1);
}

void useEditorialBold18() {
#if M5DASH_HAS_NOTO_UI_FONT
  canvas.setFont(editorialBold18FontReady ? &editorialBold18Font : &uiChineseFont);
#else
  canvas.setFont(&fonts::efontCN_16);
#endif
  canvas.setTextSize(1);
}

void useEditorialBold24() {
#if M5DASH_HAS_NOTO_UI_FONT
  canvas.setFont(editorialBold24FontReady ? &editorialBold24Font : &uiChineseFont);
#else
  canvas.setFont(&fonts::efontCN_24);
#endif
  canvas.setTextSize(1);
}

void useEditorialBold24(M5Canvas &target) {
#if M5DASH_HAS_NOTO_UI_FONT
  target.setFont(editorialBold24FontReady ? &editorialBold24Font : &uiChineseFont);
#else
  target.setFont(&fonts::efontCN_24);
#endif
  target.setTextSize(1);
}

void useClockSecondFont(M5Canvas &target) {
#if M5DASH_HAS_NOTO_UI_FONT
  target.setFont(editorialBold32DigitsFontReady ? &editorialBold32DigitsFont
                                                : &editorialBold24Font);
#else
  target.setFont(&fonts::efontCN_24);
#endif
  target.setTextSize(1);
}

void drawClockSecondValue(M5Canvas &target, int originX, int originY,
                          int second, uint16_t mint, uint16_t ink) {
  target.fillRect(kClockSecondPatchX - originX, kClockSecondPatchY - originY,
                  kClockSecondPatchWidth, kClockSecondPatchHeight, mint);
  char buffer[3];
  snprintf(buffer, sizeof(buffer), "%02d", second);
  target.setTextColor(ink);
  target.setTextDatum(middle_center);
  useClockSecondFont(target);
  target.drawString(buffer, kClockSecondTextX - originX,
                    kClockSecondTextY - originY);
  target.fillRect(kClockSecondUnderlineX - originX,
                  kClockSecondUnderlineY - originY,
                  kClockSecondUnderlineWidth, kClockSecondUnderlineHeight, ink);
}

void useEditorialHero104() {
#if M5DASH_HAS_NOTO_UI_FONT
  if (editorialBold104FontReady) {
    canvas.setFont(&editorialBold104Font);
  } else {
    canvas.setFont(&fonts::Font8);
  }
#else
  canvas.setFont(&fonts::Font8);
#endif
  canvas.setTextSize(1);
}

void useEditorialHero80() {
#if M5DASH_HAS_NOTO_UI_FONT
  if (editorialBold80FontReady) {
    canvas.setFont(&editorialBold80Font);
  } else {
    canvas.setFont(&fonts::Font8);
  }
#else
  canvas.setFont(&fonts::Font8);
#endif
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

bool forceVibrationOffVerified() {
  // M5Unified's StopWatch vibration helper performs a single unchecked I2C
  // write. During a blocking OTA that write can be lost, leaving PWM1 latched
  // at the previous duty until the main loop resumes. Write the IOE1 PWM1
  // register directly and require several matching read-backs before allowing
  // the flash transfer to begin.
  constexpr uint8_t kMotorPwmRegister = 0x1B;
  constexpr uint8_t kRequiredConfirmations = 3;
  constexpr uint8_t kMaximumAttempts = 12;
  const uint8_t disabledPwm[2] = {0x00, 0x00};
  auto &ioe1 = M5.getIOExpander(0);
  uint8_t confirmations = 0;

  vibrationStopAt = 0;
  for (uint8_t attempt = 0; attempt < kMaximumAttempts; ++attempt) {
    // Keep the public API call as a fallback, then use the return-valued I2C
    // path for the authoritative write and read-back.
    M5.Power.setVibration(0);
    uint8_t actualPwm[2] = {0xFF, 0xFF};
    bool writeOk = ioe1.writeRegister(kMotorPwmRegister, disabledPwm,
                                      sizeof(disabledPwm));
    bool readOk = ioe1.readRegister(kMotorPwmRegister, actualPwm,
                                    sizeof(actualPwm));
    if (writeOk && readOk && actualPwm[0] == 0x00 && actualPwm[1] == 0x00) {
      if (++confirmations >= kRequiredConfirmations) {
        lastVibrationPowerGuardAt = millis();
        return true;
      }
    } else {
      confirmations = 0;
    }
    delay(10);
  }
  lastVibrationPowerGuardAt = millis();
  return false;
}

bool pulseVibrationBlocking(uint8_t strength, uint16_t durationMs) {
  // OTA transfer deliberately owns the main loop, so the normal
  // updateVibration() deadline cannot stop a pulse until the transfer ends.
  // Close these three lifecycle pulses and prove PWM1 is off before continuing.
  startVibration(strength, durationMs);
  delay(durationMs);
  bool stopped = forceVibrationOffVerified();
  delay(40);
  return stopped;
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
  config1 |= 0x01;                     // Single click belongs to the app shell.
  M5.In_I2C.writeRegister8(kM5Pm1Address, kM5Pm1ButtonConfig1Register, config1,
                           kM5Pm1I2cFrequency);

  uint8_t config2 = M5.In_I2C.readRegister8(
      kM5Pm1Address, kM5Pm1ButtonConfig2Register, kM5Pm1I2cFrequency);
  config2 |= 0x01;  // Disable PMIC double-click shutdown; software uses long press.
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
  if (voiceSessionActive) performTypelessAction("stop", voiceSessionMode);
  voiceSessionActive = false;
  voiceSessionMode = DashboardTypelessMode::unavailable;
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
    // Display standby is deliberately not network standby. Typeless releases
    // the microphone, while Wi-Fi, Bridge polling, the speaker and the haptic
    // path remain available for an AI hotspot alert.
    stopVoiceForStandby();
    aButtonTracking = false;
    aButtonConsumed = false;
    aButtonLongTriggered = false;
    aButtonPressedAt = 0;
    bButtonTracking = false;
    bButtonConsumed = false;
    bButtonLongTriggered = false;
    bButtonPressedAt = 0;
    overlayMode = OverlayMode::none;
    completionAnimationRunning = false;
    completionBaselineReady = false;
    activeGesture = DashboardGesture::none;
    touchPending = false;
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
  if (pendingAiHotspotWake) {
    pendingAiHotspotWake = false;
    appMode = DashboardAppMode::dashboard;
    currentPage = 5;
    overlayMode = OverlayMode::none;
  }
  if (configMode) {
    ESP.restart();
  } else {
    drawCurrentPage();
  }
}

void updatePowerButton() {
  bool pressed = readPowerButtonPressed();
  DashboardPowerAction action = updateDashboardPowerButton(
      powerButtonState, pressed, millis(), kPowerButtonShortPressMaxMs,
      kPowerButtonDoubleClickMs, kPowerButtonLongPressMs, deviceUsbConnected);
  if (action == DashboardPowerAction::toggleScreen) {
    setScreenLocked(!screenLocked);
  } else if (action == DashboardPowerAction::openLauncher) {
    // A deliberate double-click wins over the deferred AI-hotspot wake route.
    pendingAiHotspotWake = false;
    if (screenLocked) setScreenLocked(false);
    enterAppLauncher();
  } else if (action == DashboardPowerAction::powerOff) {
    if (!screenLocked) setScreenLocked(true);
    disableBottomLed();
    M5.Power.powerOff();
  }
}

void updateDevicePower(bool force = false) {
  constexpr uint32_t usbRefreshMs = 500;
  if (force || lastUsbConnectionReadAt == 0 ||
      millis() - lastUsbConnectionReadAt >= usbRefreshMs) {
    lastUsbConnectionReadAt = millis();
    int vbusMillivolts = M5.Power.getVBUSVoltage();
    deviceUsbConnected = vbusMillivolts >= 4000 || deviceCharging;
  }

  constexpr uint32_t refreshMs = 15000;
  if (!force && lastBatteryReadAt != 0 && millis() - lastBatteryReadAt < refreshMs) return;
  lastBatteryReadAt = millis();
  int level = M5.Power.getBatteryLevel();
  deviceBatteryLevel = level >= 0 ? max(0, min(100, level)) : -1;
  deviceCharging =
      M5.Power.isCharging() == m5::Power_Class::is_charging_t::is_charging;
  // Charging can become false at 100%, while VBUS still needs to reserve the
  // PMIC's USB + 2 second Download Mode action.
  int vbusMillivolts = M5.Power.getVBUSVoltage();
  deviceUsbConnected = vbusMillivolts >= 4000 || deviceCharging;
}

bool typelessUsbAvailable() {
#if defined(M5DASH_USB_AUDIO)
  return dashboardTypelessUsbAvailable(
      usbAudioReady, deviceUsbConnected,
      usbLinkUsable.load(std::memory_order_acquire), usbBridgeOnline);
#else
  return false;
#endif
}

DashboardTypelessMode availableTypelessMode() {
  return dashboardTypelessMode(
      typelessUsbAvailable(), WiFi.status() == WL_CONNECTED,
      bridgeOnline && activeBridgeHost.length() > 0 && activeBridgePort > 0);
}

void drawBatteryStatusAt(uint16_t background, uint16_t normalColor,
                         int iconX, int iconY, bool useChargingAccent = true) {
  constexpr int iconWidth = 24;
  constexpr int iconHeight = 13;
  uint16_t color = normalColor;
  if (deviceCharging && useChargingAccent) {
    color = rgb(58, 222, 126);
  } else if (deviceBatteryLevel >= 0 && deviceBatteryLevel <= 15) {
    color = rgb(255, 91, 91);
  } else if (deviceBatteryLevel >= 0 && deviceBatteryLevel <= 30) {
    color = rgb(255, 190, 75);
  }

  canvas.drawRoundRect(iconX, iconY, iconWidth, iconHeight, 3, color);
  canvas.fillRoundRect(iconX + iconWidth, iconY + 4, 3, 6, 1, color);
  if (deviceBatteryLevel >= 0) {
    // While charging, use the percent text for the exact level and reserve the
    // full battery body as a stable high-contrast field for the lightning
    // cutout. A level-proportional fill can be too short to reach the bolt.
    int fillWidth = deviceCharging
                        ? (iconWidth - 4)
                        : (iconWidth - 4) * deviceBatteryLevel / 100;
    if (fillWidth > 0) {
      canvas.fillRoundRect(iconX + 2, iconY + 2, fillWidth, iconHeight - 4, 2, color);
    }
  }
  if (deviceCharging) {
    // Two filled wedges form a bold lightning cutout that remains visible on
    // the 466 px AMOLED instead of collapsing to a one-pixel zig-zag.
    canvas.fillTriangle(iconX + 14, iconY + 1,
                        iconX + 8, iconY + 7,
                        iconX + 14, iconY + 7, background);
    canvas.fillTriangle(iconX + 11, iconY + 6,
                        iconX + 17, iconY + 6,
                        iconX + 11, iconY + 12, background);
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

String formatDurationCompact(int minutes) {
  if (minutes < 0) return "--";
  if (minutes < 60) return String(minutes) + "m";
  if (minutes < 1440) {
    int hours = minutes / 60;
    int rest = minutes % 60;
    return rest > 0 ? String(hours) + "h" + String(rest) + "m"
                    : String(hours) + "h";
  }
  int days = minutes / 1440;
  int hours = (minutes % 1440) / 60;
  return hours > 0 ? String(days) + "d" + String(hours) + "h"
                   : String(days) + "d";
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

bool countUsesChineseHundredMillions(int64_t value) {
  return value >= 100000000;
}

String formatChineseCountNumber(int64_t value) {
  if (!countUsesChineseHundredMillions(value)) return formatCount(value);
  char buffer[24];
  double hundredMillions = static_cast<double>(value) / 100000000.0;
  snprintf(buffer, sizeof(buffer), "%.2f", hundredMillions);
  String result(buffer);
  while (result.endsWith("0")) {
    result.remove(result.length() - 1);
  }
  if (result.endsWith(".")) result.remove(result.length() - 1);
  return result;
}

String formatChineseCount(int64_t value) {
  String result = formatChineseCountNumber(value);
  if (countUsesChineseHundredMillions(value)) result += "亿";
  return result;
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
  return countUsesChineseHundredMillions(value) ? formatChineseCount(value)
                                                : formatThousands(value);
}

bool timerRunning(const String &state) {
  return state == "running" || state == "RUNNING";
}

bool timerPaused(const String &state) {
  return state == "paused" || state == "PAUSED";
}

int currentStopwatchElapsed() {
  int elapsed = ticktick.stopwatchElapsed;
  if (timerRunning(ticktick.stopwatchState) && ticktick.syncedAt != 0) {
    elapsed += static_cast<uint32_t>(millis() - ticktick.syncedAt) / 1000;
  }
  return max(0, elapsed);
}

int currentCountdownRemaining() {
  int remaining = ticktick.countdownRemaining;
  if (timerRunning(ticktick.countdownState) && ticktick.syncedAt != 0) {
    remaining -= static_cast<uint32_t>(millis() - ticktick.syncedAt) / 1000;
  }
  return max(0, remaining);
}

String formatTimerSeconds(int seconds) {
  seconds = max(0, seconds);
  int hours = seconds / 3600;
  int minutes = (seconds % 3600) / 60;
  int remainder = seconds % 60;
  char buffer[16];
  if (hours > 0) {
    snprintf(buffer, sizeof(buffer), "%02d:%02d:%02d", hours, minutes, remainder);
  } else {
    snprintf(buffer, sizeof(buffer), "%02d:%02d", minutes, remainder);
  }
  return String(buffer);
}

String tickTickStatusCN() {
  if (!ticktick.connected) return "TickTick 未连接";
  if (timerRunning(ticktick.stopwatchState)) return "正计时进行中";
  if (timerPaused(ticktick.stopwatchState)) return "正计时已暂停";
  if (timerRunning(ticktick.countdownState)) return "25 分钟专注中";
  if (timerPaused(ticktick.countdownState)) return "倒计时已暂停";
  return "选择一种专注方式";
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

uint16_t tickTickColor() {
  if (!ticktick.connected) return rgb(105, 92, 104);
  if (timerPaused(ticktick.stopwatchState) || timerPaused(ticktick.countdownState)) {
    return rgb(255, 196, 0);
  }
  if (timerRunning(ticktick.stopwatchState) || timerRunning(ticktick.countdownState)) {
    return rgb(255, 59, 48);
  }
  return rgb(155, 148, 138);
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

void drawProviderBrandIcon(const uint16_t *pixels) {
  // The generated arrays store native RGB565 numeric values. M5GFX treats a
  // uint16_t source as byte-swapped when swapBytes is false, producing the
  // neon/noisy corruption confirmed on the physical device. Scope the swap
  // to this one blit and restore the canvas state for every later renderer.
  bool previousSwap = canvas.getSwapBytes();
  canvas.setSwapBytes(true);
  canvas.pushImage(kCenterIconX, kCenterIconY,
                   kCenterIconSize, kCenterIconSize,
                   pixels);
  canvas.setSwapBytes(previousSwap);
}

void drawCodexIcon(uint16_t background) {
  (void)background;
  drawProviderBrandIcon(codex_brand_icon_rgb565);
}

void drawClaudeIcon(uint16_t background) {
  (void)background;
  drawProviderBrandIcon(claude_brand_icon_rgb565);
}

void drawCompletionProviderIcon(bool claudeProvider, int8_t step) {
  const uint16_t *pixels = nullptr;
  int size = 0;
  switch (step) {
    case 0:
      pixels = claudeProvider ? claude_completion_icon_96_rgb565
                              : codex_completion_icon_96_rgb565;
      size = 96;
      break;
    case 1:
      pixels = claudeProvider ? claude_completion_icon_80_rgb565
                              : codex_completion_icon_80_rgb565;
      size = 80;
      break;
    case 2:
      pixels = claudeProvider ? claude_completion_icon_64_rgb565
                              : codex_completion_icon_64_rgb565;
      size = 64;
      break;
    case 3:
      pixels = claudeProvider ? claude_completion_icon_48_rgb565
                              : codex_completion_icon_48_rgb565;
      size = 48;
      break;
    case 4:
      pixels = claudeProvider ? claude_completion_icon_32_rgb565
                              : codex_completion_icon_32_rgb565;
      size = 32;
      break;
    default:
      return;
  }

  bool previousSwap = canvas.getSwapBytes();
  canvas.setSwapBytes(true);
  canvas.pushImage(kDashboardRingCenterX - size / 2,
                   kDashboardRingCenterY - size / 2,
                   size, size, pixels);
  canvas.setSwapBytes(previousSwap);
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

void fillAntialiasedCapsule(int x, int y, int width, int height,
                            uint16_t color) {
  canvas.fillSmoothRoundRect(x, y, width, height, height / 2, color);
}

void drawAntialiasedCapsule(int x, int y, int width, int height,
                            uint16_t fill, uint16_t border,
                            int borderWidth = 2) {
  fillAntialiasedCapsule(x, y, width, height, border);
  int inset = max(1, borderWidth);
  fillAntialiasedCapsule(x + inset, y + inset,
                         width - inset * 2, height - inset * 2, fill);
}

void drawStatusPill(const String &text, uint16_t dotColor, uint16_t fill, uint16_t border,
                    uint16_t foreground) {
  constexpr int x = 167;
  constexpr int y = 288;
  constexpr int width = 116;
  constexpr int height = 31;
  drawAntialiasedCapsule(x, y, width, height, fill, border, 1);
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
  drawAntialiasedCapsule(x, y, width, height, fill, border, 1);
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

void drawThickRoundedLine(int x0, int y0, int x1, int y1, int width,
                          uint16_t color) {
  float dx = static_cast<float>(x1 - x0);
  float dy = static_cast<float>(y1 - y0);
  float length = sqrtf(dx * dx + dy * dy);
  int radius = max(1, width / 2);
  if (length < 0.5f) {
    canvas.fillCircle(x0, y0, radius, color);
    return;
  }
  float px = -dy * radius / length;
  float py = dx * radius / length;
  int ax = static_cast<int>(lroundf(x0 + px));
  int ay = static_cast<int>(lroundf(y0 + py));
  int bx = static_cast<int>(lroundf(x0 - px));
  int by = static_cast<int>(lroundf(y0 - py));
  int cx = static_cast<int>(lroundf(x1 + px));
  int cy = static_cast<int>(lroundf(y1 + py));
  int dx2 = static_cast<int>(lroundf(x1 - px));
  int dy2 = static_cast<int>(lroundf(y1 - py));
  canvas.fillTriangle(ax, ay, bx, by, cx, cy, color);
  canvas.fillTriangle(bx, by, cx, cy, dx2, dy2, color);
  canvas.fillCircle(x0, y0, radius, color);
  canvas.fillCircle(x1, y1, radius, color);
}

void drawQuadraticThickRoundedLine(int x0, int y0,
                                   int controlX, int controlY,
                                   int x1, int y1,
                                   int width, uint16_t color) {
  int previousX = x0;
  int previousY = y0;
  for (int step = 1; step <= 16; ++step) {
    float t = step / 16.0f;
    float inverse = 1.0f - t;
    int currentX = static_cast<int>(lroundf(
        inverse * inverse * x0 + 2.0f * inverse * t * controlX + t * t * x1));
    int currentY = static_cast<int>(lroundf(
        inverse * inverse * y0 + 2.0f * inverse * t * controlY + t * t * y1));
    drawThickRoundedLine(previousX, previousY, currentX, currentY, width, color);
    previousX = currentX;
    previousY = currentY;
  }
}

void drawMicrophoneIcon(int left, int top, uint16_t color,
                        uint16_t background) {
  // Faithful raster translation of the approved 58 x 107 SVG microphone.
  canvas.fillRoundRect(left + 8, top, 42, 67, 21, color);
  canvas.fillRoundRect(left + 15, top + 7, 28, 53, 14, background);

  // The SVG cradle is two quadratic segments, not one shallow quadratic.
  // Both meet the stand at (29, 82), keeping the microphone visually joined.
  drawQuadraticThickRoundedLine(left, top + 42,
                                left, top + 82,
                                left + 29, top + 82, 7, color);
  drawQuadraticThickRoundedLine(left + 29, top + 82,
                                left + 58, top + 82,
                                left + 58, top + 42, 7, color);
  drawThickRoundedLine(left + 29, top + 82, left + 29, top + 103, 7, color);
  drawThickRoundedLine(left + 14, top + 104, left + 44, top + 104, 7, color);
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
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t coral = rgb(255, 107, 99);
  const uint16_t yellow = rgb(255, 196, 0);
  const uint16_t red = rgb(255, 76, 99);
  const uint16_t muted = rgb(106, 105, 101);
  DashboardTypelessMode availableMode = availableTypelessMode();
  DashboardTypelessMode displayMode =
      voiceSessionActive ? voiceSessionMode : availableMode;
  bool available = displayMode != DashboardTypelessMode::unavailable;
  bool usbMode = displayMode == DashboardTypelessMode::usbMic;
  bool macMode = displayMode == DashboardTypelessMode::macMic;
  bool usbMeterActive = usbMode && voiceCaptureActive;
  uint16_t accent = !available        ? muted
                    : voiceCaptureFailed ? red
                    : voiceSessionActive ? coral
                                         : yellow;

  int16_t waveform[kVoiceWaveformPoints];
  int levelPercent = 0;
  portENTER_CRITICAL(&voiceVisualMux);
  memcpy(waveform, voiceWaveform, sizeof(waveform));
  levelPercent = voiceLevelPercent;
  portEXIT_CRITICAL(&voiceVisualMux);
  if (!usbMeterActive) {
    memset(waveform, 0, sizeof(waveform));
    levelPercent = 0;
  }

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

  String modeLabel = usbMode ? "USB MIC"
                     : macMode ? "MAC MIC"
                               : "NO BRIDGE";
#if !defined(M5DASH_USB_AUDIO)
  if (displayMode == DashboardTypelessMode::usbMic) modeLabel = "USB 未启用";
#endif

  drawEditorialBackdrop(coral);
  // Keep the mode in the native 24 px header and the state in the native
  // 80 px hero. "USB MIC / READY" and "MAC MIC / READY" therefore share
  // exactly the same grid, weight and baseline instead of squeezing a long
  // mixed-size phrase into the hero line.
  drawEditorialHeader("Typeless", modeLabel, ink);
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(ink);
  useEditorialHero80();
  if (!available) {
    canvas.drawString("NO", 18, 170);
    canvas.drawString("BRIDGE", 18, 235);
  } else {
    canvas.drawString(voiceCaptureFailed ? "ERROR"
                      : voiceSessionActive ? "LIVE" : "READY",
                      18, 205);
  }
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(muted);
  useEditorialMicro14();
  if (usbMode) {
    canvas.drawString("48 KHZ · USB", 58, 260);
  } else if (macMode) {
    canvas.drawString("BUILT-IN · WI-FI", 58, 260);
  }

  drawMicrophoneIcon(325, 147, ink, coral);

  constexpr int waveLeft = 56;
  constexpr int waveRight = 394;
  constexpr int waveCenterY = 296;
  constexpr int waveHalfHeight = 22;
  canvas.drawFastHLine(waveLeft, waveCenterY, waveRight - waveLeft,
                       rgb(198, 194, 184));

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
                      usbMeterActive ? ink : muted);
      if (usbMeterActive) {
        canvas.drawLine(previousX, previousY + 1, currentX, currentY + 1,
                        rgb(112, 109, 102));
      }
    }
    previousX = currentX;
    previousY = currentY;
  }

  canvas.setTextDatum(middle_left);
  canvas.setTextColor(muted);
  useEditorialMicro14();
  canvas.drawString(usbMode ? "实时峰值" : macMode ? "输入来源" : "连接状态",
                    60, 328);
  canvas.setTextDatum(middle_right);
  canvas.setTextColor(ink);
  canvas.setFont(&fonts::Font2);
  canvas.setTextSize(1);
  canvas.drawString(usbMode ? String(peakDb) + " dBFS"
                    : macMode ? "MAC" : "--",
                    390, 328);

  fillAntialiasedCapsule(kEditorialFooterX, kEditorialFooterY,
                         kEditorialFooterWidth, kEditorialFooterHeight, ink);
  canvas.fillCircle(kEditorialFooterX + 28,
                    kEditorialFooterY + kEditorialFooterHeight / 2, 15, accent);
  if (voiceSessionActive) {
    canvas.fillRoundRect(kEditorialFooterX + 23, kEditorialFooterY + 21,
                         10, 10, 2, ink);
  } else {
    canvas.fillCircle(kEditorialFooterX + 28,
                      kEditorialFooterY + kEditorialFooterHeight / 2, 5, ink);
  }
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(background);
  useEditorialBold18();
  String hint = !available ? "NO BRIDGE"
                : voiceCaptureFailed ? "再按一次重试"
                : voiceSessionActive && usbMode ? "轻触结束手表听写"
                : voiceSessionActive && macMode ? "轻触结束电脑听写"
                : usbMode ? "轻触使用手表麦克风"
                          : "轻触使用电脑麦克风";
  canvas.drawString(hint, kEditorialFooterX + 137,
                    kEditorialFooterY + kEditorialFooterHeight / 2 + 1);
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
  canvas.drawString(task.contentVisible
                        ? String(task.messageCount) + " 条可见消息"
                        : "对话内容保持私密",
                    108, y + 45);
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
    canvas.drawString(task.contentVisible ? "正在等待第一条可见消息"
                                          : "任务正在运行 · 对话内容保持私密",
                      225, 220);
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

bool focusTaskActive() {
  return ticktick.connected &&
         (timerRunning(ticktick.stopwatchState) || timerPaused(ticktick.stopwatchState) ||
          timerRunning(ticktick.countdownState) || timerPaused(ticktick.countdownState));
}

size_t buildOrbitTasks(OrbitTaskItem (&items)[5]) {
  size_t count = 0;
  if (focusTaskActive() && count < 5) {
    items[count++] = {'F', -1, tickTickStatusCN()};
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
  if (provider == 'F') return rgb(255, 104, 115);
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
    if (items[index].provider != 'F') shortLabel += String(items[index].transcriptIndex + 1);
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

void updateObsidianDiceShake() {
  if (currentPage != 6 || overlayMode != OverlayMode::none ||
      obsidianDice.availableCount <= 0 || !M5.Imu.isEnabled()) {
    obsidianShakePreviousReady = false;
    return;
  }
  uint32_t now = millis();
  M5.Imu.update();
  float accelX = 0.0f;
  float accelY = 0.0f;
  float accelZ = 0.0f;
  if (!M5.Imu.getAccel(&accelX, &accelY, &accelZ)) return;
  float deltaX = accelX - obsidianShakePreviousX;
  float deltaY = accelY - obsidianShakePreviousY;
  float deltaZ = accelZ - obsidianShakePreviousZ;
  bool rolled = dashboardShakeDetected(obsidianShakePreviousReady,
                                       deltaX, deltaY, deltaZ, now,
                                       lastObsidianShakeAt, 900, 0.78f);
  obsidianShakePreviousX = accelX;
  obsidianShakePreviousY = accelY;
  obsidianShakePreviousZ = accelZ;
  obsidianShakePreviousReady = true;
  if (!rolled) return;
  lastObsidianShakeAt = now;
  performObsidianAction("roll");
}

size_t visibleDashboardResultCount() {
  return dashboardResults.count;
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
  if (count == 0) {
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
  if (selectedResult >= static_cast<int>(visibleCount)) selectedResult = -1;
  if (selectedResult >= 0) {
    const DashboardResult &item = visible[selectedResult];
    uint16_t accent = providerAccent(item.provider);
    canvas.fillRoundRect(72, 146, 306, 170, 34, rgb(30, 31, 37));
    canvas.fillCircle(225, 183, 10, accent);
    canvas.setTextColor(accent);
    useChinese16();
    canvas.drawString(item.provider == 'A' ? "Claude" : "Codex",
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
  // Full-screen overlays replace the editorial page. Do not let its accent
  // circle survive in the 8 px frame around the 450 px design canvas.
  if (overlayMode == OverlayMode::connection ||
      overlayMode == OverlayMode::wifiPicker ||
      overlayMode == OverlayMode::transcript ||
      overlayMode == OverlayMode::orbit ||
    overlayMode == OverlayMode::results) {
    editorialFrameAccentActive = false;
    editorialFrameBurstActive = false;
  }
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

  // This overlay replaces the entire provider/editorial frame. Clear any
  // outer-frame decoration left by the page rendered immediately before it;
  // otherwise the 8 px physical margin leaks paper or the previous accent
  // circle as four bright slivers around the round display.
  editorialFrameAccentActive = false;
  editorialFrameBurstActive = false;

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

  drawCompletionProviderIcon(claudeProvider, frame.providerIconStep);

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

void drawEditorialBackdrop(uint16_t accent) {
  editorialFrameAccentActive = true;
  editorialFrameAccent = accent;
  canvas.fillScreen(editorialPaperColor());
  canvas.fillSmoothCircle(364, 130, 164, accent);
}

void drawEditorialHeader(const String &primary, const String &secondary,
                         uint16_t ink) {
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(ink);
  useEditorialBold24();
  canvas.drawString(primary, kEditorialHeaderX, kEditorialHeaderFirstLineY);
  canvas.drawString(secondary, kEditorialHeaderX, kEditorialHeaderSecondLineY);
  canvas.fillRect(kEditorialHeaderX, kEditorialHeaderUnderlineY, 52, 4, ink);
}

void drawEditorialHero(const String &value, int x, int y, int maxWidth,
                       uint16_t ink, float maxScale = 1.34f) {
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(ink);
  useEditorialHero104();
  canvas.drawString(value, x, y);
}

void drawEditorialMetricPill(int x, const String &label, int64_t rawValue,
                             bool filled, uint16_t accent, uint16_t background,
                             uint16_t ink, uint16_t yellow) {
  constexpr int y = 282;
  constexpr int width = 175;
  constexpr int height = 50;
  uint16_t fill = filled ? ink : background;
  uint16_t labelColor = filled ? rgb(201, 199, 192) : rgb(106, 105, 101);
  uint16_t valueColor = filled ? background : ink;
  fillAntialiasedCapsule(x, y, width, height, fill);
  if (!filled) {
    drawAntialiasedCapsule(x, y, width, height, background, yellow);
  }
  canvas.fillCircle(x + 27, y + 25, 7, filled ? accent : yellow);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(labelColor);
  useEditorialMicro14();
  canvas.drawString(label, x + 103, y + 16);
  canvas.setTextColor(valueColor);
  String value = formatChineseCountNumber(rawValue);
  if (countUsesChineseHundredMillions(rawValue)) {
    value += "亿";
  }
  useEditorialBold18();
  canvas.drawString(value, x + 103, y + 34);
}

void drawClockShortcutDock() {
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t yellow = rgb(255, 196, 0);
  fillAntialiasedCapsule(kClockOrbitActionX, kClockActionY,
                         kClockActionWidth, kClockActionHeight, ink);
  drawAntialiasedCapsule(kClockResultsActionX, kClockActionY,
                         kClockActionWidth, kClockActionHeight,
                         background, yellow);

  constexpr int iconY = kClockActionY + kClockActionHeight / 2;
  constexpr int orbitX = kClockOrbitActionX + 24;
  canvas.fillCircle(orbitX, iconY, 14, background);
  canvas.drawLine(orbitX, iconY - 7, orbitX, iconY + 7, ink);
  canvas.drawLine(orbitX - 7, iconY, orbitX + 7, iconY, ink);
  canvas.drawLine(orbitX - 5, iconY - 5, orbitX + 5, iconY + 5, ink);
  canvas.drawLine(orbitX + 5, iconY - 5, orbitX - 5, iconY + 5, ink);

  constexpr int resultX = kClockResultsActionX + 24;
  canvas.fillCircle(resultX, iconY, 14, yellow);
  canvas.drawCircle(resultX, iconY, 6, ink);
  canvas.drawEllipse(resultX, iconY, 9, 4, ink);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(background);
  useEditorialBold18();
  canvas.drawString("星盘", kClockOrbitActionX + 78, iconY + 1);
  canvas.setTextColor(ink);
  canvas.drawString("成果", kClockResultsActionX + 78, iconY + 1);
}

void drawClockProgressCap(float angle, uint16_t color) {
  float radians = angle * PI / 180.0f;
  int x = 225 + static_cast<int>(
                    lroundf(cosf(radians) * kClockQuotaArcCenterRadius));
  int y = 225 + static_cast<int>(
                    lroundf(sinf(radians) * kClockQuotaArcCenterRadius));
  canvas.fillSmoothCircle(x, y, kClockQuotaArcCapRadius, color);
}

void drawClockProgressSegment(float startAngle, float endAngle, int percent,
                              bool fillFromEnd, uint16_t track,
                              uint16_t active) {
  canvas.fillArc(225, 225, kClockQuotaArcOuterRadius,
                 kClockQuotaArcInnerRadius, startAngle, endAngle, track);
  drawClockProgressCap(startAngle, track);
  drawClockProgressCap(endAngle, track);
  int safePercent = max(0, min(100, percent));
  if (safePercent <= 0) return;
  float activeStart = startAngle;
  float activeEnd = endAngle;
  float activeSweep = (endAngle - startAngle) * safePercent / 100.0f;
  if (fillFromEnd) {
    activeStart = endAngle - activeSweep;
  } else {
    activeEnd = startAngle + activeSweep;
  }
  canvas.fillArc(225, 225, kClockQuotaArcOuterRadius,
                 kClockQuotaArcInnerRadius, activeStart, activeEnd, active);
  drawClockProgressCap(activeStart, active);
  drawClockProgressCap(activeEnd, active);
}

void drawClockPage() {
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t mint = rgb(24, 229, 161);
  const uint16_t yellow = rgb(255, 196, 0);
  const uint16_t codexTrack = rgb(200, 203, 255);
  const uint16_t claudeTrack = rgb(243, 198, 181);
  const uint16_t codexBlue = rgb(95, 103, 255);
  const uint16_t claudeOrange = rgb(226, 122, 86);
  drawEditorialBackdrop(mint);
  int codexWeekUsed = max(0, min(100, codex.weekUsedPercent));
  int claudeWeekUsed = max(0, min(100, claude.weekUsedPercent));
  // Deep provider color means consumed quota and grows outward from 6 o'clock.
  drawClockProgressSegment(95.0f, 162.7f, codexWeekUsed, false,
                           codexTrack, codexBlue);
  drawClockProgressSegment(17.3f, 85.0f, claudeWeekUsed, true,
                           claudeTrack, claudeOrange);
  drawEditorialHeader("时钟", "总览", ink);

  int focusMinutes = max(0, ticktick.todayFocusSeconds / 60);
  struct tm local = {};
  bool timeReady = clockLocalTime(local);
  String timeText = "--:--";
  if (timeReady) {
    char buffer[8];
    snprintf(buffer, sizeof(buffer), "%02d:%02d", local.tm_hour, local.tm_min);
    timeText = String(buffer);
  }
  drawEditorialHero(timeText, 26, 205, 394, ink, 1.28f);
  if (timeReady) {
    drawClockSecondValue(canvas, 0, 0, local.tm_sec, mint, ink);
    lastClockDrawSecond = local.tm_sec;
    lastClockDrawMinute = local.tm_hour * 60 + local.tm_min;
  } else {
    lastClockDrawSecond = -1;
    lastClockDrawMinute = -1;
  }
  drawBatteryStatusAt(mint, ink, 326, 76, false);

  String weatherText = weather.available
                           ? weather.label + " · " + String(weather.temperatureC, 0) + "℃"
                           : "天气暂不可用 · --℃";
  String date;
  if (timeReady) {
    static const char *weekdays[] = {"日", "一", "二", "三", "四", "五", "六"};
    date = "周" + String(weekdays[local.tm_wday]) + " · " +
           String(local.tm_mon + 1) + "月" + String(local.tm_mday) + "日";
  } else {
    date = "等待校时";
  }

  canvas.setTextColor(ink);
  useEditorialBold18();
  canvas.setTextDatum(middle_left);
  canvas.drawString(date, 58, 260);

  fillAntialiasedCapsule(58, 282, 143, 42, ink);
  canvas.fillCircle(81, 303, 7, yellow);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(background);
  useEditorialMicro14();
  canvas.drawString(weatherText, 135, 303);

  drawAntialiasedCapsule(213, 282, 179, 42, background, yellow);
  canvas.fillCircle(236, 303, 7, mint);
  canvas.setTextColor(ink);
  useEditorialMicro14();
  String usageText = "--";
  bool usageUsesHundredMillions = false;
  if (aiUsage.connected && aiUsage.complete) {
    usageUsesHundredMillions =
        countUsesChineseHundredMillions(aiUsage.todayTotalTokens);
    usageText = String(aiUsage.approximate ? "~" : "") +
                formatChineseCountNumber(aiUsage.todayTotalTokens);
  }
  String focusText = "专" + String(focusMinutes) + "m · AI " + usageText;
  if (usageUsesHundredMillions) {
    focusText += "亿";
  }
  useEditorialMicro14();
  canvas.drawString(focusText, 311, 303);
  drawClockShortcutDock();
}

void drawClockSecondOnly(const struct tm &local) {
  if (!clockSecondCanvasReady) {
    drawCurrentPage();
    return;
  }
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t mint = rgb(24, 229, 161);
  drawClockSecondValue(clockSecondCanvas, kClockSecondPatchX, kClockSecondPatchY,
                       local.tm_sec, mint, ink);
  int frameOffset = designFrameOffset();
  M5.Display.startWrite();
  clockSecondCanvas.pushSprite(
      displayFrameOffsetX() + frameOffset + kClockSecondPatchX,
      displayFrameOffsetY() + frameOffset + kClockSecondPatchY);
  M5.Display.endWrite();
  lastClockDrawSecond = local.tm_sec;
  lastClockDrawMinute = local.tm_hour * 60 + local.tm_min;
}

void drawFocusHeroTime(const String &value, uint16_t ink) {
  String primary = value;
  String seconds;
  if (value.length() > 5) {
    int split = value.lastIndexOf(':');
    if (split > 0) {
      primary = value.substring(0, split);
      seconds = value.substring(split + 1);
    }
  }

  canvas.setTextColor(ink);
  canvas.setTextDatum(middle_left);
  useEditorialHero104();
  canvas.drawString(primary, 28, 205);

  if (seconds.length() > 0) {
    canvas.setTextDatum(middle_center);
    useEditorialBold24();
    canvas.drawString(seconds, 382, 225);
    canvas.fillRect(359, 250, 46, 5, ink);
  }
}

void drawFocusModeOption(int x, int width, const String &key, const String &label,
                         bool selected, uint16_t background, uint16_t ink,
                         uint16_t yellow) {
  if (selected) {
    fillAntialiasedCapsule(x, 282, width, 50, ink);
  } else {
    drawAntialiasedCapsule(x, 282, width, 50, background, yellow);
  }

  const uint16_t keyFill = selected ? background : yellow;
  const uint16_t textColor = selected ? background : ink;
  canvas.fillCircle(x + 27, 307, 16, keyFill);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(ink);
  useEditorialBold18();
  canvas.drawString(key, x + 27, 307);
  canvas.setTextColor(textColor);
  useEditorialBold18();
  canvas.drawString(label, x + width / 2 + 16, 307);
}

void drawFocusActions(const String &key, bool running, bool paused,
                      uint16_t background, uint16_t ink) {
  String action = running ? "暂停" : paused ? "继续" : "开始";
  const int actionCenterY = kFocusActionY + kFocusActionHeight / 2;
  const int primaryKeyX = kFocusPrimaryActionX + 26;
  const int primaryLabelX = kFocusPrimaryActionX + 108;
  const int endCenterX = kFocusEndActionX + kFocusEndActionWidth / 2;

  fillAntialiasedCapsule(kFocusPrimaryActionX, kFocusActionY,
                         kFocusPrimaryActionWidth, kFocusActionHeight, ink);
  canvas.fillCircle(primaryKeyX, actionCenterY, 15, background);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(ink);
  useEditorialBold18();
  canvas.drawString(key, primaryKeyX, actionCenterY);
  canvas.setTextColor(background);
  useEditorialBold24();
  canvas.drawString(action, primaryLabelX, actionCenterY);

  drawAntialiasedCapsule(kFocusEndActionX, kFocusActionY,
                         kFocusEndActionWidth, kFocusActionHeight,
                         background, ink);
  canvas.setTextColor(ink);
  useEditorialMicro14();
  canvas.drawString("结束", endCenterX, actionCenterY);
}

bool focusUsesStopwatchMode() {
  bool stopwatchActive = timerRunning(ticktick.stopwatchState) ||
                         timerPaused(ticktick.stopwatchState);
  bool countdownActive = timerRunning(ticktick.countdownState) ||
                         timerPaused(ticktick.countdownState);
  return stopwatchActive || !countdownActive;
}

void drawFocusPage() {
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t coral = rgb(255, 59, 48);
  const uint16_t yellow = rgb(255, 196, 0);
  bool stopwatchMode = focusUsesStopwatchMode();
  bool running = stopwatchMode ? timerRunning(ticktick.stopwatchState)
                               : timerRunning(ticktick.countdownState);
  bool paused = stopwatchMode ? timerPaused(ticktick.stopwatchState)
                              : timerPaused(ticktick.countdownState);
  String heroValue = stopwatchMode ? formatTimerSeconds(currentStopwatchElapsed())
                                   : formatTimerSeconds(currentCountdownRemaining());

  drawEditorialBackdrop(coral);

  canvas.setTextDatum(middle_left);
  canvas.setTextColor(ink);
  useEditorialBold24();
  canvas.drawString(ticktick.connected ? "专注" : "等待", kFocusStatusX,
                    kFocusStatusFirstLineY);
  canvas.drawString(!ticktick.connected ? "连接" : running ? "进行中" : paused ? "已暂停"
                                                                       : "准备好",
                    kFocusStatusX, kFocusStatusSecondLineY);
  canvas.fillRect(kFocusStatusX, kFocusStatusUnderlineY, 52, 4, ink);

  drawFocusHeroTime(heroValue, ink);
  drawFocusModeOption(52, 175, "A", "正计时", stopwatchMode, background, ink, yellow);
  drawFocusModeOption(225, 175, "B", "25分钟", !stopwatchMode, background, ink, yellow);
  drawFocusActions(stopwatchMode ? "A" : "B", running, paused, background, ink);
}

String providerEditorialStatus(const CodexData &provider) {
  if (!provider.connected) return "离线";
  if (provider.waiting > 0) return "等待确认";
  if (provider.active > 0) return "正在工作";
  if (provider.errors > 0) return "需要检查";
  return "当前空闲";
}

void drawProviderQuotaHero(int remainingPercent, uint16_t ink) {
  canvas.setTextDatum(middle_left);
  canvas.setTextColor(ink);
  useEditorialHero104();
  if (remainingPercent < 0) {
    canvas.drawString("--", 28, 205);
    return;
  }

  // M5GFX's VLW renderer allocates one complete glyph bitmap on the loop-task
  // stack. Noto Bold 104's percent glyph is 100 x 79 (7,900 bytes), which the
  // device core dump proved can overflow that stack. Keep the native 104 px
  // digits, then draw a separately embedded 96 px RGBA glyph. It is nearly as
  // tall as the digits, retains true antialiasing across both page colours,
  // and bypasses the VLW stack allocation that caused the provider reboot.
  String digits(remainingPercent);
  canvas.drawString(digits, 28, 205);
  int markLeft = 28 + canvas.textWidth(digits) + 3;
  int markTop = 205 - static_cast<int>(provider_percent_96_png_height) / 2;
  canvas.drawPng(provider_percent_96_png, provider_percent_96_png_len,
                 markLeft, markTop,
                 provider_percent_96_png_width, provider_percent_96_png_height,
                 0, 0, 1.0f, 1.0f, datum_t::top_left);
}

void drawProviderResetArrow(int centerX, int centerY, uint16_t color) {
  // Draw the reset mark as geometry. Noto CJK maps U+21BA to its .notdef
  // placeholder on this device, even though the codepoint exists in the VLW.
  canvas.fillArc(centerX, centerY, 7, 5, 38, 320, color);
  canvas.fillTriangle(centerX - 8, centerY - 5,
                      centerX - 2, centerY - 7,
                      centerX - 3, centerY - 1, color);
}

void drawProviderEditorialFooter(const CodexData &provider, int resetMinutes,
                                 uint16_t accent,
                                 uint16_t background, uint16_t ink) {
  fillAntialiasedCapsule(kEditorialFooterX, kEditorialFooterY,
                         kEditorialFooterWidth, kEditorialFooterHeight, ink);
  canvas.fillCircle(kEditorialFooterX + 28,
                    kEditorialFooterY + kEditorialFooterHeight / 2, 7, accent);

  String firstLine;
  String secondLine;
  bool showResetArrow = false;
  if (provider.active > 0) {
    firstLine = String(provider.active) + " 个活动任务";
    secondLine = "轻触图标查看详情";
  } else if (provider.waiting > 0) {
    firstLine = String(provider.waiting) + " 个任务等待确认";
    secondLine = "请在电脑端继续";
  } else if (provider.errors > 0) {
    firstLine = "发现异常状态";
    secondLine = "请在电脑端检查";
  } else {
    if (resetMinutes >= 0) {
      firstLine = formatDurationCompact(resetMinutes);
      showResetArrow = true;
    } else {
      firstLine = "重置待同步";
    }
    secondLine = "暂无活动任务";
  }

  canvas.setTextDatum(middle_center);
  uint16_t muted = rgb(201, 199, 192);
  canvas.setTextColor(muted);
  useEditorialMicro14();
  int firstLineCenterX = kEditorialFooterX + 129;
  int firstLineCenterY = kEditorialFooterY + 17;
  if (showResetArrow) {
    int textWidth = canvas.textWidth(firstLine);
    constexpr int iconWidth = 16;
    constexpr int iconGap = 4;
    int groupWidth = iconWidth + iconGap + textWidth;
    int groupLeft = firstLineCenterX - groupWidth / 2;
    drawProviderResetArrow(groupLeft + iconWidth / 2, firstLineCenterY, muted);
    canvas.drawString(firstLine,
                      groupLeft + iconWidth + iconGap + textWidth / 2,
                      firstLineCenterY);
  } else {
    canvas.drawString(firstLine, firstLineCenterX, firstLineCenterY);
  }
  canvas.setTextColor(background);
  useEditorialBold18();
  canvas.drawString(secondLine, kEditorialFooterX + 129, kEditorialFooterY + 37);
}

void drawProviderEditorialPage(CodexData &provider, bool claudeProvider) {
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t yellow = rgb(255, 196, 0);
  const uint16_t accent = claudeProvider ? rgb(226, 122, 86) : rgb(95, 103, 255);
  bool showWeek = claudeProvider || provider.weekUsedPercent >= 0;
  int mainUsedPercent = showWeek ? provider.weekUsedPercent : provider.shortUsedPercent;
  int mainPercent = dashboardRemainingPercent(mainUsedPercent);
  int mainReset = showWeek ? provider.weekResetInMin : provider.shortResetInMin;
  String mainLabel = showWeek ? "本周剩余额度" : "五小时剩余额度";

  markRenderDiagnostic(201, currentPage);
  drawEditorialBackdrop(accent);
  markRenderDiagnostic(202, currentPage);
  drawEditorialHeader(claudeProvider ? "Claude" : "Codex",
                      providerEditorialStatus(provider), ink);
  markRenderDiagnostic(203, currentPage);
  drawProviderQuotaHero(mainPercent, ink);
  markRenderDiagnostic(204, currentPage);

  canvas.setTextDatum(middle_left);
  canvas.setTextColor(rgb(93, 92, 89));
  useEditorialMicro14();
  canvas.drawString(mainLabel, 58, 260);

  if (claudeProvider) {
    drawClaudeIcon(accent);
  } else {
    drawCodexIcon(accent);
  }
  markRenderDiagnostic(205, currentPage);

  drawEditorialMetricPill(52, "今日用量", provider.todayTokens,
                          true, accent, background, ink, yellow);
  drawEditorialMetricPill(225, "累计", provider.lifetimeTokens,
                          false, accent, background, ink, yellow);
  markRenderDiagnostic(206, currentPage);
  drawProviderEditorialFooter(provider, mainReset, accent,
                              background, ink);
  markRenderDiagnostic(207, currentPage);
}

void drawRegressionSafeProviderIcon(bool claudeProvider, uint16_t background) {
  if (claudeProvider) {
    canvas.drawPng(claude_icon_png, claude_icon_png_len,
                   177, 170, 96, 96,
                   0, 0, 1.0f, 1.0f, datum_t::top_left);
  } else {
    canvas.drawPng(codex_icon_png, codex_icon_png_len,
                   177, 170, 96, 96,
                   0, 0, 1.0f, 1.0f, datum_t::top_left);
  }
  maskRoundedImageCorners(177, 170, 96, 96, 22, background);
}

void drawRegressionSafeProviderPage(CodexData &provider, bool claudeProvider) {
  const uint16_t background = claudeProvider ? rgb(15, 11, 9) : rgb(7, 8, 17);
  const uint16_t foreground = claudeProvider ? rgb(250, 249, 245) : rgb(243, 243, 248);
  const uint16_t muted = claudeProvider ? rgb(176, 174, 165) : rgb(142, 145, 160);
  const uint16_t track = claudeProvider ? rgb(54, 42, 37) : rgb(34, 37, 57);
  const uint16_t active = claudeProvider ? rgb(217, 119, 87) : rgb(95, 103, 255);
  const uint16_t metricLine = claudeProvider ? rgb(71, 52, 44) : 0;

  bool showWeek = claudeProvider || provider.weekUsedPercent >= 0;
  int mainUsedPercent = showWeek ? provider.weekUsedPercent : provider.shortUsedPercent;
  int mainPercent = dashboardRemainingPercent(mainUsedPercent);
  int mainReset = showWeek ? provider.weekResetInMin : provider.shortResetInMin;

  drawRoundScreenBase(background, track, mainPercent, active);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(claudeProvider ? rgb(185, 173, 167) : rgb(163, 166, 188));
  useChinese16();
  canvas.drawString(showWeek ? "本周额度" : "五小时额度", 225, 48);

  canvas.setTextColor(foreground);
  useNumberFont();
  canvas.drawString(mainPercent >= 0 ? String(mainPercent) + "%" : "--", 225, 78);
  drawBatteryStatus(background, muted);

  drawMetric("活动任务", String(provider.active), 104, 136, 169, 78, 130,
             muted, foreground, false, metricLine);
  drawMetric("等待确认", String(provider.waiting), 346, 136, 169, 320, 372,
             muted, foreground, false, metricLine);
  drawMetric("今日用量", formatChineseCount(provider.todayTokens), 112, 267, 301,
             81, 143, muted, foreground,
             countUsesChineseHundredMillions(provider.todayTokens), metricLine);
  if (!claudeProvider && showWeek && provider.shortUsedPercent >= 0) {
    drawMetric("五时剩余",
               String(dashboardRemainingPercent(provider.shortUsedPercent)) + "%",
               338, 267, 301, 312, 364, muted, foreground, false, metricLine);
  } else {
    drawMetric("累计", formatLifetimeUsage(provider.lifetimeTokens),
               338, 267, 301, 312, 364, muted, foreground, true, metricLine);
  }

  drawRegressionSafeProviderIcon(claudeProvider, background);
  drawStatusPill(claudeProvider ? claudeStatusCN() : codexStatusCN(),
                 claudeProvider ? claudeStatusColor() : codexStatusColor(),
                 claudeProvider ? rgb(40, 31, 27) : rgb(22, 24, 39),
                 claudeProvider ? rgb(105, 64, 51) : rgb(66, 70, 96),
                 claudeProvider ? rgb(241, 234, 230) : rgb(224, 225, 241));
  drawFooterPill(showWeek ? "周额重置" : "额度重置", formatDurationCN(mainReset),
                 claudeProvider ? rgb(33, 27, 24) : rgb(22, 23, 29),
                 claudeProvider ? rgb(75, 57, 49) : rgb(58, 60, 67),
                 muted, foreground);
  drawPageIndicator(active, claudeProvider ? rgb(81, 68, 62) : rgb(66, 69, 88));
}

void drawCodexPage() {
  if (kProviderRegressionSafeRenderer) {
    drawRegressionSafeProviderPage(codex, false);
    return;
  }
  drawProviderEditorialPage(codex, false);
}

void drawClaudePage() {
  if (kProviderRegressionSafeRenderer) {
    drawRegressionSafeProviderPage(claude, true);
    return;
  }
  drawProviderEditorialPage(claude, true);
}

void drawFeatureActionRow(const String &primaryLabel, const String &secondaryLabel,
                          bool primaryEnabled, uint16_t accent,
                          uint16_t background, uint16_t ink) {
  uint16_t primaryFill = primaryEnabled ? ink : rgb(174, 171, 164);
  uint16_t primaryText = primaryEnabled ? background : rgb(227, 223, 214);
  fillAntialiasedCapsule(kFeaturePrimaryActionX, kFeatureActionY,
                         kFeaturePrimaryActionWidth, kFeatureActionHeight,
                         primaryFill);
  canvas.fillCircle(kFeaturePrimaryActionX + 27,
                    kFeatureActionY + kFeatureActionHeight / 2, 9, accent);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(primaryText);
  useEditorialBold18();
  canvas.drawString(primaryLabel, kFeaturePrimaryActionX + 101,
                    kFeatureActionY + kFeatureActionHeight / 2 + 1);

  drawAntialiasedCapsule(kFeatureSecondaryActionX, kFeatureActionY,
                         kFeatureSecondaryActionWidth, kFeatureActionHeight,
                         background, ink);
  canvas.setTextColor(ink);
  useEditorialMicro14();
  canvas.drawString(secondaryLabel,
                    kFeatureSecondaryActionX + kFeatureSecondaryActionWidth / 2,
                    kFeatureActionY + kFeatureActionHeight / 2 + 1);
}

void drawVibrationIcon(int x, int y, uint16_t color) {
  canvas.drawRoundRect(x - 7, y - 12, 14, 24, 4, color);
  canvas.drawFastHLine(x - 3, y + 8, 6, color);
  canvas.drawLine(x - 12, y - 7, x - 15, y - 3, color);
  canvas.drawLine(x - 15, y + 3, x - 12, y + 7, color);
  canvas.drawLine(x + 12, y - 7, x + 15, y - 3, color);
  canvas.drawLine(x + 15, y + 3, x + 12, y + 7, color);
}

void drawAIHotspotBurst(M5Canvas &target, int frameOffset) {
  constexpr int sourceSize = 220;
  constexpr int outputSize = 360;
  constexpr int outputX = 130;
  constexpr int outputY = -35;
  if (aiHotspotBurstCanvasReady) {
    constexpr float zoom = static_cast<float>(outputSize) / sourceSize;
    aiHotspotBurstCanvas.pushRotateZoomWithAA(
        &target,
        outputX + outputSize / 2 + frameOffset,
        outputY + outputSize / 2 + frameOffset,
        0.0f, zoom, zoom);
    return;
  }
  target.drawPng(ai_hotspot_burst_png, ai_hotspot_burst_png_len,
                 outputX + frameOffset, outputY + frameOffset,
                 outputSize, outputSize, 0, 0, 1.0f, 1.0f,
                 datum_t::top_left);
}

void drawAIHotspotPage() {
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t coral = rgb(255, 75, 67);
  const uint16_t muted = rgb(98, 96, 91);
  editorialFrameBurstActive = true;
  canvas.fillScreen(background);
  drawAIHotspotBurst(canvas, 0);
  drawEditorialHeader("AI 热点", aiHotspot.active ? "尖叫" : "监听中", ink);

  if (aiHotspot.active) {
    canvas.setTextDatum(middle_left);
    canvas.setTextColor(ink);
    useChinese24();
    canvas.setTextSize(1.2f);
    String lines[2];
    transcriptTextLines(aiHotspot.title.length() > 0 ? aiHotspot.title : "发现新的 AI 热点",
                        330, lines);
    canvas.drawString(lines[0], 58, 188);
    if (lines[1].length() > 0) canvas.drawString(lines[1], 58, 228);
    canvas.setTextSize(1);

    canvas.setTextColor(muted);
    useChinese16();
    canvas.drawString((aiHotspot.source.length() > 0 ? aiHotspot.source : "AI") +
                          " · 刚刚",
                      60, 267);

    canvas.fillCircle(95, 307, 22, ink);
    drawSpeakerIcon(95, 307, background);
    canvas.fillCircle(235, 307, 22, ink);
    drawVibrationIcon(235, 307, background);
    canvas.setTextColor(ink);
    useEditorialMicro14();
    canvas.drawString(notificationMuted ? "静音" : "声音", 121, 307);
    canvas.drawString("震动", 261, 307);
    drawFeatureActionRow("知道了", "打开", true, coral, background, ink);
    return;
  }

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(ink);
  useChinese24();
  canvas.drawString("暂无新热点", 225, 226);
  canvas.setTextColor(muted);
  useChinese16();
  canvas.drawString(aiHotspot.connected ? "官方信息源正在监听" : "等待热点信息源",
                    225, 268);
  drawFeatureActionRow("继续监听", "打开", false, coral, background, ink);
}

void drawObsidianDicePage() {
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t yellow = rgb(255, 196, 0);
  const uint16_t muted = rgb(98, 96, 91);
  bool hasSelection = obsidianDice.title.length() > 0;
  drawEditorialBackdrop(yellow);
  canvas.drawPng(obsidian_dice_png, obsidian_dice_png_len,
                 252, 82, 150, 150, 0, 0, 1.0f, 1.0f, datum_t::top_left);
  drawEditorialHeader("幸运笔记", hasSelection ? "摇骰结果" : "准备摇骰", ink);

  canvas.setTextDatum(middle_left);
  canvas.setTextColor(ink);
  // The native 80 px face includes both READY/LIVE and 0-9. Never scale the
  // 104 px quota font here: fractional VLW scaling drops pixel rows on-device.
  useEditorialHero80();
  canvas.drawString(String(obsidianDice.availableCount), 55, 202);
  canvas.setTextColor(muted);
  useEditorialMicro14();
  canvas.drawString("篇可抽", 58, 250);

  canvas.setTextColor(ink);
  useChinese24();
  String lines[2];
  transcriptTextLines(hasSelection ? obsidianDice.title : "摇一篇文档", 332, lines);
  canvas.drawString(lines[0], 58, 280);
  if (lines[1].length() > 0) canvas.drawString(lines[1], 58, 308);
  canvas.setTextColor(muted);
  useEditorialMicro14();
  String folder = hasSelection ? obsidianDice.folder : "Smart Workspace · 抬腕摇一摇";
  canvas.drawString(fitTextToWidth(folder, 320), 58, 331);
  drawFeatureActionRow(hasSelection ? "打开文档" : "摇一摇", "再摇",
                       obsidianDice.availableCount > 0, yellow, background, ink);
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

String formatLocalStopwatchTime(uint64_t elapsedMs) {
  uint64_t hundredths = (elapsedMs / 10) % 100;
  uint64_t totalSeconds = elapsedMs / 1000;
  uint64_t seconds = totalSeconds % 60;
  uint64_t minutes = (totalSeconds / 60) % 60;
  uint64_t hours = totalSeconds / 3600;
  char buffer[28];
  snprintf(buffer, sizeof(buffer), "%02llu:%02llu:%02llu.%02llu",
           static_cast<unsigned long long>(hours),
           static_cast<unsigned long long>(minutes),
           static_cast<unsigned long long>(seconds),
           static_cast<unsigned long long>(hundredths));
  return String(buffer);
}

void drawLocalStopwatchTimeText(M5Canvas &target, int centerX, int baselineY) {
  target.setTextDatum(baseline_center);
  target.setTextColor(rgb(216, 242, 255));
  if (stopwatchDigitFontReady) {
    target.setFont(&stopwatchDigitFont);
  } else {
    target.setFont(&fonts::DejaVu56);
  }
  target.setTextSize(1);
  target.drawString(
      formatLocalStopwatchTime(localStopwatchElapsedMs(localStopwatch, millis())),
      centerX, baselineY);
}

void drawLocalStopwatchTimeOnly() {
  if (!stopwatchTimeCanvasReady) {
    drawCurrentPage();
    return;
  }
  stopwatchTimeCanvas.fillSprite(rgb(65, 72, 75));
  drawLocalStopwatchTimeText(stopwatchTimeCanvas, kStopwatchTimeWidth / 2,
                             kStopwatchTimeBaselineY - kStopwatchTimeY);
  int frameOffset = designFrameOffset();
  M5.Display.startWrite();
  stopwatchTimeCanvas.pushSprite(displayFrameOffsetX() + frameOffset + kStopwatchTimeX,
                                 displayFrameOffsetY() + frameOffset + kStopwatchTimeY);
  M5.Display.endWrite();
}

void drawLauncherIcon(bool dashboardIcon, int centerX, int centerY,
                      uint16_t color, uint16_t surface) {
  if (dashboardIcon) {
    constexpr int size = 23;
    constexpr int gap = 10;
    for (int row = 0; row < 2; ++row) {
      for (int column = 0; column < 2; ++column) {
        int x = centerX + (column == 0 ? -size - gap / 2 : gap / 2);
        int y = centerY + (row == 0 ? -size - gap / 2 : gap / 2);
        canvas.fillRoundRect(x, y, size, size, 7, color);
      }
    }
    return;
  }
  canvas.drawCircle(centerX, centerY, 34, color);
  canvas.drawCircle(centerX, centerY, 33, color);
  canvas.drawLine(centerX, centerY, centerX, centerY - 20, color);
  canvas.drawLine(centerX, centerY, centerX + 17, centerY + 10, color);
  canvas.fillCircle(centerX, centerY, 4, surface);
  canvas.fillCircle(centerX, centerY, 2, color);
}

void drawAppLauncherPage() {
  const uint16_t background = editorialPaperColor();
  const uint16_t ink = rgb(5, 5, 5);
  const uint16_t coral = rgb(255, 59, 48);
  const uint16_t yellow = rgb(255, 196, 0);
  const uint16_t muted = rgb(106, 105, 101);
  canvas.fillScreen(background);
  canvas.fillCircle(366, 84, 126, coral);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(ink);
  useChinese24();
  canvas.drawString("选择程序", 225, 78);

  constexpr int centers[] = {137, 313};
  for (int index = 0; index < 2; ++index) {
    bool selected = launcherSelection == index;
    uint16_t surface = selected ? ink : background;
    uint16_t accent = index == 0 ? coral : yellow;
    canvas.fillCircle(centers[index], 222, 74, surface);
    canvas.drawCircle(centers[index], 222, 74, accent);
    canvas.drawCircle(centers[index], 222, 72, accent);
    if (selected) canvas.drawCircle(centers[index], 222, 78, ink);
    drawLauncherIcon(index == 0, centers[index], 212,
                     selected ? background : ink, surface);

    canvas.fillCircle(centers[index] - 45, 166, 14, accent);
    canvas.setTextColor(ink);
    useNumberFont();
    canvas.setTextSize(0.82f);
    canvas.drawString(index == 0 ? "A" : "B", centers[index] - 45, 166);
    canvas.setTextSize(1);

    canvas.setTextColor(selected ? background : ink);
    canvas.setTextSize(0.82f);
    canvas.drawString(index == 0 ? "DASHBOARD" : "STOPWATCH",
                      centers[index], 278);
    canvas.setTextSize(1);
  }

  canvas.setTextColor(muted);
  useChinese16();
  canvas.setTextSize(0.86f);
  canvas.drawString("A / B 选择 · 轻触进入", 225, 374);
  canvas.setTextSize(1);
}

void drawLocalStopwatchPage() {
  const uint16_t background = rgb(0, 0, 0);
  const uint16_t panel = rgb(65, 72, 75);
  const uint16_t divider = rgb(88, 100, 106);
  const uint16_t elapsedColor = rgb(216, 242, 255);
  const uint16_t leftColor = rgb(179, 205, 255);
  const uint16_t rightColor = localStopwatch.state == LocalStopwatchState::running
                                  ? rgb(255, 158, 171)
                                  : rgb(156, 241, 182);
  const uint16_t buttonInk = rgb(20, 24, 27);
  const uint16_t muted = rgb(115, 128, 134);
  canvas.fillScreen(background);

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(205, 235, 249));
  canvas.setFont(&fonts::FreeSansBold12pt7b);
  canvas.setTextSize(1);
  canvas.drawString("STOPWATCH", 225, 24);

  canvas.fillSmoothRoundRect(98, 54, 105, 72, 34, leftColor);
  canvas.fillSmoothRoundRect(247, 54, 105, 72, 34, rightColor);
  canvas.setTextColor(buttonInk);
  canvas.setFont(&fonts::FreeSansBold12pt7b);
  canvas.setTextSize(1);
  canvas.drawString(localStopwatchLeftLabel(localStopwatch.state), 150, 90);
  canvas.drawString(localStopwatchRightLabel(localStopwatch.state), 299, 90);

  canvas.fillSmoothRoundRect(0, 148, 450, 302, 58, panel);
  drawLocalStopwatchTimeText(canvas, 225, kStopwatchTimeBaselineY);
  canvas.fillSmoothRoundRect(145, 246, 160, 4, 2, divider);

  if (localStopwatch.lapCount == 0) {
    canvas.setTextColor(muted);
    canvas.setFont(&fonts::DejaVu24);
    canvas.setTextSize(1);
    canvas.drawString("-.-", 225, 310);
  } else {
    std::size_t visible = localStopwatch.lapCount > kLocalStopwatchVisibleLaps
                              ? kLocalStopwatchVisibleLaps
                              : localStopwatch.lapCount;
    std::size_t maximumOffset =
        localStopwatchMaximumLapOffset(localStopwatch.lapCount);
    if (localStopwatchLapOffset > maximumOffset) {
      localStopwatchLapOffset = maximumOffset;
    }
    std::size_t first = localStopwatchFirstVisibleLap(
        localStopwatch.lapCount, localStopwatchLapOffset);
    for (std::size_t row = 0; row < visible; ++row) {
      std::size_t lapIndex = first + row;
      int y = 280 + static_cast<int>(row) * 42;
      canvas.setTextColor(elapsedColor);
      canvas.setFont(&fonts::DejaVu18);
      canvas.setTextSize(1);
      canvas.setTextDatum(middle_left);
      canvas.drawString("LAP " + String(static_cast<unsigned int>(lapIndex + 1)), 68, y);
      canvas.setTextDatum(middle_right);
      canvas.drawString(formatLocalStopwatchTime(localStopwatch.laps[lapIndex]), 382, y);
    }
  }

  canvas.setTextDatum(middle_center);
  canvas.setTextColor(rgb(171, 181, 186));
  useChinese16();
  // Keep the VLW bitmap at native scale. Fractional downscaling drops source
  // pixel rows in M5GFX and visibly trims the footer's lower strokes.
  canvas.setTextSize(1);
  String footer = "双击电源键返回";
  std::size_t maximumLapOffset =
      localStopwatchMaximumLapOffset(localStopwatch.lapCount);
  if (maximumLapOffset > 0) {
    footer = localStopwatchLapOffset == 0
                 ? "上滑回看 · 双击电源键"
                 : localStopwatchLapOffset >= maximumLapOffset
                       ? "下滑返回最新 · 双击电源键"
                       : "上下滑浏览 · 双击电源键";
  }
  canvas.drawString(footer, 225, kStopwatchFooterY);
}

void renderCurrentPage(uint32_t now, uint16_t background) {
  editorialFrameAccentActive = false;
  editorialFrameBurstActive = false;
  if (appMode == DashboardAppMode::launcher) {
    drawAppLauncherPage();
    composeRenderedFrame(background);
    return;
  }
  if (appMode == DashboardAppMode::stopwatch) {
    drawLocalStopwatchPage();
    composeRenderedFrame(background);
    return;
  }
  markRenderDiagnostic(120, currentPage);
  if (!haveData) {
    drawConnectingPage();
  } else if (currentPage == 0) {
    drawClockPage();
  } else if (currentPage == 1) {
    drawFocusPage();
  } else if (currentPage == 2) {
    drawCodexPage();
  } else if (currentPage == 3) {
    drawClaudePage();
  } else if (currentPage == 4) {
    drawVoiceOverlay();
  } else if (currentPage == 5) {
    drawAIHotspotPage();
  } else {
    drawObsidianDicePage();
  }
  drawOverlay();
  drawCompletionOverlay(now);
  markRenderDiagnostic(180, currentPage);
  composeRenderedFrame(background);
  markRenderDiagnostic(190, currentPage);
}

void drawCurrentPage() {
  // Sample the animation clock once for the whole physical frame. Taking a
  // second millis() reading between the 450 px design canvas and the 466 px
  // surround can cross the completion boundary and expose four paper-coloured
  // points around an otherwise dark/accent animation frame.
  uint32_t now = millis();
  uint16_t background = currentRenderedBackground(now);
  renderCurrentPage(now, background);
  pushRenderedFrame(background);
  markRenderDiagnostic(0);
}

void resetDashboardInputState() {
  aButtonTracking = false;
  aButtonConsumed = false;
  aButtonLongTriggered = false;
  aButtonPressedAt = 0;
  bButtonTracking = false;
  bButtonConsumed = false;
  bButtonLongTriggered = false;
  bButtonPressedAt = 0;
  aClickState = DashboardClickButtonState();
  bClickState = DashboardClickButtonState();
  configChordActive = false;
  touchPending = false;
  activeGesture = DashboardGesture::none;
}

void enterAppLauncher() {
  if (configMode) return;
  if (voiceSessionActive || voiceCaptureActive) stopVoiceForStandby();
  appMode = DashboardAppMode::launcher;
  overlayMode = OverlayMode::none;
  completionAnimationRunning = false;
  completionBaselineReady = false;
  resetDashboardInputState();
  requireHighPerformance();
  drawCurrentPage();
}

void enterDashboardApp() {
  appMode = DashboardAppMode::dashboard;
  currentPage = 0;
  overlayMode = OverlayMode::none;
  resetDashboardInputState();
  requireHighPerformance();
  drawCurrentPage();
}

void enterLocalStopwatchApp() {
  appMode = DashboardAppMode::stopwatch;
  overlayMode = OverlayMode::none;
  localStopwatchLapOffset = 0;
  resetDashboardInputState();
  lastLocalStopwatchDrawAt = 0;
  requireHighPerformance();
  drawCurrentPage();
}

void updateAppShellButtons() {
  bool aPressed = M5.BtnA.wasPressed();
  bool bPressed = readBButtonPressed();
  bool bStarted = bPressed && !shellBButtonWasPressed;
  shellBButtonWasPressed = bPressed;

  if (appMode == DashboardAppMode::launcher) {
    if (aPressed) {
      launcherSelection = 0;
      startVibration(65, 30);
      drawCurrentPage();
    } else if (bStarted) {
      launcherSelection = 1;
      startVibration(65, 30);
      drawCurrentPage();
    }
    return;
  }

  if (appMode != DashboardAppMode::stopwatch) return;
  if (aPressed) {
    std::size_t previousLapCount = localStopwatch.lapCount;
    localStopwatchLeftAction(localStopwatch, millis());
    if (localStopwatch.lapCount != previousLapCount) localStopwatchLapOffset = 0;
    startVibration(75, 32);
    drawCurrentPage();
  } else if (bStarted) {
    localStopwatchRightAction(localStopwatch, millis());
    startVibration(75, 32);
    drawCurrentPage();
  }
}

void updateAppShellTouch(const m5::touch_detail_t &touch) {
  if (!touch.wasReleased()) return;
  int designX = touch.base_x - displayFrameOffsetX() - designFrameOffset();
  int designY = touch.base_y - displayFrameOffsetY() - designFrameOffset();

  if (appMode == DashboardAppMode::stopwatch &&
      localStopwatchLapRegionContains(designX, designY) &&
      abs(touch.distanceY()) >= 45 &&
      abs(touch.distanceY()) > abs(touch.distanceX())) {
    // A finger moving upward has a negative distanceY and reveals older laps.
    int pageDirection = touch.distanceY() < 0 ? 1 : -1;
    std::size_t previousOffset = localStopwatchLapOffset;
    localStopwatchLapOffset = localStopwatchLapPageOffset(
        localStopwatchLapOffset, pageDirection, localStopwatch.lapCount);
    bool moved = localStopwatchLapOffset != previousOffset;
    startVibration(moved ? 48 : 28, moved ? 26 : 18);
    drawCurrentPage();
    return;
  }

  if (abs(touch.distanceX()) >= kGestureLockThreshold ||
      abs(touch.distanceY()) >= kGestureLockThreshold) {
    return;
  }

  if (appMode == DashboardAppMode::launcher) {
    AppShellTouchTarget target = appLauncherTouchTarget(designX, designY);
    if (target == AppShellTouchTarget::dashboard) {
      launcherSelection = 0;
      startVibration(85, 36);
      enterDashboardApp();
    } else if (target == AppShellTouchTarget::stopwatch) {
      launcherSelection = 1;
      startVibration(85, 36);
      enterLocalStopwatchApp();
    }
    return;
  }

  if (appMode != DashboardAppMode::stopwatch) return;
  AppShellTouchTarget target = localStopwatchTouchTarget(designX, designY);
  if (target == AppShellTouchTarget::leftAction) {
    std::size_t previousLapCount = localStopwatch.lapCount;
    localStopwatchLeftAction(localStopwatch, millis());
    if (localStopwatch.lapCount != previousLapCount) localStopwatchLapOffset = 0;
    startVibration(75, 32);
    drawCurrentPage();
  } else if (target == AppShellTouchTarget::rightAction) {
    localStopwatchRightAction(localStopwatch, millis());
    startVibration(75, 32);
    drawCurrentPage();
  }
}

void updateCenterIconAnimation() {
  // ESP_RST_PANIC with a completed page-render stage isolated the fault to
  // this former post-render path. Provider icons are intentionally static:
  // the full page compositor now remains the sole owner of frame/display I/O.
}

void notifyTransitions(const TickTickData &oldTickTick, const CodexData &oldCodex, bool hadData,
                       bool completionStarted) {
  if (!hadData) return;
  if (timerRunning(oldTickTick.countdownState) &&
      !timerRunning(ticktick.countdownState) && ticktick.countdownRemaining == 0) {
    startVibration(170, 220);
    startTonePattern(kFocusDoneTones,
                     sizeof(kFocusDoneTones) / sizeof(kFocusDoneTones[0]));
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
    task.contentVisible = taskSource["content_visible"] | false;
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
  TickTickData oldTickTick = ticktick;
  CodexData oldCodex = codex;
  AIHotspotData oldAiHotspot = aiHotspot;
  bool hadData = haveData;
  if (hadData && lastStateAppliedAt != 0 &&
      static_cast<uint32_t>(millis() - lastStateAppliedAt) > kCompletionStateGapMs) {
    completionBaselineReady = false;
  }

  JsonObject t = doc["ticktick"];
  ticktick.connected = t["connected"] | false;
  JsonObject stopwatch = t["stopwatch"];
  ticktick.stopwatchState = String(static_cast<const char *>(stopwatch["state"] | "idle"));
  ticktick.stopwatchElapsed = stopwatch["elapsed_seconds"] | 0;
  JsonObject countdown = t["countdown"];
  ticktick.countdownState = String(static_cast<const char *>(countdown["state"] | "idle"));
  ticktick.countdownDuration = countdown["duration_seconds"] | 1500;
  ticktick.countdownRemaining = countdown["remaining_seconds"] | ticktick.countdownDuration;
  ticktick.todayFocusSeconds = t["today_focus_seconds"] | 0;
  ticktick.error = String(static_cast<const char *>(t["error"] | ""));
  ticktick.syncedAt = millis();

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

  JsonObject u = doc["ai_usage"];
  aiUsage.connected = u["connected"] | false;
  aiUsage.complete = u["complete"] | false;
  aiUsage.approximate = u["approximate"] | false;
  aiUsage.todayTotalTokens = u["today_total_tokens"] | 0LL;
  aiUsage.todayAuthoritativeTokens = u["today_authoritative_tokens"] | 0LL;

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

  JsonObject hotspot = doc["ai_hotspot"];
  aiHotspot.connected = hotspot["connected"] | false;
  aiHotspot.active = hotspot["active"] | false;
  aiHotspot.unreadCount = hotspot["unread_count"] | 0;
  JsonObject alert = hotspot["alert"];
  aiHotspot.id = String(static_cast<const char *>(alert["id"] | ""));
  aiHotspot.title = String(static_cast<const char *>(alert["title"] | ""));
  aiHotspot.source = String(static_cast<const char *>(alert["source"] | ""));
  aiHotspot.url = String(static_cast<const char *>(alert["url"] | ""));
  aiHotspot.receivedAt = alert["received_at"] | 0LL;

  JsonObject obsidian = doc["obsidian"];
  obsidianDice.connected = obsidian["connected"] | false;
  obsidianDice.availableCount = obsidian["available_count"] | 0;
  JsonObject selectedNote = obsidian["selected"];
  obsidianDice.title = String(static_cast<const char *>(selectedNote["title"] | ""));
  obsidianDice.folder = String(static_cast<const char *>(selectedNote["folder"] | ""));
  obsidianDice.excerpt = String(static_cast<const char *>(selectedNote["excerpt"] | ""));
  obsidianDice.relativePath =
      String(static_cast<const char *>(selectedNote["relative_path"] | ""));
  obsidianDice.rolledAt = obsidian["rolled_at"] | 0LL;

  if (hadData && oldCodex.active > 0 && codex.active == 0 && codex.connected &&
      codex.waiting == 0 && codex.errors == 0) {
    codexDoneAnimationUntilAt = millis() + kCodexDoneAnimationMs;
  }

  haveData = true;
  lastStateAppliedAt = millis();
  notifyTransitions(oldTickTick, oldCodex, hadData, completionStarted);
  bool newAiHotspot = aiHotspot.active &&
                      (!oldAiHotspot.active || aiHotspot.id != oldAiHotspot.id);
  if (newAiHotspot && (screenLocked || appMode == DashboardAppMode::dashboard)) {
    requireHighPerformance();
    startVibration(220, 650);
    startTonePattern(kAiScreamTones,
                     sizeof(kAiScreamTones) / sizeof(kAiScreamTones[0]));
    if (screenLocked) {
      pendingAiHotspotWake = true;
    } else {
      currentPage = 5;
      overlayMode = OverlayMode::none;
    }
  }
  return true;
}

void loadOtaPreferences() {
  Preferences prefs;
  if (!prefs.begin("m5dash-ota", true)) return;
  installedOtaSha = prefs.getString("sha", "");
  prefs.end();
}

bool saveInstalledOtaSha(const String &sha256) {
  Preferences prefs;
  if (!prefs.begin("m5dash-ota", false)) return false;
  size_t written = prefs.putString("sha", sha256);
  prefs.end();
  if (written != sha256.length()) return false;
  installedOtaSha = sha256;
  return true;
}

void drawOtaStatus(const String &label, int percent) {
  const uint16_t background = rgb(7, 8, 14);
  const uint16_t accent = rgb(111, 117, 255);
  // OTA owns the complete 466 px physical frame. The Clock page leaves its
  // mint accent flag armed so normal page composition can extend that circle
  // through the 8 px frame margin; clear both editorial bleed modes before
  // composing this dark full-screen status surface.
  editorialFrameAccentActive = false;
  editorialFrameBurstActive = false;
  canvas.fillScreen(background);
  canvas.setTextDatum(middle_center);
  canvas.setTextColor(accent);
  useNumberFont();
  canvas.drawString("OTA", 225, 154);
  canvas.setTextColor(rgb(235, 236, 241));
  canvas.drawString(label, 225, 220);
  if (percent >= 0) {
    canvas.setTextColor(rgb(166, 170, 185));
    canvas.drawString(String(percent) + "%", 225, 275);
    canvas.fillRoundRect(105, 313, 240, 10, 5, rgb(49, 52, 67));
    int width = max(0, min(240, percent * 240 / 100));
    if (width > 0) canvas.fillRoundRect(105, 313, width, 10, 5, accent);
  }
  composeRenderedFrame(background);
  pushRenderedFrame(background);
}

bool fetchOtaManifest(String &sha256, size_t &imageSize, bool &available) {
  available = false;
  if (WiFi.status() != WL_CONNECTED || activeBridgeHost.length() == 0 ||
      activeBridgePort == 0) {
    return false;
  }
  String url = "http://" + activeBridgeHost + ":" + String(activeBridgePort) +
               "/api/ota/manifest";
  String tokens[2] = {settings.token, settings.token2};
  int tokenOrder[2] = {activeTokenSlot == 1 ? 1 : 0, activeTokenSlot == 1 ? 0 : 1};
  for (int orderIndex = 0; orderIndex < 2; ++orderIndex) {
    int tokenIndex = tokenOrder[orderIndex];
    if (tokens[tokenIndex].length() == 0 ||
        (orderIndex > 0 && tokens[tokenIndex] == tokens[tokenOrder[0]])) {
      continue;
    }
    HTTPClient http;
    http.setTimeout(3000);
    if (!http.begin(url)) return false;
    http.addHeader("X-Dashboard-Token", tokens[tokenIndex]);
    int statusCode = http.GET();
    if (statusCode == HTTP_CODE_NO_CONTENT) {
      http.end();
      activeTokenSlot = tokenIndex;
      return true;
    }
    if (statusCode == HTTP_CODE_OK) {
      JsonDocument doc;
      DeserializationError parseError = deserializeJson(doc, http.getStream());
      http.end();
      if (parseError || (doc["schema"] | 0) != 1) return false;
      sha256 = String(static_cast<const char *>(doc["sha256"] | ""));
      sha256.toLowerCase();
      String releaseId = String(static_cast<const char *>(doc["release_id"] | ""));
      imageSize = doc["size"] | static_cast<size_t>(0);
      if (releaseId != sha256 ||
          !dashboardOtaSha256Valid(sha256.c_str(), sha256.length()) ||
          !dashboardOtaSizeValid(imageSize, kDashboardFactoryOtaPartitionSize)) {
        return false;
      }
      activeTokenSlot = tokenIndex;
      available = true;
      return true;
    }
    http.end();
    if (statusCode != HTTP_CODE_UNAUTHORIZED && statusCode != HTTP_CODE_FORBIDDEN) break;
  }
  return false;
}

bool streamOtaFirmware(const String &sha256, size_t imageSize) {
  const esp_partition_t *running = esp_ota_get_running_partition();
  const esp_partition_t *target = esp_ota_get_next_update_partition(nullptr);
  if (target == nullptr || target == running ||
      !dashboardOtaSizeValid(imageSize, target->size)) {
    return false;
  }

  int tokenIndex = activeTokenSlot == 1 ? 1 : 0;
  String token = tokenIndex == 1 ? settings.token2 : settings.token;
  if (token.length() == 0) return false;
  String url = "http://" + activeBridgeHost + ":" + String(activeBridgePort) +
               "/api/ota/firmware/" + sha256;
  HTTPClient http;
  const char *headerKeys[] = {"X-Firmware-SHA256", "X-Firmware-Release"};
  http.collectHeaders(headerKeys, 2);
  http.setTimeout(10000);
  if (!http.begin(url)) return false;
  http.addHeader("X-Dashboard-Token", token);
  int statusCode = http.GET();
  if (statusCode != HTTP_CODE_OK || http.getSize() != static_cast<int>(imageSize) ||
      http.header("X-Firmware-SHA256") != sha256 ||
      http.header("X-Firmware-Release") != sha256) {
    http.end();
    return false;
  }

  esp_ota_handle_t handle = 0;
  if (esp_ota_begin(target, imageSize, &handle) != ESP_OK) {
    http.end();
    return false;
  }
  uint8_t *buffer = static_cast<uint8_t *>(malloc(8192));
  if (buffer == nullptr) {
    esp_ota_abort(handle);
    http.end();
    return false;
  }

  mbedtls_sha256_context digest;
  mbedtls_sha256_init(&digest);
  bool digestReady = mbedtls_sha256_starts(&digest, 0) == 0;
  bool writeOk = digestReady;
  size_t received = 0;
  int lastPercent = -1;
  uint32_t lastDataAt = millis();
  NetworkClient *stream = http.getStreamPtr();
  while (writeOk && received < imageSize) {
    size_t availableBytes = stream->available();
    if (availableBytes == 0) {
      if ((!http.connected() && received < imageSize) ||
          static_cast<uint32_t>(millis() - lastDataAt) > 10000) {
        writeOk = false;
        break;
      }
      delay(2);
      continue;
    }
    size_t wanted = min(static_cast<size_t>(8192), imageSize - received);
    wanted = min(wanted, availableBytes);
    size_t count = stream->readBytes(buffer, wanted);
    if (count == 0) continue;
    lastDataAt = millis();
    if (mbedtls_sha256_update(&digest, buffer, count) != 0 ||
        esp_ota_write(handle, buffer, count) != ESP_OK) {
      writeOk = false;
      break;
    }
    received += count;
    int percent = static_cast<int>(received * 100 / imageSize);
    if (percent / 5 != lastPercent / 5) {
      lastPercent = percent;
      drawOtaStatus("INSTALL", percent);
    }
    delay(1);
  }

  uint8_t actualDigest[32] = {};
  if (!writeOk || received != imageSize ||
      mbedtls_sha256_finish(&digest, actualDigest) != 0) {
    writeOk = false;
  }
  mbedtls_sha256_free(&digest);
  free(buffer);
  http.end();

  char actualHex[65] = {};
  for (size_t index = 0; index < sizeof(actualDigest); ++index) {
    snprintf(actualHex + index * 2, 3, "%02x", actualDigest[index]);
  }
  if (!writeOk || sha256 != String(actualHex)) {
    esp_ota_abort(handle);
    return false;
  }
  if (esp_ota_end(handle) != ESP_OK) return false;
  // Persist the one-shot release marker before switching boot partitions. If
  // the new image cannot boot, the surviving image will not repeatedly erase
  // and retry the same bad candidate; USB remains the recovery path.
  if (!saveInstalledOtaSha(sha256)) return false;
  if (esp_ota_set_boot_partition(target) != ESP_OK) return false;
  return true;
}

void updateHttpOta() {
  if (otaUpdateRunning || static_cast<uint32_t>(millis() - lastOtaCheckAt) <
                              kOtaCheckIntervalMs) {
    return;
  }
  bool timerActive = timerRunning(ticktick.stopwatchState) ||
                     timerRunning(ticktick.countdownState) ||
                     localStopwatch.state == LocalStopwatchState::running;
  bool voiceActive = voiceSessionActive || voiceCaptureActive;
  if (appMode != DashboardAppMode::dashboard || currentPage != 0 ||
      overlayMode != OverlayMode::none ||
      !dashboardOtaCanStart(WiFi.status() == WL_CONNECTED, bridgeOnline,
                            screenLocked, configMode, voiceActive, timerActive,
                            completionAnimationRunning, deviceBatteryLevel,
                            deviceUsbConnected)) {
    return;
  }
  lastOtaCheckAt = millis();
  String sha256;
  size_t imageSize = 0;
  bool available = false;
  if (!fetchOtaManifest(sha256, imageSize, available) || !available ||
      sha256 == installedOtaSha || sha256 == rejectedOtaSha) {
    return;
  }

  otaUpdateRunning = true;
  requireHighPerformance();
  drawOtaStatus("VERIFY", 0);
  if (!pulseVibrationBlocking(120, 100)) {
    rejectedOtaSha = sha256;
    drawOtaStatus("MOTOR ERROR", -1);
    delay(1200);
    otaUpdateRunning = false;
    drawCurrentPage();
    return;
  }
  bool installed = streamOtaFirmware(sha256, imageSize);
  if (!installed) {
    rejectedOtaSha = sha256;
    drawOtaStatus("OTA ERROR", -1);
    pulseVibrationBlocking(190, 220);
    delay(980);
    otaUpdateRunning = false;
    drawCurrentPage();
    return;
  }
  drawOtaStatus("RESTART", 100);
  pulseVibrationBlocking(150, 180);
  delay(320);
  ESP.restart();
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

void sendUsbDashboardAction(const String &action) {
  String tokens[2] = {settings.token, settings.token2};
  int tokenSlot = activeUsbTokenSlot >= 0 ? activeUsbTokenSlot : 0;
  if (tokens[tokenSlot].length() == 0) tokenSlot = 1 - tokenSlot;
  if (tokens[tokenSlot].length() == 0) return;
  pendingUsbTokenSlot = tokenSlot;
  dashboardBridgeSerial.print(kUsbActionPrefix);
  dashboardBridgeSerial.print(tokens[tokenSlot]);
  dashboardBridgeSerial.print('|');
  dashboardBridgeSerial.println(action);
  lastUsbRequestAt = millis();
}

bool sendHttpDashboardAction(const String &path, uint16_t timeoutMs = 3000) {
  if (WiFi.status() != WL_CONNECTED || activeBridgeHost.length() == 0 ||
      activeBridgePort == 0) {
    return false;
  }
  String url = "http://" + activeBridgeHost + ":" + String(activeBridgePort) + path;
  String tokens[2] = {settings.token, settings.token2};
  int tokenOrder[2] = {activeTokenSlot == 1 ? 1 : 0, activeTokenSlot == 1 ? 0 : 1};
  for (int orderIndex = 0; orderIndex < 2; ++orderIndex) {
    int tokenIndex = tokenOrder[orderIndex];
    if (tokens[tokenIndex].length() == 0) continue;
    HTTPClient http;
    http.setTimeout(timeoutMs);
    if (!http.begin(url)) return false;
    http.addHeader("X-Dashboard-Token", tokens[tokenIndex]);
    http.addHeader("Content-Type", "application/json");
    int statusCode = http.POST("{}");
    if (statusCode == HTTP_CODE_OK) {
      JsonDocument doc;
      DeserializationError parseError = deserializeJson(doc, http.getStream());
      http.end();
      if (parseError) return false;
      activeTokenSlot = tokenIndex;
      bridgeOnline = true;
      // POST actions now return a tiny {"ok":true} acknowledgement. Older
      // bridges returned a full state snapshot, so retain that fallback while
      // installations roll forward.
      if (doc["ok"].is<bool>()) return doc["ok"].as<bool>();
      return applyDashboardState(doc);
    }
    http.end();
    if (statusCode != HTTP_CODE_UNAUTHORIZED && statusCode != HTTP_CODE_FORBIDDEN) break;
  }
  return false;
}

bool sendHttpTickTickAction(const String &action) {
  return sendHttpDashboardAction("/api/ticktick/" + action);
}

void applyOptimisticTickTickAction(const String &action) {
  uint32_t now = millis();
  if (action == "stopwatch-click") {
    if (timerRunning(ticktick.stopwatchState)) {
      ticktick.stopwatchElapsed = currentStopwatchElapsed();
      ticktick.stopwatchState = "paused";
    } else if (timerPaused(ticktick.stopwatchState)) {
      ticktick.stopwatchState = "running";
    } else {
      if (timerRunning(ticktick.countdownState)) {
        ticktick.countdownRemaining = currentCountdownRemaining();
        ticktick.countdownState = "paused";
      }
      ticktick.stopwatchElapsed = 0;
      ticktick.stopwatchState = "running";
    }
    ticktick.syncedAt = now;
    return;
  }
  if (action == "countdown-click") {
    if (timerRunning(ticktick.countdownState)) {
      ticktick.countdownRemaining = currentCountdownRemaining();
      ticktick.countdownState = "paused";
    } else if (timerPaused(ticktick.countdownState)) {
      ticktick.countdownState = "running";
    } else {
      if (timerRunning(ticktick.stopwatchState)) {
        ticktick.stopwatchElapsed = currentStopwatchElapsed();
        ticktick.stopwatchState = "paused";
      }
      ticktick.countdownRemaining = max(1, ticktick.countdownDuration);
      ticktick.countdownState = "running";
    }
    ticktick.syncedAt = now;
    return;
  }
  if (action == "stopwatch-end" && timerRunning(ticktick.stopwatchState)) {
    ticktick.stopwatchElapsed = currentStopwatchElapsed();
    ticktick.stopwatchState = "paused";
    ticktick.syncedAt = now;
  } else if (action == "countdown-end" && timerRunning(ticktick.countdownState)) {
    ticktick.countdownRemaining = currentCountdownRemaining();
    ticktick.countdownState = "paused";
    ticktick.syncedAt = now;
  }
}

void performTickTickAction(const String &action) {
  requireHighPerformance();
  currentPage = 1;
  overlayMode = OverlayMode::none;
  startVibration(action.endsWith("end") ? 90 : 55, action.endsWith("end") ? 55 : 28);
  // Freeze/resume the visible timer at the button event. The USB/HTTP action
  // can take several seconds while TickTick's UI command is confirmed; the
  // following authoritative state response will still reconcile this preview.
  applyOptimisticTickTickAction(action);
  if (usbBridgeOnline) {
    sendUsbDashboardAction(action);
  } else {
    sendHttpTickTickAction(action);
  }
  drawCurrentPage();
}

void performAIHotspotAction(const String &action) {
  requireHighPerformance();
  currentPage = 5;
  overlayMode = OverlayMode::none;
  stopTonePattern();
  startVibration(action == "open" ? 80 : 60, action == "open" ? 55 : 35);
  String wireAction = action == "open" ? "ai-open" : "ai-ack";
  if (usbBridgeOnline) {
    sendUsbDashboardAction(wireAction);
  } else {
    sendHttpDashboardAction(action == "open" ? "/api/ai/open" : "/api/ai/ack");
  }
  drawCurrentPage();
}

void performObsidianAction(const String &action) {
  requireHighPerformance();
  currentPage = 6;
  overlayMode = OverlayMode::none;
  startVibration(action == "roll" ? 125 : 130, action == "roll" ? 90 : 90);
  String wireAction = action == "open" ? "obsidian-open" : "obsidian-roll";
  if (usbBridgeOnline) {
    sendUsbDashboardAction(wireAction);
  } else {
    sendHttpDashboardAction(action == "open" ? "/api/obsidian/open"
                                               : "/api/obsidian/roll");
  }
  drawCurrentPage();
}

bool performTypelessAction(const String &action, DashboardTypelessMode mode) {
  if (mode == DashboardTypelessMode::unavailable) return false;
  String wireAction = action == "start" ? "typeless-start" : "typeless-stop";
  if (mode == DashboardTypelessMode::usbMic && usbBridgeOnline) {
    sendUsbDashboardAction(wireAction);
    return true;
  }
  if (mode == DashboardTypelessMode::macMic) {
    return sendHttpDashboardAction(
        action == "start" ? "/api/typeless/start-mac" : "/api/typeless/stop",
        kTypelessHttpActionTimeoutMs);
  }
  if (usbBridgeOnline) {
    sendUsbDashboardAction(wireAction);
    return true;
  } else {
    return sendHttpDashboardAction(action == "start" ? "/api/typeless/start"
                                                       : "/api/typeless/stop");
  }
}

void sendUsbStateRequest() {
  if (!bootDiagnosticAcknowledged) {
    dashboardBridgeSerial.print(kUsbDiagnosticPrefix);
    dashboardBridgeSerial.print(bootResetReason);
    dashboardBridgeSerial.print('|');
    dashboardBridgeSerial.print(previousRenderDiagnosticStage);
    dashboardBridgeSerial.print('|');
    dashboardBridgeSerial.println(previousRenderDiagnosticPage);
  }
  String tokens[2] = {settings.token, settings.token2};
  int configuredTokenCount = (tokens[0].length() > 0 ? 1 : 0) +
                             (tokens[1].length() > 0 ? 1 : 0);
  bool hasEmptyTokenSlot = configuredTokenCount < 2;
  if (configuredTokenCount == 0 ||
      (hasEmptyTokenSlot && usbUnauthorizedCount >= configuredTokenCount)) {
    uint64_t chipId = ESP.getEfuseMac();
    char deviceId[24];
    snprintf(deviceId, sizeof(deviceId), "M5-%012llX",
             static_cast<unsigned long long>(chipId));
    dashboardBridgeSerial.print(kUsbPairRequestPrefix);
    dashboardBridgeSerial.println(deviceId);
    lastUsbRequestAt = millis();
    return;
  }
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
  if (line.startsWith(kUsbPairResponsePrefix)) {
    String pairedToken = line.substring(strlen(kUsbPairResponsePrefix));
    if (!dashboardUsbPairingTokenValid(pairedToken.c_str(), pairedToken.length())) return;
    int pairedSlot = pairedToken == settings.token ? 0
                     : pairedToken == settings.token2 ? 1
                     : settings.token.length() == 0 ? 0
                     : settings.token2.length() == 0 ? 1
                     : -1;
    if (pairedSlot < 0) return;
    DashboardSettings pairedSettings = settings;
    if (pairedSlot == 0) pairedSettings.token = pairedToken;
    if (pairedSlot == 1) pairedSettings.token2 = pairedToken;
    if (!saveDashboardSettings(pairedSettings)) return;
    settings = pairedSettings;
    activeUsbTokenSlot = pairedSlot;
    pendingUsbTokenSlot = pairedSlot;
    usbUnauthorizedCount = 0;
    lastUsbRequestAt = 0;
    startVibration(80, 35);
    return;
  }
  if (line.startsWith(kUsbErrorPrefix)) {
    activeUsbTokenSlot = -1;
    if (usbUnauthorizedCount < 2) ++usbUnauthorizedCount;
    lastUsbRequestAt = 0;
    return;
  }
  if (!line.startsWith(kUsbResponsePrefix)) return;
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, line.substring(strlen(kUsbResponsePrefix)));
  if (error || !applyDashboardState(doc)) return;
  bootDiagnosticAcknowledged = true;
  activeUsbTokenSlot = pendingUsbTokenSlot;
  usbUnauthorizedCount = 0;
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
      } else {
        const char completionPrefix[] = "M5DASH_EVENT_V1|completion|";
        String sender = discoveryUdp.remoteIP().toString();
        if (strncmp(buffer, completionPrefix, strlen(completionPrefix)) == 0 &&
            sender == activeBridgeHost &&
            (settings.token.length() > 0 || settings.token2.length() > 0) &&
            static_cast<uint32_t>(millis() - lastCompletionHintAt) >= 200) {
          lastCompletionHintAt = millis();
          completionFetchPending = true;
        }
      }
    }
    packetSize = discoveryUdp.parsePacket();
  }
}

void updateCompletionFetchHint() {
  if (!completionFetchPending) return;
  uint32_t now = millis();
  if (usbBridgeOnline) {
    if (usbReplyPending(now, lastUsbRequestAt, kUsbReplyGraceMs)) return;
    completionFetchPending = false;
    lastUsbRequestAt = now;
    sendUsbStateRequest();
    return;
  }
  if (WiFi.status() != WL_CONNECTED || activeBridgeHost.length() == 0) return;
  completionFetchPending = false;
  lastFetchAt = now;
  if (!fetchState()) bridgeOnline = false;
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
  completionFetchPending = false;
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
    // USB-first is a complete operating mode. Wi-Fi is optional and only
    // enters provisioning after Alice deliberately holds A+B.
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
  markRenderDiagnostic(100, nextPage);
  requireHighPerformance();
  obsidianShakePreviousReady = false;

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
  markRenderDiagnostic(110, nextPage);
  currentPage = nextPage;
  overlayMode = OverlayMode::none;
  uint32_t renderNow = millis();
  uint16_t renderBackground = currentRenderedBackground(renderNow);
  renderCurrentPage(renderNow, renderBackground);
  markRenderDiagnostic(130, nextPage);

  constexpr int frameCount = 10;
  constexpr int frameDurationMs = 14;
  int displayWidth = kUiFrameSize;
  int displayOffsetX = displayFrameOffsetX();
  int displayOffsetY = displayFrameOffsetY();
  int direction = delta > 0 ? 1 : -1;
  for (int frame = 1; frame <= frameCount; ++frame) {
    markRenderDiagnostic(static_cast<uint16_t>(140 + frame), nextPage);
    int numerator = frame * frame * (3 * frameCount - 2 * frame);
    int offset = displayWidth * numerator / (frameCount * frameCount * frameCount);
    M5.Display.startWrite();
    fillDisplayFrameMargins(renderBackground);
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
  markRenderDiagnostic(160, nextPage);
  pushRenderedFrame(renderBackground);
  startVibration(65, 30);
  markRenderDiagnostic(0);
}

void returnToClockPage() {
  int delta = dashboardHomePageDelta(currentPage);
  if (delta != 0) {
    changePage(delta);
    return;
  }
  overlayMode = OverlayMode::none;
  drawCurrentPage();
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
  bool featureTap = (currentPage == 5 || currentPage == 6) &&
                    dashboardFeatureTapAccepted(
                        finishedGesture, touch.distanceX(), touch.distanceY());
  bool ordinaryTap = finishedGesture == DashboardGesture::none &&
                     abs(touch.distanceX()) < kGestureLockThreshold &&
                     abs(touch.distanceY()) < kGestureLockThreshold;
  if (finishedGesture == DashboardGesture::page &&
      abs(touch.distanceX()) >= kSwipeThreshold) {
    changePage(touch.distanceX() < 0 ? 1 : -1);
    // If this marker is never observed after a PANIC, the failure is detected
    // while returning from changePage rather than in the following loop work.
    markProviderLoopDiagnostic(501);
  } else if (finishedGesture == DashboardGesture::brightness ||
             finishedGesture == DashboardGesture::volume) {
    overlayUntilAt = millis() + kControlOverlayMs;
    saveUiPreferences();
    if (finishedGesture == DashboardGesture::volume && !notificationMuted) {
      startTonePattern(kVolumePreviewTone,
                       sizeof(kVolumePreviewTone) / sizeof(kVolumePreviewTone[0]));
    }
    drawCurrentPage();
  } else if (ordinaryTap || featureTap) {
    int designX = touch.base_x - displayFrameOffsetX() - designFrameOffset();
    int designY = touch.base_y - displayFrameOffsetY() - designFrameOffset();
    if (currentPage == 1) {
      DashboardFocusTouchTarget target = dashboardFocusTouchTarget(designX, designY);
      if (target != DashboardFocusTouchTarget::none) {
        bool stopwatchMode = focusUsesStopwatchMode();
        String action = target == DashboardFocusTouchTarget::primary
                            ? stopwatchMode ? "stopwatch-click" : "countdown-click"
                            : stopwatchMode ? "stopwatch-end" : "countdown-end";
        activeGesture = DashboardGesture::none;
        touchPending = false;
        performTickTickAction(action);
        return;
      }
    }
    if (currentPage == 0) {
      DashboardClockTouchTarget target = dashboardClockTouchTarget(designX, designY);
      if (target == DashboardClockTouchTarget::orbit) {
        overlayMode = OverlayMode::orbit;
        startVibration(55, 28);
        drawCurrentPage();
        activeGesture = DashboardGesture::none;
        touchPending = false;
        return;
      }
      if (target == DashboardClockTouchTarget::results) {
        selectedResult = -1;
        overlayMode = OverlayMode::results;
        startVibration(55, 28);
        drawCurrentPage();
        activeGesture = DashboardGesture::none;
        touchPending = false;
        return;
      }
    }
    if (currentPage == 5) {
      DashboardFeatureTouchTarget target =
          dashboardFeatureTouchTarget(designX, designY, false);
      if (aiHotspot.active && target != DashboardFeatureTouchTarget::none) {
        activeGesture = DashboardGesture::none;
        touchPending = false;
        performAIHotspotAction(target == DashboardFeatureTouchTarget::secondary
                                   ? "open"
                                   : "ack");
        return;
      }
    }
    if (currentPage == 6) {
      DashboardFeatureTouchTarget target =
          dashboardFeatureTouchTarget(designX, designY, true);
      if (target != DashboardFeatureTouchTarget::none &&
          obsidianDice.availableCount > 0) {
        activeGesture = DashboardGesture::none;
        touchPending = false;
        bool openSelected = target == DashboardFeatureTouchTarget::primary &&
                            obsidianDice.title.length() > 0;
        performObsidianAction(openSelected ? "open" : "roll");
        return;
      }
    }
    if (currentPage == 4 && dashboardVoiceTouchTarget(designX, designY)) {
      activeGesture = DashboardGesture::none;
      touchPending = false;
      toggleVoiceSession();
      return;
    }
    bool running = currentPage == 2 ? codex.active > 0
                                    : currentPage == 3 ? claude.active > 0 : false;
    if (running && dashboardPointInExpandedRect(
                       designX, designY, kCenterIconX, kCenterIconY,
                       kCenterIconSize, kCenterIconSize,
                       kProviderIconTouchExpansion)) {
      activeGesture = DashboardGesture::none;
      touchPending = false;
      openTranscript();
      return;
    }
  }
  activeGesture = DashboardGesture::none;
  touchPending = false;
  markProviderLoopDiagnostic(502);
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
          if (items[index].provider == 'F') {
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
  DashboardTypelessMode endedMode = voiceSessionMode;
  bool shouldStopRemote = voiceSessionActive;
  voiceSessionActive = false;
  voiceSessionMode = DashboardTypelessMode::unavailable;
  voiceCaptureFailed = false;
#if defined(M5DASH_USB_AUDIO)
  // Invalidate the PCM stream first, then leave the microphone UI immediately.
  // I2S/task cleanup can take a few hundred milliseconds, but it no longer
  // blocks the visible response to the B-button release.
  bool hadCapture = deactivateVoiceCaptureStream();
#endif
  voiceCaptureActive = false;
  overlayMode = OverlayMode::none;
  overlayUntilAt = 0;
  startVibration(105, 70);
  drawCurrentPage();
  // Give the user the visible and tactile stop acknowledgement before any
  // network work. The Bridge queues the Typeless toggle and responds with a
  // compact acknowledgement, so READY no longer waits behind macOS.
  if (shouldStopRemote) performTypelessAction("stop", endedMode);
#if defined(M5DASH_USB_AUDIO)
  finishVoiceCaptureHardware(hadCapture);
#endif
}

void toggleVoiceSession() {
  if (!voiceSessionActive) {
    DashboardTypelessMode mode = availableTypelessMode();
    if (mode == DashboardTypelessMode::unavailable) {
      startVibration(45, 24);
      drawCurrentPage();
      return;
    }
    voiceCaptureFailed = false;
    voiceSessionMode = mode;
    if (mode == DashboardTypelessMode::usbMic) {
      voiceSessionActive = beginVoiceCapture();
      if (voiceSessionActive) performTypelessAction("start", mode);
    } else {
      voiceCaptureActive = false;
      // The local session owns the control intent immediately. This makes the
      // first tap vibrate and show LIVE at once, and it preserves STOP as the
      // next action even if the HTTP acknowledgement is lost after Typeless
      // has already started on the Mac.
      voiceSessionActive = true;
      startVibration(55, 28);
      drawCurrentPage();
      bool acknowledged = performTypelessAction("start", mode);
      if (!acknowledged) {
        voiceCaptureFailed = true;
        startVibration(185, 160);
      } else {
        startVibration(120, 90);
      }
      drawCurrentPage();
    }
    return;
  }

  endVoiceCapture();
}

void updateVoiceAudio() {
  static bool availabilityInitialized = false;
  static DashboardTypelessMode previousAvailableMode =
      DashboardTypelessMode::unavailable;
  DashboardTypelessMode availableMode = availableTypelessMode();
  if (!availabilityInitialized) {
    availabilityInitialized = true;
    previousAvailableMode = availableMode;
  } else if (availableMode != previousAvailableMode) {
    previousAvailableMode = availableMode;
    if (voiceSessionActive &&
        voiceSessionMode == DashboardTypelessMode::usbMic &&
        availableMode != DashboardTypelessMode::usbMic) {
      endVoiceCapture();
      return;
    }
    if (!screenLocked && appMode == DashboardAppMode::dashboard &&
        currentPage == 4) {
      drawCurrentPage();
    }
  }
  if (voiceSessionActive && voiceCaptureFailed && !voiceCaptureActive) {
    voiceSessionActive = false;
    voiceSessionMode = DashboardTypelessMode::unavailable;
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

bool readBButtonPressed() {
  // M5Unified normally owns button debouncing. The raw KEYB read is an explicit
  // fallback for StopWatch builds where the board-specific button event is lost.
  return M5.BtnB.isPressed() || digitalRead(kBButtonPin) == LOW;
}

void beginBButtonPress() {
  bButtonTracking = true;
  bButtonConsumed = false;
  bButtonLongTriggered = false;
  bButtonPressedAt = millis();
  requireHighPerformance();
}

void cancelBButtonPress() {
  bButtonTracking = false;
  bButtonConsumed = false;
  bButtonLongTriggered = false;
  bButtonPressedAt = 0;
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
  bootResetReason = static_cast<uint8_t>(esp_reset_reason());
  if (renderDiagnosticMagic == kRenderDiagnosticMagic) {
    previousRenderDiagnosticStage = renderDiagnosticStage;
    previousRenderDiagnosticPage = renderDiagnosticPage <= 7 ? renderDiagnosticPage : 7;
  } else {
    previousRenderDiagnosticStage = 0;
    previousRenderDiagnosticPage = 7;
  }
  markRenderDiagnostic(1);
  bool shouldOpenSavedWifiPicker = openWifiPickerAfterRestart;
  openWifiPickerAfterRestart = false;
  auto config = M5.config();
  config.clear_display = true;
  M5.begin(config);
  // M5PM1 clears CHG_EN after reset and Download Mode. Re-enable the physical
  // charger on every application boot; USB data and battery charging are
  // independent and are expected to operate at the same time.
  M5.Power.setBatteryCharge(true);
  pinMode(kBButtonPin, INPUT_PULLUP);
  configurePowerButtonPolicy();
  disableBottomLed();
  M5.Display.setRotation(0);
  loadUiPreferences();
  loadOtaPreferences();
  // M5.begin() initializes the internal speaker by default. The dashboard is
  // silent most of the time, so leave the codec and PA off until a tone starts.
  disableSpeakerOutput();
  canvas.setColorDepth(16);
  canvas.createSprite(kUiDesignSize, kUiDesignSize);
  initializeUiChineseFont();
  initializeStopwatchDigitFont();
  initializeEditorialFonts();
  frameCanvas.setColorDepth(16);
  frameCanvasReady = frameCanvas.createSprite(kUiFrameSize, kUiFrameSize) != nullptr;
  stopwatchTimeCanvas.setColorDepth(16);
  stopwatchTimeCanvasReady =
      stopwatchTimeCanvas.createSprite(kStopwatchTimeWidth, kStopwatchTimeHeight) != nullptr;
  clockSecondCanvas.setColorDepth(16);
  clockSecondCanvasReady =
      clockSecondCanvas.createSprite(kClockSecondPatchWidth, kClockSecondPatchHeight) != nullptr;
  aiHotspotBurstCanvas.setColorDepth(16);
  aiHotspotBurstCanvasReady =
      aiHotspotBurstCanvas.createSprite(220, 220) != nullptr;
  if (aiHotspotBurstCanvasReady) {
    aiHotspotBurstCanvas.fillSprite(editorialPaperColor());
    aiHotspotBurstCanvas.drawPng(
        ai_hotspot_burst_source_png, ai_hotspot_burst_source_png_len,
        0, 0, 220, 220, 0, 0, 1.0f, 1.0f, datum_t::top_left);
    aiHotspotBurstCanvas.setPivot(110, 110);
  }
  transitionCanvas.setColorDepth(16);
  transitionCanvasReady =
      transitionCanvas.createSprite(kUiFrameSize, kUiFrameSize) != nullptr;
  lastHighPerformanceAt = millis();
  updateDevicePower(true);

  DashboardSettings defaults;
  // Credentials never ship inside firmware images. Existing devices load their
  // saved NVS values; a fresh device pairs with the local bridge over USB.
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
  if (settings.ssid.length() > 0 || settings.ssid2.length() > 0) connectWifi();
  if (!configMode) {
    drawCurrentPage();
    if (shouldOpenSavedWifiPicker) openWifiPicker();
  }
  // A freshly installed OTA image is accepted only after the complete device
  // setup path has succeeded. Factory bootloaders without rollback support
  // simply return a harmless status here.
  esp_ota_mark_app_valid_cancel_rollback();
  lastOtaCheckAt = millis();
}

void loop() {
  markProviderLoopDiagnostic(600);
  M5.update();
  updatePowerButton();
  updateVibration();
  updateTonePattern();
  updateVoiceAudio();
  updateAudioPowerGuard();
  updateDevicePower();
  if (usbAudioStreaming) requireHighPerformance();
  updateCpuPolicy();
  updateHttpOta();
  if (screenLocked) {
    // Keep the lightweight data plane alive with the AMOLED, touch controller
    // and microphone asleep. State updates can therefore trigger an audible
    // AI-hotspot alert and arm page 6 for the next wake.
    if (configMode) {
      provisioning.handle();
      delay(10);
      return;
    }
    updateUsbBridge();
    if (settings.ssid.length() > 0 || settings.ssid2.length() > 0) connectWifi();
    updateBridgeDiscovery();
    updateCompletionFetchHint();
    uint32_t now = millis();
    if (now - lastFetchAt >= dashboardStateRefreshInterval() &&
        !usbReplyPending(now, lastUsbRequestAt, kUsbReplyGraceMs)) {
      lastFetchAt = now;
      if (!usbBridgeOnline && !fetchState()) bridgeOnline = false;
    }
    delay(25);
    return;
  }

  updateOverlayTimeout();
  updateCompletionAnimation();
  updateCenterIconAnimation();
  updateResultBallImuAnimation();
  updateObsidianDiceShake();
  markProviderLoopDiagnostic(610);
  if (configMode) {
    bool bothButtons = M5.BtnA.isPressed() && readBButtonPressed();
    if (!bothButtons) configHoldTriggered = false;
    if (bothButtons && !configHoldTriggered &&
        M5.BtnA.pressedFor(2500)) {
      configHoldTriggered = true;
      stopVibration();
      ESP.restart();
    }
    updateProvisioningTouch(M5.Touch.getDetail());
    provisioning.handle();
    delay(2);
    return;
  }

  if (appMode != DashboardAppMode::dashboard) {
    updateAppShellButtons();
    updateUsbBridge();
    if (settings.ssid.length() > 0 || settings.ssid2.length() > 0) connectWifi();
    updateBridgeDiscovery();
    updateCompletionFetchHint();

    auto shellTouch = M5.Touch.getDetail();
    updateAppShellTouch(shellTouch);

    uint32_t now = millis();
    if (appMode == DashboardAppMode::stopwatch &&
        localStopwatch.state == LocalStopwatchState::running &&
        static_cast<uint32_t>(now - lastLocalStopwatchDrawAt) >=
            kStopwatchFrameIntervalMs) {
      lastLocalStopwatchDrawAt = now;
      requireHighPerformance();
      drawLocalStopwatchTimeOnly();
    }
    if (now - lastFetchAt >= dashboardStateRefreshInterval() &&
        !usbReplyPending(now, lastUsbRequestAt, kUsbReplyGraceMs)) {
      lastFetchAt = now;
      if (!usbBridgeOnline && !fetchState()) bridgeOnline = false;
      drawCurrentPage();
    }
    delay(10);
    return;
  }

  DashboardClickAction aPendingAction =
      flushDashboardClick(aClickState, millis(), kFocusDoubleClickMs);
  DashboardClickAction bPendingAction =
      flushDashboardClick(bClickState, millis(), kFocusDoubleClickMs);
  if (aPendingAction == DashboardClickAction::singleClick) {
    performTickTickAction("stopwatch-click");
  }
  if (bPendingAction == DashboardClickAction::singleClick) {
    performTickTickAction("countdown-click");
  }

  bool aButtonPressed = M5.BtnA.isPressed();
  if (aButtonPressed && !aButtonTracking) beginAButtonPress();
  bool bButtonPressed = readBButtonPressed();
  if (bButtonPressed && !bButtonTracking) beginBButtonPress();

  bool bothButtons = aButtonPressed && bButtonPressed;
  if (bothButtons) {
    configChordActive = true;
    aButtonConsumed = true;
  }
  if (bothButtons && !configHoldTriggered &&
      M5.BtnA.pressedFor(2500) && millis() - bButtonPressedAt >= 2500) {
    configHoldTriggered = true;
    startProvisioning();
    return;
  }
  if (!bothButtons) configHoldTriggered = false;

  if (configChordActive) {
    aButtonConsumed = true;
    bButtonConsumed = true;
    if (voiceSessionActive) {
      endVoiceCapture();
    }
    if (!aButtonPressed && !bButtonPressed) {
      configChordActive = false;
      cancelAButtonPress();
      cancelBButtonPress();
    }
  } else {
    if (bButtonPressed && bButtonTracking && !bButtonLongTriggered &&
        static_cast<uint32_t>(millis() - bButtonPressedAt) >= kBButtonLongPressMs) {
      bButtonLongTriggered = true;
      bButtonConsumed = true;
      returnToClockPage();
    }
    if (!bButtonPressed && bButtonTracking) {
      if (!bButtonConsumed) {
        DashboardClickAction action =
            queueDashboardClick(bClickState, millis(), kFocusDoubleClickMs);
        if (action == DashboardClickAction::doubleClick) {
          performTickTickAction("countdown-end");
        }
      }
      cancelBButtonPress();
    }
    if (aButtonPressed && aButtonTracking && !aButtonLongTriggered &&
        static_cast<uint32_t>(millis() - aButtonPressedAt) >= kAButtonLongPressMs) {
      aButtonLongTriggered = true;
      aButtonConsumed = true;
      if (!wifiReconnectPaused) wifiPickerMessage = "";
      openWifiPicker();
    }
    if (!aButtonPressed && aButtonTracking) {
      if (!aButtonConsumed) {
        DashboardClickAction action =
            queueDashboardClick(aClickState, millis(), kFocusDoubleClickMs);
        if (action == DashboardClickAction::doubleClick) {
          performTickTickAction("stopwatch-end");
        }
      }
      cancelAButtonPress();
    }
  }

  markProviderLoopDiagnostic(630);
  bool hadDataBeforeUsbUpdate = haveData;
  updateUsbBridge();
  if (!hadDataBeforeUsbUpdate && haveData &&
      appMode == DashboardAppMode::dashboard && currentPage == 0 &&
      overlayMode == OverlayMode::none && !completionAnimationRunning) {
    // The launcher can enter Dashboard before the first USB state reply. The
    // screen then contains drawConnectingPage(), not the Clock surface. Paint
    // the complete Clock once before its seconds-only patch is allowed to run.
    drawCurrentPage();
  }
  markProviderLoopDiagnostic(631);
  connectWifi();
  markProviderLoopDiagnostic(632);
  if (configMode) {
    delay(2);
    return;
  }
  updateBridgeDiscovery();
  updateCompletionFetchHint();
  markProviderLoopDiagnostic(633);

  auto touch = M5.Touch.getDetail();
  markProviderLoopDiagnostic(640);
  updateTouchInteraction(touch);
  markProviderLoopDiagnostic(641);

  uint32_t tickSecond = millis() / 1000;
  if (haveData && appMode == DashboardAppMode::dashboard && currentPage == 0 &&
      overlayMode == OverlayMode::none &&
      !completionAnimationRunning) {
    struct tm clockNow = {};
    if (clockLocalTime(clockNow)) {
      int minuteKey = clockNow.tm_hour * 60 + clockNow.tm_min;
      DashboardClockRefresh refresh = dashboardClockRefresh(
          clockNow.tm_sec, lastClockDrawSecond, minuteKey, lastClockDrawMinute);
      if (refresh == DashboardClockRefresh::fullPage) {
        drawCurrentPage();
      } else if (refresh == DashboardClockRefresh::secondsOnly) {
        drawClockSecondOnly(clockNow);
      }
    }
  }
  if (haveData && currentPage == 1 &&
      (timerRunning(ticktick.stopwatchState) || timerRunning(ticktick.countdownState)) &&
      tickSecond != lastTickTickDrawSecond) {
    lastTickTickDrawSecond = tickSecond;
    drawCurrentPage();
  }

  if (millis() - lastFetchAt >= dashboardStateRefreshInterval() &&
      !usbReplyPending(millis(), lastUsbRequestAt, kUsbReplyGraceMs)) {
    lastFetchAt = millis();
    bool hadDataBeforeFetch = haveData;
    if (!usbBridgeOnline && !fetchState()) bridgeOnline = false;
    // The Clock page owns a once-per-second patch renderer. Do not undo that
    // work with the normal two-second state-sync redraw; the next minute
    // boundary refreshes the complete page and picks up weather, usage, focus,
    // and battery changes. Overlays and completion animations still redraw
    // immediately because they replace the base clock surface.
    bool deferClockStateRedraw =
        hadDataBeforeFetch && haveData &&
        appMode == DashboardAppMode::dashboard && currentPage == 0 &&
        overlayMode == OverlayMode::none && !completionAnimationRunning;
    if (!deferClockStateRedraw) drawCurrentPage();
  }
  markProviderLoopDiagnostic(699);
  delay(10);
}
