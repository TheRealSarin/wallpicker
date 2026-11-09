import os
import tempfile
import unittest

from wallpicker.config import Config, ConfigError, apply_overrides, load_config, parse_color


class ParseColorTest(unittest.TestCase):
    def test_rgb_is_opaque(self):
        self.assertEqual(parse_color("#ff0000"), (1.0, 0.0, 0.0, 1.0))

    def test_rgba_keeps_alpha(self):
        self.assertAlmostEqual(parse_color("#00000080")[3], 128 / 255)

    def test_rejects_bad_values(self):
        for value in ("red", "#fff", "#gg0000", "", 123):
            with self.assertRaises(ConfigError):
                parse_color(value)


class ApplyOverridesTest(unittest.TestCase):
    def test_empty_table_keeps_defaults(self):
        self.assertEqual(apply_overrides(Config(), {}), Config())

    def test_overrides_known_options(self):
        config = apply_overrides(Config(), {
            "general": {"directory": "~/walls", "live_preview": False},
            "layout": {"visible": 3, "position": "top"},
            "appearance": {"selection": "#ff000080", "dim": 1},
        })
        self.assertEqual(config.general.directory, "~/walls")
        self.assertFalse(config.general.live_preview)
        self.assertEqual(config.layout.visible, 3)
        self.assertEqual(config.layout.position, "top")
        self.assertEqual(config.appearance.dim, 1.0)
        self.assertIsInstance(config.appearance.dim, float)
        self.assertEqual(config.layout.margin, Config().layout.margin)

    def test_commands_accept_strings_and_lists(self):
        config = apply_overrides(Config(), {"commands": {"preview": "swww img {path}", "apply": ["x", "{path}"]}})
        self.assertEqual(config.commands.preview, "swww img {path}")
        self.assertEqual(config.commands.apply, ["x", "{path}"])

    def test_keys_accept_a_single_name(self):
        config = apply_overrides(Config(), {"keys": {"apply": "Return"}})
        self.assertEqual(config.keys.apply, ("Return",))

    def test_rejects_invalid_input(self):
        cases = [
            ["general"],
            {"colours": {}},
            {"general": {"nope": 1}},
            {"general": "x"},
            {"general": {"recursive": "yes"}},
            {"layout": {"visible": 0}},
            {"layout": {"margin": True}},
            {"layout": {"position": "left"}},
            {"appearance": {"dim": 2}},
            {"appearance": {"border": "blue"}},
            {"commands": {"apply": []}},
            {"commands": {"apply": [1]}},
            {"keys": {"next": [""]}},
        ]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ConfigError):
                apply_overrides(Config(), data)


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def write(self, text):
        path = os.path.join(self.directory.name, "config.toml")
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def test_reads_toml(self):
        path = self.write('[layout]\nvisible = 7\n')
        self.assertEqual(load_config(path).layout.visible, 7)

    def test_missing_explicit_file_is_an_error(self):
        with self.assertRaises(ConfigError):
            load_config(os.path.join(self.directory.name, "missing.toml"))

    def test_missing_default_file_gives_defaults(self):
        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.directory.name
        try:
            self.assertEqual(load_config().layout, Config().layout)
        finally:
            if old is None:
                del os.environ["XDG_CONFIG_HOME"]
            else:
                os.environ["XDG_CONFIG_HOME"] = old

    def test_syntax_errors_are_reported(self):
        with self.assertRaises(ConfigError):
            load_config(self.write("[layout\n"))

    def test_shipped_example_is_valid(self):
        example = os.path.join(os.path.dirname(__file__), "..", "examples", "config.toml")
        self.assertEqual(load_config(example).layout, Config().layout)


if __name__ == "__main__":
    unittest.main()
