#include <CoreAudio/CoreAudio.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static bool has_input(AudioObjectID device) {
  AudioObjectPropertyAddress address = {
      kAudioDevicePropertyStreamConfiguration,
      kAudioDevicePropertyScopeInput,
      kAudioObjectPropertyElementMain,
  };
  UInt32 size = 0;
  if (AudioObjectGetPropertyDataSize(device, &address, 0, NULL, &size) != noErr ||
      size < sizeof(AudioBufferList)) {
    return false;
  }
  AudioBufferList *list = malloc(size);
  if (list == NULL) return false;
  bool result = false;
  if (AudioObjectGetPropertyData(device, &address, 0, NULL, &size, list) == noErr) {
    for (UInt32 index = 0; index < list->mNumberBuffers; ++index) {
      if (list->mBuffers[index].mNumberChannels > 0) {
        result = true;
        break;
      }
    }
  }
  free(list);
  return result;
}

static bool is_m5(AudioObjectID device) {
  AudioObjectPropertyAddress address = {
      kAudioObjectPropertyName,
      kAudioObjectPropertyScopeGlobal,
      kAudioObjectPropertyElementMain,
  };
  CFStringRef name = NULL;
  UInt32 size = sizeof(name);
  if (AudioObjectGetPropertyData(device, &address, 0, NULL, &size, &name) != noErr ||
      name == NULL) {
    return false;
  }
  return CFStringCompare(name, CFSTR("TinyUSB UAC1"), 0) == kCFCompareEqualTo;
}

static AudioObjectID find_m5(void) {
  AudioObjectPropertyAddress address = {
      kAudioHardwarePropertyDevices,
      kAudioObjectPropertyScopeGlobal,
      kAudioObjectPropertyElementMain,
  };
  AudioObjectID system = kAudioObjectSystemObject;
  UInt32 size = 0;
  if (AudioObjectGetPropertyDataSize(system, &address, 0, NULL, &size) != noErr) {
    return kAudioObjectUnknown;
  }
  AudioObjectID *devices = malloc(size);
  if (devices == NULL) return kAudioObjectUnknown;
  AudioObjectID found = kAudioObjectUnknown;
  if (AudioObjectGetPropertyData(system, &address, 0, NULL, &size, devices) == noErr) {
    size_t count = size / sizeof(AudioObjectID);
    for (size_t index = 0; index < count; ++index) {
      if (has_input(devices[index]) && is_m5(devices[index])) {
        found = devices[index];
        break;
      }
    }
  }
  free(devices);
  return found;
}

static AudioObjectID default_input(void) {
  AudioObjectPropertyAddress address = {
      kAudioHardwarePropertyDefaultInputDevice,
      kAudioObjectPropertyScopeGlobal,
      kAudioObjectPropertyElementMain,
  };
  AudioObjectID device = kAudioObjectUnknown;
  UInt32 size = sizeof(device);
  if (AudioObjectGetPropertyData(kAudioObjectSystemObject, &address, 0, NULL, &size,
                                 &device) != noErr) {
    return kAudioObjectUnknown;
  }
  return device;
}

static bool select_m5(void) {
  AudioObjectID target = find_m5();
  if (target == kAudioObjectUnknown) return false;
  if (default_input() == target) return true;
  AudioObjectPropertyAddress address = {
      kAudioHardwarePropertyDefaultInputDevice,
      kAudioObjectPropertyScopeGlobal,
      kAudioObjectPropertyElementMain,
  };
  OSStatus status = AudioObjectSetPropertyData(
      kAudioObjectSystemObject, &address, 0, NULL, sizeof(target), &target);
  if (status == noErr) {
    puts("M5 microphone selected");
    fflush(stdout);
    return true;
  }
  return false;
}

int main(int argc, char **argv) {
  bool watch = argc > 1 && strcmp(argv[1], "--watch") == 0;
  do {
    bool selected = select_m5();
    if (!watch) return selected ? 0 : 1;
    sleep(2);
  } while (true);
}
