---
name: lab-member-manager
description: >-
  Extracts member profiles, research topics, and embedded photos from Excel intake templates (*.xlsm / *.xlsx),
  crops profile images to 1:1, cleans duplicate role/program text, and synchronizes both Thai (data/th/people.json)
  and English (data/en/people.json) datasets for the lab portfolio website.
---

# Lab Member Manager

## Overview

Automates the intake workflow for lab members (Current Team, Current Advisees, and Alumni) from the standardized Excel intake template (`ONTHAI-Lab-Member-Intake-Template.xlsm` / `*.xlsx`) into the lab website portfolio.

It performs:
1. **Excel Parsing**: Reads row data from the sheet `ข้อมูลเผยแพร่` (Name, Role, Program, Degree, Topic, Period, Status).
2. **Embedded Photo Extraction**: Extracts original profile pictures embedded in the Excel worksheet (`xl/media/image*.jpg/png`) via drawing anchor relationships.
3. **Square Crop (1:1)**: Centers and crops images to a 1:1 aspect ratio (`sips --cropToHeightWidth`) so they display properly in circular avatars without distortion.
4. **Text Normalization**: Eliminates redundant program/degree text between the `role` and `program` fields.
5. **Bilingual Sync**: Updates both `data/th/people.json` and `data/en/people.json` in their appropriate group (`current-team`, `current-advisees`, or `alumni`).

---

## Dependencies

- Python 3 (standard libraries: `zipfile`, `xml.etree.ElementTree`, `json`, `re`, `argparse`)
- macOS `sips` command-line image tool (built into macOS)

---

## Quick Start

Whenever a new member fills in the intake template or an updated Excel file is placed in the project root:

```bash
# Preview what will be imported/updated
python3 .agents/skills/lab-member-manager/scripts/sync_members.py --dry-run

# Run full synchronization and photo extraction
python3 .agents/skills/lab-member-manager/scripts/sync_members.py
```

To specify an explicit Excel file path:
```bash
python3 .agents/skills/lab-member-manager/scripts/sync_members.py --file path/to/template.xlsm
```

---

## Utility Scripts

### `sync_members.py`
Located at: `.agents/skills/lab-member-manager/scripts/sync_members.py`

#### Arguments:
- `--file` / `-f`: Path to the intake Excel workbook (`.xlsm` or `.xlsx`). If omitted, auto-discovers `*Member-Intake*.xlsm` or `*ONTHAI*.xlsm` in the workspace root.
- `--dry-run`: Parses and displays all member rows and media targets without writing changes to disk.

---

## Workflow Protocol

When the user asks to add or update lab members:
1. Check the workspace root for `*Intake*.xlsm` or `*Intake*.xlsx`.
2. Run `python3 .agents/skills/lab-member-manager/scripts/sync_members.py` to extract images and update JSON files.
3. Verify that the new member entry appears in both `data/th/people.json` and `data/en/people.json`.
4. Check that the image in `assets/people/<name>.jpg` is a 1:1 square centered on the face.
5. Inform the user of the new additions and their display category.

---

## Common Mistakes & Troubleshooting

- **Exporting to `.csv` instead of `.xlsm`:** CSV is plain text and silently discards all embedded images. Always inspect the `.xlsm` or `.xlsx` workbook directly for images.
- **Redundant Titles:** Avoid having the degree acronym in both `role` and `program` (e.g. use "นักศึกษาปริญญาตรี" in role rather than "นักศึกษาปริญญาตรี (สบ. สาธารณสุขชุมชน)" when program already states "สาธารณสุขศาสตรบัณฑิต สาขาสาธารณสุขชุมชน").
- **Image Aspect Ratio:** Raw phone camera photos are often 4:3 or 16:9. The script crops them to 1:1 square to prevent head-stretching in CSS `border-radius: 9999px` circular containers.
