import unittest

from bridge.weather import normalize_weather, weather_failure_state, weather_poll_delay


class WeatherTests(unittest.TestCase):
    def test_normalizes_current_suzhou_weather(self):
        value = normalize_weather(
            {"current": {"temperature_2m": 27.4, "weather_code": 0}},
            "苏州",
            now=123,
        )
        self.assertTrue(value["available"])
        self.assertEqual(value["city"], "苏州")
        self.assertEqual(value["temperature_c"], 27.4)
        self.assertEqual(value["label"], "晴")
        self.assertEqual(value["updated_at"], 123)

    def test_rejects_missing_current_conditions(self):
        with self.assertRaises(ValueError):
            normalize_weather({}, "苏州")

    def test_transient_failure_keeps_last_good_conditions_visible(self):
        last = {
            "available": True,
            "city": "苏州",
            "temperature_c": 26.4,
            "weather_code": 1,
            "label": "晴间多云",
            "updated_at": 123,
            "error": "",
        }

        failed = weather_failure_state(last, "苏州", OSError("temporary 503"))

        self.assertTrue(failed["available"])
        self.assertEqual(failed["temperature_c"], 26.4)
        self.assertEqual(failed["error"], "temporary 503")

    def test_first_failure_retries_soon_instead_of_waiting_an_hour(self):
        failed = weather_failure_state({}, "苏州", OSError("temporary 503"))

        self.assertFalse(failed["available"])
        self.assertEqual(weather_poll_delay({}, success=False), 60)
        self.assertEqual(weather_poll_delay({}, success=True), 3600)


if __name__ == "__main__":
    unittest.main()
