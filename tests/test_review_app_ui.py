from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT_DIR = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT_DIR / "tests" / "review_app_harness.py"


def find_button(at: AppTest, label: str):
    for button in at.button:
        if button.label == label:
            return button
    raise AssertionError(f"Button not found: {label}")


def header_values(at: AppTest) -> list[str]:
    return [item.value for item in at.header]


def subheader_values(at: AppTest) -> list[str]:
    return [item.value for item in at.subheader]


class ReviewAppUiTest(unittest.TestCase):
    def test_workflow_buttons_navigate_sections(self) -> None:
        at = AppTest.from_file(str(HARNESS_PATH), default_timeout=15)
        at.run()

        self.assertIn("Extend images", subheader_values(at))
        self.assertIn("Extend board", header_values(at))

        find_button(at, "2. Build sequence").click()
        at.run()
        self.assertIn("Build movie", subheader_values(at))
        self.assertIn("Build board", header_values(at))

        find_button(at, "3. Review clips").click()
        at.run()
        self.assertIn("Review Run", header_values(at))
        self.assertTrue(any(" | " in value for value in subheader_values(at)))

        find_button(at, "4. Retry weak clips").click()
        at.run()
        self.assertIn("Redo queue", subheader_values(at))
        self.assertIn("Retry board", header_values(at))

        find_button(at, "1. Extend stills").click()
        at.run()
        self.assertIn("Extend images", subheader_values(at))
        self.assertIn("Extend board", header_values(at))

    def test_build_generation_controls_are_dry_and_responsive(self) -> None:
        at = AppTest.from_file(str(HARNESS_PATH), default_timeout=40)
        at.run()

        find_button(at, "2. Build sequence").click()
        at.run()

        self.assertIn("Build movie", subheader_values(at))
        at.checkbox(key="build_use_kling::D:/Programming/olga_movie/Olia_continue/extend_api").set_value(True)
        at.run()

        find_button(at, "Generate clips").click()
        at.run()

        self.assertTrue(any(item.value == "Started Kling generation for 4 pair(s). Watch the progress card below." for item in at.success))
        self.assertIsNotNone(find_button(at, "Refresh progress"))
        self.assertIsNotNone(find_button(at, "Stop current run"))

        find_button(at, "Stop current run").click()
        at.run()

        self.assertTrue(any("Requested stop for the current Kling build run." == item.value for item in at.success))


if __name__ == "__main__":
    unittest.main()
