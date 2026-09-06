# Bannerlord Culture Validator

Validates that `<Culture>` definitions in a Mount & Blade II: Bannerlord mod carry
all the data they need to work, by resolving every reference they make
(`NPCCharacter.*`, `PartyTemplate.*`, `EquipmentRoster.*`, `BodyProperty.*`,
`Item.*`, ...) against one or more `ModuleData` folders.

Read-only: it only parses XML and prints a report. It never edits your mod files.

## Files

| File | Purpose |
| --- | --- |
| `culture_validator.py` | CLI entry point |
| `object_index.py` | Scans data folders, builds the object/culture index |
| `culture_requirements.py` | The requirement catalog (what each culture type needs) |
| `report.py` | Console + JSON report formatting |
| `checks_config.json` | Priority table — flip checks between `required` / `optional` / `info` / `disabled` |

## Usage

```
python culture_validator.py --data <folder> [<folder> ...] --cultures <file|folder> [options]
```

- `--data FOLDER` — one or more `ModuleData` folders whose objects the cultures
  may reference (repeat the flag or use multiple paths).
- `--cultures PATH` — the XML file containing the `<Culture>` entries to validate
  (or a folder of such files).
- `--config FILE` — priority overrides (defaults to `checks_config.json` if present).
- `--json-report PATH` — where to write the JSON report (default: `culture_validation_report.json` in the current directory).
- `--no-color` — disable ANSI colors.

## Example

Validate your cultures against the base-game data folders:

```
python culture_validator.py `
  --data "C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\SandBoxCore\ModuleData" `
         "C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\SandBox\ModuleData" `
         "C:\MyMod\ModuleData" `
  --cultures "C:\MyMod\ModuleData\spcultures.xml"
```

## What it checks

Each culture is classified as `main` (`is_main_culture="true"`), `minor`
(`can_have_settlement="true"`), `bandit` (`is_bandit="true"`) or `neutral`, and
only the applicable checks run:

- **required** — common attributes, main-culture attributes/template lists,
  settlement attributes, bandit attributes, NPC character references, party
  template references, equipment roster references, body property references,
  item references, name lists, and equipment template categories: every
  `EquipmentCategories` flag set `DefaultEquipmentSelectionModel` selects on
  (Lord, Child, Teen, KingdomRuler, each male + female) must have at least one
  matching `<Flags>` roster, with a Battle and Civilian set for Lord/KingdomRuler
  and a Civilian set for Child/Teen (main cultures only).
- **required (value validity)** — `is_main_culture`/`is_bandit`/`can_have_settlement`
  must be `true`/`false` and the `color`/`color2`/`cloth_alternative_color*`/
  `banner_*_color*` attributes must be valid hex (the game parses these with
  `Convert.ToBoolean` / `Convert.ToUInt32(value, 16)` and crashes on bad values),
  and every `EquipmentRoster` `<Flags>` name must be a real `EquipmentCategories`
  member with a boolean value (`Enum.Parse` / `bool.Parse` crash at load on those).
- **optional** — education character templates, NPC characters and
  body properties tagged with the culture (missing = warning only).
- **info** — default policies, feats / clan banner icons / ship hulls
  (these live in engine code and cannot be resolved against XML).

## Exit codes

- `0` — all required checks passed
- `1` — at least one required check failed (culture missing necessary data)
- `2` — the tool could not run (bad paths, unreadable cultures file)