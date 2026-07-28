#!/usr/bin/env python3
"""Repo-level invariants that no single skill's test suite would catch.

Two failure modes are guarded here, both of which have actually happened:

1. A SKILL.md loses or malforms its frontmatter. The skill host discovers skills
   by that frontmatter, so the skill goes silently undiscoverable -- it does not
   error, it just stops existing.

2. The README and CLAUDE.md tables drift from the directories on disk. They
   carried `outlook` and `trello` rows for weeks after those skills moved to
   their own repos, and CLAUDE.md explicitly asks for the tables to be kept in
   sync -- an instruction that until now nothing enforced.

Deliberately not enforced: table *ordering* or per-row wording. This checks that
every skill is mentioned in each table and that no table mentions a skill that
does not exist, so the tables can be rewritten freely without tripping CI.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
CLAUDE_MD = REPO / "CLAUDE.md"

# Directories that live alongside the skills but are not skills themselves,
# plus the repo root label that heads the CLAUDE.md structure tree.
NON_SKILL_DIRS = {"docs", "tests", "plans", "claude-skills", ".github", ".git", ".claude"}


def skill_dirs() -> list[Path]:
    return sorted(p.parent for p in REPO.glob("*/SKILL.md"))


def skill_names() -> list[str]:
    return [p.name for p in skill_dirs()]


def parse_frontmatter(path: Path) -> dict:
    """Parse the leading --- fenced YAML block.

    Hand-rolled rather than via PyYAML so this suite stays stdlib-only: it is the
    one test job that must run before any skill's dependencies are installed.
    Only the flat `key: value` form the skill format actually uses is supported.
    """
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        header = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if header:
            key = header.group(1)
            fields[key] = header.group(2).strip().strip('"').strip("'")
        elif key and line.startswith((" ", "\t")):
            # Folded continuation line.
            fields[key] = f"{fields[key]} {line.strip()}".strip()
    return fields


def section_body(text: str, heading: str) -> str:
    """Return the body between the heading titled `heading` and the next heading.

    Matched on the heading's *exact* text once emoji and punctuation are stripped,
    not on containment. Containment picks the wrong section: the README's
    "Claude and Codex Skills" <h1> contains "Skills", so a loose match returns the
    badge block instead of the skills table and every assertion below then fails
    for the wrong reason.
    """
    headings = list(re.finditer(r"^(#+)[ \t]*([^\n]*)$", text, re.MULTILINE))
    target = heading.casefold()
    for i, match in enumerate(headings):
        title = re.sub(r"[^\w\s-]", "", match.group(2)).strip().casefold()
        if title == target:
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            return text[match.end():end]
    return ""


def mentions(section: str, skill: str) -> bool:
    """True if `section` names `skill`, by directory name or by display name.

    The tables are written for humans -- "PST to Markdown", "GPT Image 2" -- so a
    plain directory-name search would fail on rows that are perfectly correct.
    Hyphens are treated as spaces and case is ignored.
    """
    haystack = re.sub(r"[\s-]+", " ", section).casefold()
    return re.sub(r"[\s-]+", " ", skill).casefold() in haystack


class TestSkillDiscovery(unittest.TestCase):

    def test_repo_has_skills(self):
        # Guards the rest of this file: every other assertion loops over this
        # list, so an empty list would make the whole suite vacuously green.
        self.assertGreater(len(skill_dirs()), 0, "no */SKILL.md found")

    def test_every_skill_dir_has_a_readme_or_is_documented(self):
        for path in skill_dirs():
            with self.subTest(skill=path.name):
                self.assertTrue(
                    (path / "SKILL.md").is_file(),
                    f"{path.name}/SKILL.md is not a regular file",
                )


class TestFrontmatter(unittest.TestCase):

    def test_frontmatter_block_is_present_and_parses(self):
        for path in skill_dirs():
            with self.subTest(skill=path.name):
                fields = parse_frontmatter(path / "SKILL.md")
                self.assertTrue(
                    fields,
                    f"{path.name}/SKILL.md has no parseable --- frontmatter block",
                )

    def test_name_and_description_are_present_and_non_empty(self):
        for path in skill_dirs():
            with self.subTest(skill=path.name):
                fields = parse_frontmatter(path / "SKILL.md")
                for field in ("name", "description"):
                    self.assertIn(field, fields, f"{path.name}: missing '{field}'")
                    self.assertTrue(
                        fields[field].strip(),
                        f"{path.name}: '{field}' is empty",
                    )

    def test_name_matches_directory(self):
        for path in skill_dirs():
            with self.subTest(skill=path.name):
                fields = parse_frontmatter(path / "SKILL.md")
                self.assertEqual(
                    fields.get("name"), path.name,
                    f"{path.name}/SKILL.md declares name '{fields.get('name')}'",
                )

    def test_description_is_substantial_enough_to_route_on(self):
        # The host matches user intent against this string. A stub description
        # means the skill never triggers.
        for path in skill_dirs():
            with self.subTest(skill=path.name):
                description = parse_frontmatter(path / "SKILL.md")["description"]
                self.assertGreaterEqual(
                    len(description), 40,
                    f"{path.name}: description is too short to route on",
                )


class TestInstallerParity(unittest.TestCase):
    """The shell suite checks this too; repeated here so a Python-only run catches it."""

    def available_skills(self, installer: Path) -> set[str]:
        match = re.search(
            r"^AVAILABLE_SKILLS=\((.*?)\)\s*$",
            installer.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        self.assertIsNotNone(match, f"{installer.name}: no AVAILABLE_SKILLS array")
        return set(match.group(1).split())

    def test_both_installers_offer_every_skill(self):
        expected = set(skill_names())
        for installer in ("install.sh", "install-codex.sh"):
            with self.subTest(installer=installer):
                self.assertEqual(self.available_skills(REPO / installer), expected)


class TestReadmeTables(unittest.TestCase):
    """CLAUDE.md asks for these tables to be kept in sync. This is that check."""

    @classmethod
    def setUpClass(cls):
        cls.readme = README.read_text(encoding="utf-8")

    def test_skills_table_lists_every_skill(self):
        section = section_body(self.readme, "Skills")
        for name in skill_names():
            with self.subTest(skill=name):
                self.assertIn(f"./{name}/", section, f"README Skills table omits {name}")

    def test_credentials_table_lists_every_skill(self):
        section = section_body(self.readme, "Credentials")
        for name in skill_names():
            with self.subTest(skill=name):
                self.assertTrue(mentions(section, name), f"README Credentials table omits {name}")

    def test_requirements_table_lists_every_skill(self):
        section = section_body(self.readme, "Requirements")
        for name in skill_names():
            with self.subTest(skill=name):
                self.assertTrue(mentions(section, name), f"README Requirements table omits {name}")

    def test_no_table_links_to_a_directory_that_does_not_exist(self):
        # The outlook/trello failure: rows outliving the directories they point at.
        # The Moved note deliberately links to the external repos by URL, not by
        # relative path, so it is not matched here.
        for link in re.findall(r"\]\(\./([^)/]+)/\)", self.readme):
            with self.subTest(link=link):
                self.assertTrue(
                    (REPO / link).is_dir(),
                    f"README links to ./{link}/ which does not exist",
                )


class TestClaudeMdTables(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.claude_md = CLAUDE_MD.read_text(encoding="utf-8")

    def test_structure_tree_lists_every_skill(self):
        section = section_body(self.claude_md, "Repository Structure")
        for name in skill_names():
            with self.subTest(skill=name):
                self.assertIn(
                    f"{name}/", section,
                    f"CLAUDE.md structure tree omits {name}",
                )

    def test_credentials_table_lists_every_skill(self):
        section = section_body(self.claude_md, "Credentials")
        for name in skill_names():
            with self.subTest(skill=name):
                self.assertTrue(mentions(section, name), f"CLAUDE.md credentials table omits {name}")

    def test_structure_tree_has_no_stale_skill_entries(self):
        section = section_body(self.claude_md, "Repository Structure")
        known = set(skill_names()) | NON_SKILL_DIRS
        listed = set(re.findall(r"^[│├└─\s]*([a-z0-9][\w-]*)/", section, re.MULTILINE))
        for name in listed - known:
            with self.subTest(entry=name):
                self.assertTrue(
                    (REPO / name).exists(),
                    f"CLAUDE.md structure tree lists '{name}/' which does not exist",
                )


if __name__ == "__main__":
    unittest.main()
