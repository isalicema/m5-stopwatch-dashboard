#include <cassert>

#include "../firmware/M5Dashboard/app_shell_logic.h"
#include "../firmware/M5Dashboard/icon_animation.h"
#include "../firmware/M5Dashboard/interaction_logic.h"
#include "../firmware/M5Dashboard/ota_logic.h"

int main() {
  assert(dashboardOtaSha256Valid(
      "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", 64));
  assert(!dashboardOtaSha256Valid(
      "0123456789ABCDEF0123456789abcdef0123456789abcdef0123456789abcdef", 64));
  assert(!dashboardOtaSha256Valid("short", 5));
  assert(dashboardOtaSizeValid(5088528, 0x4F0000));
  assert(!dashboardOtaSizeValid(0, 0x4F0000));
  assert(!dashboardOtaSizeValid(0x4F0001, 0x600000));
  assert(dashboardOtaCanStart(true, true, false, false, false, false, false, 40, false));
  assert(dashboardOtaCanStart(true, true, false, false, false, false, false, 5, true));
  assert(!dashboardOtaCanStart(true, true, true, false, false, false, false, 100, true));
  assert(!dashboardOtaCanStart(true, true, false, false, true, false, false, 100, true));
  assert(!dashboardOtaCanStart(true, true, false, false, false, true, false, 100, true));
  assert(dashboardUsbPairingTokenValid("abcdefghijklmnopqrstuvwxyz_123456", 33));
  assert(!dashboardUsbPairingTokenValid("too-short", 9));
  assert(!dashboardUsbPairingTokenValid("abcdefghijklmnop|bad", 20));
  assert(classifyDashboardGesture(8, 7, 100, 450, 18) == DashboardGesture::none);
  assert(classifyDashboardGesture(-80, 12, 100, 450, 18) == DashboardGesture::page);
  assert(classifyDashboardGesture(9, -60, 100, 450, 18) ==
         DashboardGesture::brightness);
  assert(classifyDashboardGesture(9, 60, 350, 450, 18) == DashboardGesture::volume);
  assert(classifyDashboardGesture(30, 30, 100, 450, 18) == DashboardGesture::none);

  assert(adjustedDashboardPercent(50, -150, 10, 300, 5) == 100);
  assert(adjustedDashboardPercent(50, 150, 10, 300, 5) == 10);
  assert(adjustedDashboardPercent(40, -29, 0, 300, 5) == 50);
  assert(adjustedDashboardPercent(5, 300, 0, 300, 5) == 0);
  assert(adjustedDashboardPercent(40, -3, 0, 300, 1) == 41);
  assert(adjustedDashboardPercent(40, 3, 0, 300, 1) == 39);

  assert(shouldToggleVoiceSessionOnRelease(true, false));
  assert(!shouldToggleVoiceSessionOnRelease(true, true));
  assert(!shouldToggleVoiceSessionOnRelease(false, false));
  assert(dashboardTypelessUsbAvailable(true, true, true, true));
  assert(!dashboardTypelessUsbAvailable(true, false, true, true));
  assert(!dashboardTypelessUsbAvailable(true, true, false, true));
  assert(dashboardTypelessMode(true, true, true) ==
         DashboardTypelessMode::usbMic);
  assert(dashboardTypelessMode(false, true, true) ==
         DashboardTypelessMode::macMic);
  assert(dashboardTypelessMode(false, false, true) ==
         DashboardTypelessMode::unavailable);
  assert(dashboardTypelessMode(false, true, false) ==
         DashboardTypelessMode::unavailable);
  assert(dashboardClockRefresh(8, 8, 60, 60) == DashboardClockRefresh::none);
  assert(dashboardClockRefresh(9, 8, 60, 60) ==
         DashboardClockRefresh::secondsOnly);
  assert(dashboardClockRefresh(0, 59, 61, 60) ==
         DashboardClockRefresh::fullPage);
  assert(dashboardClockRefresh(8, -1, 60, -1) ==
         DashboardClockRefresh::fullPage);
  assert(!dashboardTypelessUsbAvailable(true, true, true, false));
  assert(!dashboardTypelessUsbAvailable(false, true, true, true));

  assert(dashboardRectInsideCircle(kFocusStatusX, kFocusStatusBoundsY,
                                   kFocusStatusBoundsWidth,
                                   kFocusStatusBoundsHeight, 225, 225, 209));
  assert(dashboardRectInsideCircle(kFocusPrimaryActionX, kFocusActionY,
                                   kFocusPrimaryActionWidth, kFocusActionHeight,
                                   225, 225, 209));
  assert(dashboardRectInsideCircle(kFocusEndActionX, kFocusActionY,
                                   kFocusEndActionWidth, kFocusActionHeight,
                                   225, 225, 209));
  assert(dashboardRectInsideCircle(kFocusPrimaryTouchX, kFocusActionTouchY,
                                   kFocusPrimaryTouchWidth, kFocusActionTouchHeight,
                                   225, 225, 225));
  assert(dashboardRectInsideCircle(kFocusEndTouchX, kFocusActionTouchY,
                                   kFocusEndTouchWidth, kFocusActionTouchHeight,
                                   225, 225, 225));
  assert(dashboardFocusTouchTarget(180, 370) ==
         DashboardFocusTouchTarget::primary);
  assert(dashboardFocusTouchTarget(320, 370) ==
         DashboardFocusTouchTarget::end);
  assert(dashboardFocusTouchTarget(180, 425) ==
         DashboardFocusTouchTarget::primary);
  assert(dashboardFocusTouchTarget(320, 425) ==
         DashboardFocusTouchTarget::end);
  assert(dashboardFocusTouchTarget(320, 435) ==
         DashboardFocusTouchTarget::end);
  assert(dashboardFocusTouchTarget(320, 436) ==
         DashboardFocusTouchTarget::none);
  assert(dashboardFocusTouchTarget(225, 330) == DashboardFocusTouchTarget::none);
  assert(dashboardFocusTouchTarget(90, 390) == DashboardFocusTouchTarget::none);
  assert(dashboardFocusTapAccepted(30, -22));
  assert(dashboardFocusTapAccepted(-34, 34));
  assert(!dashboardFocusTapAccepted(35, 0));
  assert(dashboardTimerPreserveRunningAnchor(true, true, 68, 71));
  assert(dashboardTimerPreserveRunningAnchor(true, true, 71, 68));
  assert(!dashboardTimerPreserveRunningAnchor(true, true, 68, 72));
  assert(!dashboardTimerPreserveRunningAnchor(false, true, 68, 68));
  assert(!dashboardTimerPreserveRunningAnchor(true, false, 68, 68));
  assert(dashboardAlignedRunningTimerBase(71, 2, false) == 69);
  assert(dashboardAlignedRunningTimerBase(68, 2, false) == 66);
  assert(dashboardAlignedRunningTimerBase(68, 2, true) == 70);
  assert(dashboardAlignedRunningTimerBase(1, 2, false) == 0);

  assert(dashboardRectInsideCircle(kEditorialHeaderX, kEditorialHeaderBoundsY,
                                   kEditorialHeaderBoundsWidth,
                                   kEditorialHeaderBoundsHeight, 225, 225, 209));
  assert(dashboardRectInsideCircle(kClockOrbitActionX, kClockActionY,
                                   kClockActionWidth, kClockActionHeight,
                                   225, 225, 209));
  assert(dashboardRectInsideCircle(kClockResultsActionX, kClockActionY,
                                   kClockActionWidth, kClockActionHeight,
                                   225, 225, 209));
  assert(dashboardClockTouchTarget(150, 370) ==
         DashboardClockTouchTarget::orbit);
  assert(dashboardClockTouchTarget(300, 370) ==
         DashboardClockTouchTarget::results);
  assert(dashboardClockTouchTarget(150, 303) ==
         DashboardClockTouchTarget::none);
  assert(dashboardClockTouchTarget(300, 303) ==
         DashboardClockTouchTarget::none);
  assert(dashboardClockTouchTarget(150, 324) ==
         DashboardClockTouchTarget::none);
  assert(dashboardClockTouchTarget(300, 324) ==
         DashboardClockTouchTarget::none);
  assert(dashboardClockTouchTarget(150, 335) ==
         DashboardClockTouchTarget::none);
  assert(dashboardClockTouchTarget(150, 336) ==
         DashboardClockTouchTarget::orbit);
  assert(dashboardClockTouchTarget(155, 420) ==
         DashboardClockTouchTarget::orbit);
  assert(dashboardClockTouchTarget(335, 425) ==
         DashboardClockTouchTarget::results);
  assert(dashboardClockTouchTarget(300, 431) ==
         DashboardClockTouchTarget::results);
  assert(dashboardClockTouchTarget(300, 432) ==
         DashboardClockTouchTarget::none);
  assert(dashboardClockTouchTarget(225, 320) ==
         DashboardClockTouchTarget::none);
  assert(dashboardClockTapAccepted(30, -22));
  assert(dashboardClockTapAccepted(-34, 34));
  assert(!dashboardClockTapAccepted(35, 0));
  assert(!dashboardClockTapAccepted(0, -35));
  assert(dashboardRectInsideCircle(kProviderIconX - kProviderIconTouchExpansion,
                                   kProviderIconY - kProviderIconTouchExpansion,
                                   kProviderIconSize + 2 * kProviderIconTouchExpansion,
                                   kProviderIconSize + 2 * kProviderIconTouchExpansion,
                                   225, 225, 225));
  assert(dashboardPointInExpandedRect(310, 170, kProviderIconX, kProviderIconY,
                                      kProviderIconSize, kProviderIconSize,
                                      kProviderIconTouchExpansion));
  assert(!dashboardPointInExpandedRect(270, 120, kProviderIconX, kProviderIconY,
                                       kProviderIconSize, kProviderIconSize,
                                       kProviderIconTouchExpansion));
  assert(dashboardVoiceTouchTarget(225, 200));
  assert(dashboardVoiceTouchTarget(62, 94));
  assert(!dashboardVoiceTouchTarget(40, 200));
  assert(dashboardVoiceTouchTarget(225, 360));
  assert(!dashboardVoiceTouchTarget(80, 370));

  DashboardClickButtonState click;
  assert(queueDashboardClick(click, 100, 360) == DashboardClickAction::none);
  assert(flushDashboardClick(click, 459, 360) == DashboardClickAction::none);
  assert(flushDashboardClick(click, 460, 360) == DashboardClickAction::singleClick);
  assert(queueDashboardClick(click, 1000, 360) == DashboardClickAction::none);
  assert(queueDashboardClick(click, 1200, 360) == DashboardClickAction::doubleClick);
  assert(flushDashboardClick(click, 1600, 360) == DashboardClickAction::none);

  assert(dashboardHomePageDelta(0) == 0);
  for (int page = 1; page < 7; ++page) {
    assert(page + dashboardHomePageDelta(page) == 0);
  }

  click = {};
  uint32_t clickWrap = UINT32_MAX - 100;
  assert(queueDashboardClick(click, clickWrap, 360) == DashboardClickAction::none);
  assert(flushDashboardClick(click, 259, 360) == DashboardClickAction::singleClick);

  DashboardPowerButtonState power;
  assert(updateDashboardPowerButton(power, true, 100, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 180, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 679, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 680, 1500, 500, 1600, false) ==
         DashboardPowerAction::toggleScreen);

  power = {};
  assert(updateDashboardPowerButton(power, true, 100, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 180, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, true, 400, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 470, 1500, 500, 1600, false) ==
         DashboardPowerAction::openLauncher);

  power = {};
  assert(updateDashboardPowerButton(power, true, 100, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 180, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, true, 400, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, true, 2000, 1500, 500, 1600, false) ==
         DashboardPowerAction::powerOff);
  assert(updateDashboardPowerButton(power, false, 2100, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 2600, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);

  power = {};
  assert(updateDashboardPowerButton(power, true, 1000, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, true, 2600, 1500, 500, 1600, false) ==
         DashboardPowerAction::powerOff);
  assert(updateDashboardPowerButton(power, false, 2700, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);

  power = {};
  assert(updateDashboardPowerButton(power, true, 2000, 1500, 500, 1600, true) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, true, 3600, 1500, 500, 1600, true) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 3700, 1500, 500, 1600, true) ==
         DashboardPowerAction::none);

  power = {};
  uint32_t nearWrap = UINT32_MAX - 100;
  assert(updateDashboardPowerButton(power, true, nearWrap, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, nearWrap + 50, 1500, 500, 1600, false) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 449, 1500, 500, 1600, false) ==
         DashboardPowerAction::toggleScreen);

  LocalStopwatchModel localStopwatch;
  assert(localStopwatch.state == LocalStopwatchState::stopped);
  localStopwatchLeftAction(localStopwatch, 100);
  assert(localStopwatch.state == LocalStopwatchState::stopped);
  localStopwatchRightAction(localStopwatch, 100);
  assert(localStopwatch.state == LocalStopwatchState::running);
  assert(localStopwatchElapsedMs(localStopwatch, 3100) == 3000);
  localStopwatchLeftAction(localStopwatch, 3100);
  assert(localStopwatch.lapCount == 1);
  assert(localStopwatch.laps[0] == 3000);
  assert(localStopwatchMaximumLapOffset(1) == 0);
  assert(localStopwatchLapPageOffset(0, 1, 1) == 0);
  localStopwatchRightAction(localStopwatch, 5100);
  assert(localStopwatch.state == LocalStopwatchState::paused);
  assert(localStopwatch.accumulatedMs == 5000);
  assert(localStopwatchElapsedMs(localStopwatch, 9000) == 5000);
  localStopwatchRightAction(localStopwatch, 9000);
  assert(localStopwatch.state == LocalStopwatchState::running);
  assert(localStopwatchElapsedMs(localStopwatch, 10000) == 6000);
  localStopwatchRightAction(localStopwatch, 10000);
  assert(localStopwatch.state == LocalStopwatchState::paused);
  localStopwatchLeftAction(localStopwatch, 10001);
  assert(localStopwatch.state == LocalStopwatchState::stopped);
  assert(localStopwatchElapsedMs(localStopwatch, 12000) == 0);
  assert(localStopwatch.lapCount == 0);
  assert(appLauncherTouchTarget(137, 222) == AppShellTouchTarget::dashboard);
  assert(appLauncherTouchTarget(313, 222) == AppShellTouchTarget::stopwatch);
  assert(appLauncherTouchTarget(225, 100) == AppShellTouchTarget::none);
  assert(localStopwatchTouchTarget(150, 90) == AppShellTouchTarget::leftAction);
  assert(localStopwatchTouchTarget(299, 90) == AppShellTouchTarget::rightAction);
  assert(localStopwatchMaximumLapOffset(5) == 2);
  assert(localStopwatchFirstVisibleLap(5, 0) == 2);
  assert(localStopwatchLapPageOffset(0, 1, 5) == 2);
  assert(localStopwatchFirstVisibleLap(5, 2) == 0);
  assert(localStopwatchLapPageOffset(2, -1, 5) == 0);
  assert(localStopwatchLapPageOffset(0, -1, 5) == 0);
  assert(localStopwatchLapRegionContains(225, 320));
  assert(!localStopwatchLapRegionContains(225, 240));

  assert(!usbReplyPending(1000, 0, 500));
  assert(usbReplyPending(1200, 1000, 500));
  assert(!usbReplyPending(1500, 1000, 500));
  assert(usbReplyPending(100, UINT32_MAX - 99, 500));

  assert(dashboardCenteredOffset(466, 450) == 8);
  assert(dashboardCenteredOffset(468, 466) == 1);
  assert(dashboardCenteredOffset(450, 450) == 0);
  assert(dashboardCenteredOffset(320, 450) == 0);

  assert(nextConfiguredWifiProfile(-1, true, true) == 0);
  assert(nextConfiguredWifiProfile(0, true, true) == 1);
  assert(nextConfiguredWifiProfile(1, true, true) == 0);
  assert(nextConfiguredWifiProfile(-1, false, true) == 1);
  assert(nextConfiguredWifiProfile(1, false, true) == 1);
  assert(nextConfiguredWifiProfile(-1, true, false) == 0);
  assert(nextConfiguredWifiProfile(0, true, false) == 0);
  assert(nextConfiguredWifiProfile(-1, false, false) == -1);

  assert(dashboardRemainingPercent(-1) == -1);
  assert(dashboardRemainingPercent(0) == 100);
  assert(dashboardRemainingPercent(50) == 50);
  assert(dashboardRemainingPercent(100) == 0);
  assert(dashboardRemainingPercent(120) == 0);

  assert(dashboardPointInExpandedRect(177, 170, 177, 170, 96, 96, 14));
  assert(dashboardPointInExpandedRect(165, 158, 177, 170, 96, 96, 14));
  assert(!dashboardPointInExpandedRect(140, 140, 177, 170, 96, 96, 14));
  assert(dashboardTranscriptOffset(0, 1, 6, 4) == 1);
  assert(dashboardTranscriptOffset(1, 5, 6, 4) == 2);
  assert(dashboardTranscriptOffset(1, -5, 6, 4) == 0);
  assert(dashboardTranscriptOffset(0, 1, 3, 4) == 0);

  assert(dashboardFeatureTouchTarget(120, 360, false) ==
         DashboardFeatureTouchTarget::primary);
  assert(dashboardFeatureTouchTarget(300, 360, false) ==
         DashboardFeatureTouchTarget::secondary);
  assert(dashboardFeatureTouchTarget(300, 140, true) ==
         DashboardFeatureTouchTarget::hero);
  assert(dashboardFeatureTouchTarget(300, 140, false) ==
         DashboardFeatureTouchTarget::none);
  assert(dashboardFeatureTouchTarget(120, 332, false) ==
         DashboardFeatureTouchTarget::primary);
  assert(dashboardFeatureTouchTarget(120, 407, false) ==
         DashboardFeatureTouchTarget::primary);
  assert(dashboardFeatureTouchTarget(120, 430, false) ==
         DashboardFeatureTouchTarget::primary);
  assert(dashboardFeatureTouchTarget(300, 430, false) ==
         DashboardFeatureTouchTarget::secondary);
  assert(dashboardFeatureTouchTarget(120, 439, false) ==
         DashboardFeatureTouchTarget::primary);
  assert(dashboardFeatureTouchTarget(120, 440, false) ==
         DashboardFeatureTouchTarget::none);
  assert(dashboardFeatureTapAccepted(DashboardGesture::none, 17, 17));
  assert(dashboardFeatureTapAccepted(DashboardGesture::none, 0, 32));
  assert(dashboardFeatureTapAccepted(DashboardGesture::page, 31, -24));
  assert(!dashboardFeatureTapAccepted(DashboardGesture::page, 33, 0));
  assert(!dashboardFeatureTapAccepted(DashboardGesture::brightness, 4, 4));
  assert(!dashboardShakeDetected(false, 1.0f, 0.0f, 0.0f, 1000, 0, 900, 0.78f));
  assert(!dashboardShakeDetected(true, 1.0f, 0.0f, 0.0f, 850, 0, 900, 0.78f));
  assert(dashboardShakeDetected(true, 0.8f, 0.0f, 0.0f, 1000, 0, 900, 0.78f));
  assert(!dashboardShakeDetected(true, 0.5f, 0.2f, 0.1f, 1000, 0, 900, 0.78f));

  assert(selectDashboardCodexIconMode(false, 1, 1, 1, true) ==
         DashboardCodexIconMode::idle);
  assert(selectDashboardCodexIconMode(true, 1, 1, 1, true) ==
         DashboardCodexIconMode::waiting);
  assert(selectDashboardCodexIconMode(true, 1, 0, 1, true) ==
         DashboardCodexIconMode::working);
  assert(selectDashboardCodexIconMode(true, 0, 0, 1, true) ==
         DashboardCodexIconMode::failed);
  assert(selectDashboardCodexIconMode(true, 0, 0, 0, true) ==
         DashboardCodexIconMode::done);
  assert(selectDashboardCodexIconMode(true, 0, 0, 0, false) ==
         DashboardCodexIconMode::idle);

  assert(dashboardAnimationFrame(0, 120, 6) == 0);
  assert(dashboardAnimationFrame(719, 120, 6) == 5);
  assert(dashboardAnimationFrame(720, 120, 6) == 0);
  assert(dashboardAnimationFrame(100, 0, 6) == 0);
  assert(dashboardAnimationFrame(100, 120, 0) == 0);
  assert(dashboardClaudeScalePercent(0) == 92);
  assert(dashboardClaudeScalePercent(4) == 108);
  assert(dashboardClaudeScalePercent(8) == 92);

  assert(dashboardDeadlinePending(1000, 1200));
  assert(!dashboardDeadlinePending(1200, 1200));
  assert(dashboardDeadlinePending(UINT32_MAX - 50, 25));

  DashboardCompletionAnimationFrame completion =
      dashboardCompletionAnimationFrame(0);
  assert(completion.visible);
  assert(completion.ringDegrees == 0);
  assert(completion.providerIconStep == 0);
  assert(completion.successRadius == 0);
  assert(completion.intensityPercent == 100);

  completion = dashboardCompletionAnimationFrame(500);
  assert(completion.visible);
  assert(completion.ringDegrees == 180);
  assert(completion.providerIconStep == 0);
  assert(completion.successRadius == 0);

  completion = dashboardCompletionAnimationFrame(650);
  assert(completion.providerIconStep == 1);
  completion = dashboardCompletionAnimationFrame(700);
  assert(completion.providerIconStep == 2);
  completion = dashboardCompletionAnimationFrame(750);
  assert(completion.providerIconStep == 3);
  completion = dashboardCompletionAnimationFrame(800);
  assert(completion.providerIconStep == 4);
  completion = dashboardCompletionAnimationFrame(850);
  assert(completion.providerIconStep == -1);
  completion = dashboardCompletionAnimationFrame(999);
  assert(completion.providerIconStep == -1);
  assert(completion.successRadius == 0);

  completion = dashboardCompletionAnimationFrame(1000);
  assert(completion.visible);
  assert(completion.ringDegrees == 360);
  assert(completion.providerIconStep == -1);
  assert(completion.successRadius == 0);

  completion = dashboardCompletionAnimationFrame(1140);
  assert(completion.successRadius == 64);

  completion = dashboardCompletionAnimationFrame(1400);
  assert(completion.successRadius > 58);
  assert(completion.successRadius < kDashboardCompletionFullRadius);

  completion = dashboardCompletionAnimationFrame(1700);
  assert(completion.successRadius == kDashboardCompletionFullRadius);
  assert(completion.intensityPercent == 100);

  completion = dashboardCompletionAnimationFrame(2199);
  assert(completion.visible);
  assert(completion.successRadius == kDashboardCompletionFullRadius);
  assert(completion.intensityPercent == 100);

  completion = dashboardCompletionAnimationFrame(2400);
  assert(completion.visible);
  assert(completion.successRadius == kDashboardCompletionFullRadius);
  assert(completion.intensityPercent == 50);
  assert(!dashboardCompletionAnimationFrame(kDashboardCompletionDurationMs).visible);
  return 0;
}
