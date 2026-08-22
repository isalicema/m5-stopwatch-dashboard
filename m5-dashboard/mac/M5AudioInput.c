#include <CoreAudio/CoreAudio.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
  return CFStringCompare(name, CFSTR("TinyUSB UAC1"), 0) == kCFCompareEqualTo ||
         CFStringCompare(name, CFSTR("M5 StopWatch Mic"), 0) == kCFCompareEqualTo;
}

static bool is_builtin(AudioObjectID device) {
  AudioObjectPropertyAddress address = {
      kAudioDevicePropertyTransportType,
      kAudioObjectPropertyScopeGlobal,
      kAudioObjectPropertyElementMain,
  };
  UInt32 transport = 0;
  UInt32 size = sizeof(transport);
  return AudioObjectGetPropertyData(device, &address, 0, NULL, &size,
                                    &transport) == noErr &&
         transport == kAudioDeviceTransportTypeBuiltIn;
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

static AudioObjectID find_fallback(void) {
  AudioObjectPropertyAddress address = {
      kAudioHardwarePropertyDevices,
      kAudioObjectPropertyScopeGlobal,
      kAudioObjectPropertyElementMain,
  };
  UInt32 size = 0;
  if (AudioObjectGetPropertyDataSize(kAudioObjectSystemObject, &address, 0, NULL,
                                     &size) != noErr) {
    return kAudioObjectUnknown;
  }
  AudioObjectID *devices = malloc(size);
  if (devices == NULL) return kAudioObjectUnknown;
  AudioObjectID first = kAudioObjectUnknown;
  AudioObjectID found = kAudioObjectUnknown;
  if (AudioObjectGetPropertyData(kAudioObjectSystemObject, &address, 0, NULL,
                                 &size, devices) == noErr) {
    size_t count = size / sizeof(AudioObjectID);
    for (size_t index = 0; index < count; ++index) {
      AudioObjectID device = devices[index];
      if (!has_input(device) || is_m5(device)) continue;
      if (first == kAudioObjectUnknown) first = device;
      if (is_builtin(device)) {
        found = device;
        break;
      }
    }
  }
  free(devices);
  return found != kAudioObjectUnknown ? found : first;
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

static bool set_default_input(AudioObjectID target) {
  if (target == kAudioObjectUnknown || !has_input(target)) return false;
  AudioObjectPropertyAddress address = {
      kAudioHardwarePropertyDefaultInputDevice,
      kAudioObjectPropertyScopeGlobal,
      kAudioObjectPropertyElementMain,
  };
  return AudioObjectSetPropertyData(kAudioObjectSystemObject, &address, 0, NULL,
                                    sizeof(target), &target) == noErr;
}

static bool select_m5(AudioObjectID *previous) {
  AudioObjectID target = find_m5();
  if (target == kAudioObjectUnknown) return false;
  *previous = default_input();
  if (*previous == kAudioObjectUnknown) return false;
  return *previous == target || set_default_input(target);
}

int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1], "capture") == 0) {
    AudioObjectID previous = kAudioObjectUnknown;
    if (!select_m5(&previous)) return 1;
    printf("%u\n", (unsigned int)previous);
    return 0;
  }
  if (argc == 3 && strcmp(argv[1], "restore") == 0) {
    char *end = NULL;
    unsigned long value = strtoul(argv[2], &end, 10);
    if (end == argv[2] || *end != '\0' || value > UINT32_MAX) return 64;
    return set_default_input((AudioObjectID)value) ? 0 : 1;
  }
  if (argc == 2 && strcmp(argv[1], "release") == 0) {
    AudioObjectID current = default_input();
    if (current == kAudioObjectUnknown) return 1;
    if (!is_m5(current)) return 0;
    return set_default_input(find_fallback()) ? 0 : 1;
  }
  fputs("Usage: m5_audio_input capture | restore DEVICE_ID | release\n", stderr);
  return 64;
}
