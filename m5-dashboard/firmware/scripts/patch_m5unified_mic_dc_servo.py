"""Gate M5Unified's fixed-rate microphone DC servo for the 48 kHz USB path.

The StopWatch ES8311 already performs dynamic DC cancellation. M5Unified's
additional fixed 1/32-per-sample servo creates an unwanted high-pass corner at
48 kHz, so the dashboard UAC build disables only that software stage.

Adapted from digitsisyph/codex-micro-stopwatch (MIT), commit
e4f51036ebba21815854e7c427a3f51c2dc10fc1.
"""

from pathlib import Path


Import("env")  # type: ignore[name-defined]  # Provided by PlatformIO/SCons.


libdeps_dir = Path(env.subst("$PROJECT_LIBDEPS_DIR"))  # type: ignore[name-defined]
pio_env = env.subst("$PIOENV")  # type: ignore[name-defined]
source = libdeps_dir / pio_env / "M5Unified" / "src" / "utility" / "Mic_Class.cpp"

if not source.is_file():
    raise RuntimeError(f"M5Unified microphone source is missing: {source}")

original = """        auto value_tmp = (sv0 + sv1) << 3;
        int32_t offset = self->_offset;
        // Automatic zero level adjustment
        offset -= (value_tmp + offset + 16) >> 5;
        self->_offset = offset;
        offset = (offset + 8) >> 4;
        sum_value[0] = sv0 + offset;
        sum_value[1] = sv1 + offset;
"""

patched = """#if defined(M5DASH_DISABLE_M5_MIC_DC_SERVO)
        // The ES8311 hardware dynamic HPF remains enabled. Avoid stacking
        // M5Unified's fixed-per-sample DC servo in the 48 kHz USB path.
        sum_value[0] = sv0;
        sum_value[1] = sv1;
#else
        auto value_tmp = (sv0 + sv1) << 3;
        int32_t offset = self->_offset;
        // Automatic zero level adjustment
        offset -= (value_tmp + offset + 16) >> 5;
        self->_offset = offset;
        offset = (offset + 8) >> 4;
        sum_value[0] = sv0 + offset;
        sum_value[1] = sv1 + offset;
#endif
"""

text = source.read_text(encoding="utf-8")
original_count = text.count(original)
patched_count = text.count(patched)

if patched_count == 1:
    verb = "Verified"
elif original_count == 1:
    source.write_text(text.replace(original, patched, 1), encoding="utf-8")
    verb = "Applied"
else:
    raise RuntimeError(
        "M5Unified microphone source changed unexpectedly: "
        f"original={original_count}, patched={patched_count}, source={source}"
    )

print(f"{verb} dashboard USB-mic DC-servo gate in {source}")
