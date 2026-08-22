from __future__ import annotations

import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

from bridge.obsidian_dice import DEFAULT_POOLS, ObsidianDice, scan_notes


class ObsidianDiceTests(unittest.TestCase):
    def test_scan_is_limited_to_roots_and_excludes_alice_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            (root / "Insights").mkdir(parents=True)
            (root / "Alice Writing").mkdir()
            (root / "Insights/note.md").write_text("# 把控制编进拓扑\n正文", encoding="utf-8")
            (root / "Alice Writing/private.md").write_text("# 私密", encoding="utf-8")

            notes = scan_notes([root], ["Alice Writing"])
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0].title, "把控制编进拓扑")
            self.assertEqual(notes[0].folder, "Smart Workspace · Insights")

    def test_roll_and_open_use_only_indexed_note(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            root.mkdir()
            note = root / "note.md"
            note.write_text("---\ntitle: 幸运笔记\n---\n内容", encoding="utf-8")
            opened = []
            published = []
            dice = ObsidianDice(
                {
                    "roots": [str(root)],
                    "pools": [{"name": "测试池", "weight": 1, "folders": ["."]}],
                },
                published.append,
                chooser=lambda values: values[0],
                launcher=opened.append,
            )
            dice.refresh()
            state = dice.roll()
            self.assertEqual(state["available_count"], 1)
            self.assertEqual(state["selected"]["title"], "幸运笔记")
            self.assertNotIn("excerpt", state["selected"])
            dice.open_selected()
            self.assertEqual(opened, [note.resolve()])

    def test_device_title_removes_unsupported_emoji_and_normalises_dashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            root.mkdir()
            (root / "note.md").write_text("# 🌱 RabbitT — 灵感", encoding="utf-8")
            dice = ObsidianDice(
                {
                    "roots": [str(root)],
                    "pools": [{"name": "测试池", "weight": 1, "folders": ["."]}],
                },
                lambda _state: None,
                chooser=lambda values: values[0],
            )
            dice.refresh()
            self.assertEqual(dice.roll()["selected"]["title"], "RabbitT - 灵感")

    @patch("bridge.obsidian_dice.subprocess.run")
    def test_default_launcher_uses_checked_obsidian_uri(self, run):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            root.mkdir()
            note = root / "带 空格.md"
            note.write_text("# 标题", encoding="utf-8")
            dice = ObsidianDice(
                {
                    "roots": [str(root)],
                    "pools": [{"name": "测试池", "weight": 1, "folders": ["."]}],
                },
                lambda _state: None,
                chooser=lambda values: values[0],
            )
            dice.refresh()
            dice.roll()
            dice.open_selected()
            command = run.call_args.args[0]
            self.assertEqual(command[0], "/usr/bin/open")
            self.assertTrue(command[1].startswith("obsidian://open?path="))
            self.assertIn("%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.md", command[1])
            self.assertTrue(run.call_args.kwargs["check"])

    def test_creation_is_default_off_but_can_opt_in_one_note(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            for folder in ("rabbitT dream", "Codex Report"):
                (root / folder).mkdir(parents=True)
                (root / folder / "note.md").write_text(
                    "---\nlucky: true\n---\n# %s" % folder, encoding="utf-8"
                )
            (root / "RabbitT Creation").mkdir(parents=True)
            (root / "RabbitT Creation/default-off.md").write_text(
                "# 默认不抽", encoding="utf-8"
            )
            (root / "RabbitT Creation/selected.md").write_text(
                "---\nlucky: true\n---\n# 手动加入", encoding="utf-8"
            )

            notes = scan_notes([root], [], pools=DEFAULT_POOLS)
            by_folder = {note.folder_key: note for note in notes if note.pool != "手动精选"}
            self.assertEqual(set(by_folder), {"rabbitT dream", "Codex Report"})
            self.assertEqual(by_folder["rabbitT dream"].pool, "灵感探索")
            self.assertEqual(by_folder["rabbitT dream"].folder_weight, 0.35)
            self.assertEqual(by_folder["Codex Report"].folder_weight, 0.25)
            creation = [note for note in notes if note.folder_key == "RabbitT Creation"]
            self.assertEqual([note.title for note in creation], ["手动加入"])
            self.assertEqual(creation[0].pool, "手动精选")

    def test_lucky_frontmatter_can_opt_in_or_out_without_crossing_hard_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            (root / "Insights").mkdir(parents=True)
            (root / "Unlisted").mkdir()
            (root / "Alice Writing").mkdir()
            (root / "Insights/no.md").write_text("---\nlucky: false\n---\n# 不抽", encoding="utf-8")
            (root / "Unlisted/yes.md").write_text("---\nlucky: true\n---\n# 手选", encoding="utf-8")
            (root / "Alice Writing/private.md").write_text(
                "---\nlucky: true\n---\n# 私密", encoding="utf-8"
            )

            notes = scan_notes([root], [], pools=DEFAULT_POOLS)
            self.assertEqual([note.title for note in notes], ["手选"])
            self.assertEqual(notes[0].pool, "手动精选")

    def test_roll_uses_pool_then_folder_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            for folder in ("Insights", "Codex Report"):
                (root / folder).mkdir(parents=True)
                (root / folder / "note.md").write_text("# %s" % folder, encoding="utf-8")
            dice = ObsidianDice(
                {"roots": [str(root)]},
                lambda _state: None,
                chooser=lambda values: values[0],
                random_value=lambda: 0.99,
            )
            dice.refresh()
            state = dice.roll()
            self.assertEqual(state["selected"]["pool"], "灵感探索")
            self.assertEqual(state["selected"]["relative_path"], "Codex Report/note.md")
            self.assertEqual(state["selected"]["reason"], "灵感探索")

    def test_cooldown_and_history_persist_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            folder = root / "Insights"
            folder.mkdir(parents=True)
            (folder / "a.md").write_text("# A", encoding="utf-8")
            (folder / "b.md").write_text("# B", encoding="utf-8")
            state_path = Path(directory) / "dice-state.json"
            config = {
                "roots": [str(root)],
                "state_path": str(state_path),
                "cooldown_count": 30,
            }
            first = ObsidianDice(config, lambda _state: None, chooser=lambda values: values[0])
            first.refresh()
            first_roll = first.roll()["selected"]["id"]

            second = ObsidianDice(config, lambda _state: None, chooser=lambda values: values[0])
            second.refresh()
            second_roll = second.roll()["selected"]["id"]
            self.assertNotEqual(first_roll, second_roll)
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(len(persisted["recent_ids"]), 2)

    def test_open_rejects_note_removed_after_roll(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Smart Workspace"
            folder = root / "Insights"
            folder.mkdir(parents=True)
            note = folder / "gone.md"
            note.write_text("# Gone", encoding="utf-8")
            dice = ObsidianDice(
                {"roots": [str(root)]},
                lambda _state: None,
                chooser=lambda values: values[0],
                launcher=lambda _path: self.fail("launcher should not run"),
            )
            dice.refresh()
            dice.roll()
            note.unlink()
            with self.assertRaisesRegex(ValueError, "no longer available"):
                dice.open_selected()


if __name__ == "__main__":
    unittest.main()
