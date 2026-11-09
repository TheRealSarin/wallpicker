import os
import tempfile
import unittest

from wallpicker.commands import build
from wallpicker.library import cover_crop, list_wallpapers, read_state, thumbnail_key, write_state


class ListWallpapersTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = self.directory.name
        for name in ("b.PNG", "a.jpg", "notes.txt", "sub/c.webp", ".hidden/d.jpg"):
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()

    def names(self, recursive):
        return [os.path.relpath(p, self.directory.name) for p in list_wallpapers(self.directory.name, recursive)]

    def test_recursive_skips_hidden_and_non_images(self):
        self.assertEqual(self.names(True), ["a.jpg", "b.PNG", "sub/c.webp"])

    def test_flat_listing(self):
        self.assertEqual(self.names(False), ["a.jpg", "b.PNG"])

    def test_missing_directory(self):
        self.assertEqual(list_wallpapers(os.path.join(self.directory.name, "nope")), [])


class StateTest(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "nested", "current")
            self.assertEqual(read_state(path), "")
            write_state(path, "/walls/a.jpg")
            self.assertEqual(read_state(path), "/walls/a.jpg")


class CoverCropTest(unittest.TestCase):
    def test_wide_image_is_cropped_horizontally(self):
        self.assertEqual(cover_crop(3840, 1080, 288, 162), (576, 162, 144, 0))

    def test_tall_image_is_cropped_vertically(self):
        self.assertEqual(cover_crop(1080, 1920, 288, 162), (288, 512, 0, 175))

    def test_exact_ratio_needs_no_crop(self):
        self.assertEqual(cover_crop(1920, 1080, 288, 162), (288, 162, 0, 0))


class ThumbnailKeyTest(unittest.TestCase):
    def test_changes_with_inputs(self):
        base = thumbnail_key("/a.jpg", 1, 288, 162)
        self.assertNotEqual(base, thumbnail_key("/a.jpg", 2, 288, 162))
        self.assertNotEqual(base, thumbnail_key("/a.jpg", 1, 300, 162))
        self.assertEqual(base, thumbnail_key("/a.jpg", 1, 288, 162))


class BuildCommandTest(unittest.TestCase):
    def test_list_substitutes_path(self):
        self.assertEqual(build(["awww", "img", "{path}"], "/w/a b.jpg"), ["awww", "img", "/w/a b.jpg"])

    def test_list_expands_home_in_program(self):
        self.assertEqual(build(["~/set.sh", "{path}"], "/a")[0], os.path.expanduser("~/set.sh"))

    def test_string_runs_through_shell_with_quoting(self):
        self.assertEqual(build("swww img {path}", "/w/it's.jpg"), ["sh", "-c", "swww img '/w/it'\"'\"'s.jpg'"])


if __name__ == "__main__":
    unittest.main()
