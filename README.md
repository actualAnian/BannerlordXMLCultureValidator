# Bannerlord Culture Validator

Validates that `<Culture>` definitions in a Mount & Blade II: Bannerlord mod carry
all the data they need to work, by resolving every reference they make
(`NPCCharacter.*`, `PartyTemplate.*`, `EquipmentRoster.*`, `BodyProperty.*`,
`Item.*`, string IDs, ...) against one or more `ModuleData` folders.

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
### if using .exe from releases -
```
CultureValidator.exe --data [<folder> ...] --cultures <file with cultures defined |folder containing the culture .xml> [options]
```
### if downloaded from repo
```
python culture_validator.py --data [<folder> ...] --cultures <file with cultures defined |folder containing the culture .xml> [options]
```
## Options
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
         "C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\Native\ModuleData" `
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
- **required (NPC occupations)** — each NPCCharacter role referenced by the culture
  must have the correct `occupation` attribute in `spnpccharacters.xml` (e.g.
  `townsman` requires `occupation="Townsfolk"`). Wrong values cause incorrect
  hero behavior in-game.
- **required (notable template coverage)** — each main culture's `notable_templates`
  must include at least one template for each expected occupation type (Merchant,
  Artisan, Preacher, GangLeader, RuralNotable, Headman). Missing types mean the
  game cannot spawn that notable type in settlements.
- **required (character creation)** — `CharacterCreationCampaignBehavior.cs`
  constructs equipment roster IDs at runtime. Universal templates
  (`retainer`/`farmer` for parents, `guard`/`infantry` for the player) and the
  `player_char_creation_default` fallback must exist in the data folders.
- **required (culture strings)** — `GameTexts.FindText()` looks up
  `str_culture_description`, `str_culture_rich_name`, `str_faction_official`,
  `str_faction_ruler`, `str_faction_ruler_name_with_title`,
  `str_faction_noble_name_with_title`, `str_faction_formal_name_for_culture`,
  `str_faction_informal_name_for_culture`, `str_adjective_for_culture`, and
  `str_neutral_term_for_culture` (male + female variants where applicable) for
  each culture. Missing strings cause crashes or `ERROR_MISSING_NAME` in the UI.
- **warning (notable template flag)** — every NPCCharacter referenced by a culture's
  `notable_templates` must carry `is_template="true"` so the engine can identify
  them as templates rather than spawned heroes.
- **warning (character creation optional)** — non-universal character creation
  equipment rosters (e.g. `physician`, `herder`, `bard`, `kern`, `vagabond`,
  `healer`, `mercenary`, `skirmisher`) are only needed if the culture uses the
  corresponding parent/youth options in `CharacterCreationCampaignBehavior.cs`.
  Missing rosters produce a warning with guidance to check the game code.
- **optional** — education character templates, NPC characters and
  body properties tagged with the culture (missing = warning only).
- **info** — default policies, feats / clan banner icons / ship hulls
  (these live in engine code and cannot be resolved against XML).

## Exit codes

- `0` — all required checks passed
- `1` — at least one required check failed (culture missing necessary data)
- `2` — the tool could not run (bad paths, unreadable cultures file)