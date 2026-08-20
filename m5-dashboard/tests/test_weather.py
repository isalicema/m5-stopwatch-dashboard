import unittest

from bridge.weather import normalize_weather


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


if __name__ == "__main__":
    unittest.main()
