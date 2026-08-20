#include <cassert>

#include "../firmware/M5Dashboard/icon_animation.h"
#include "../firmware/M5Dashboard/interaction_logic.h"

int main() {
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

  DashboardPowerButtonState power;
  assert(updateDashboardPowerButton(power, true, 100, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 180, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 679, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 680, 500, 1500) ==
         DashboardPowerAction::toggleStandby);

  power = {};
  assert(updateDashboardPowerButton(power, true, 1000, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 1060, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, true, 1250, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 1310, 500, 1500) ==
         DashboardPowerAction::powerOff);
  assert(updateDashboardPowerButton(power, false, 1800, 500, 1500) ==
         DashboardPowerAction::none);

  power = {};
  assert(updateDashboardPowerButton(power, true, 2000, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 4000, 500, 1500) ==
         DashboardPowerAction::none);

  power = {};
  uint32_t nearWrap = UINT32_MAX - 100;
  assert(updateDashboardPowerButton(power, true, nearWrap, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, nearWrap + 50, 500, 1500) ==
         DashboardPowerAction::none);
  assert(updateDashboardPowerButton(power, false, 449, 500, 1500) ==
         DashboardPowerAction::toggleStandby);

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
  assert(completion.codexFrameIndex == 0);
  assert(completion.claudeIconScalePercent == 141);
  assert(completion.successRadius == 0);
  assert(completion.intensityPercent == 100);

  completion = dashboardCompletionAnimationFrame(500);
  assert(completion.visible);
  assert(completion.ringDegrees == 180);
  assert(completion.codexFrameIndex == 1);
  assert(completion.claudeIconScalePercent == 150);
  assert(completion.successRadius == 0);

  completion = dashboardCompletionAnimationFrame(1000);
  assert(completion.visible);
  assert(completion.ringDegrees == 360);
  assert(completion.successRadius == 0);

  completion = dashboardCompletionAnimationFrame(1140);
  assert(completion.successRadius == 64);

  completion = dashboardCompletionAnimationFrame(1400);
  assert(completion.successRadius > 58);
  assert(completion.successRadius < kDashboardCompletionFullRadius);

  completion = dashboardCompletionAnimationFrame(1700);
  assert(completion.successRadius == kDashboardCompletionFullRadius);
  assert(completion.intensityPercent == 100);

  completion = dashboardCompletionAnimationFrame(1900);
  assert(completion.visible);
  assert(completion.successRadius == kDashboardCompletionFullRadius);
  assert(completion.intensityPercent == 33);
  assert(!dashboardCompletionAnimationFrame(kDashboardCompletionDurationMs).visible);
  return 0;
}
