# Culture data deserialization — classes that consume `<Culture>` XML

How Bannerlord loads a `<Culture>` from `spcultures.xml`, which classes deserialize it
and everything it references, and which data is genuinely **required for the game not
to crash**. Cross-checked against the Culture Validator (`culture_validator.py`,
`object_index.py`, `culture_requirements.py`, `checks_config.json`).

All paths are relative to the decompiled sources in
`C:\Users\dajam\bannerlordMods\BannerlordDecompiled`.

---

## 1. The load pipeline (who calls `LoadXML`)

| Class | File | Role |
|---|---|---|
| `Campaign` | `TaleWorlds.CampaignSystem\Campaign.cs` | `InitializeBasicObjectXmls()` calls `ObjectManager.LoadXML("SPCultures")`; `InitializeDefaultCampaignObjects()` loads `Items`, `EquipmentRosters`, `partyTemplates`. Also `OnRegisterTypes` registers `CultureObject`, `CharacterObject`, `PartyTemplateObject`, `PolicyObject`, `ShipHull`, etc. |
| `Game` | `TaleWorlds.Core\Game.cs` | `RegisterTypes` registers the core types (`ItemObject`, `MBBodyProperty`, `MBEquipmentRoster`, `MBCharacterSkills`, ...); `LoadBasicFiles()` loads `BodyProperties`. |
| `MBObjectManager` | `TaleWorlds.ObjectSystem\MBObjectManager.cs` | `LoadXML(id)` merges the module XMLs for that list id, then `LoadXml()` deserializes every child element into a registered object. `RegisterType<T>(elementName, elementListName, typeId, autoCreateInstance=true)` decides whether an unknown referenced id becomes a presumed object (default **true**) or throws. |
| `MBObjectBase` | `TaleWorlds.ObjectSystem\MBObjectBase.cs` | Base `Deserialize` reads the mandatory `id` attribute (NRE if absent). |
| `ModuleHelper`, `XmlResource`, `MbObjectXmlInformation` | `TaleWorlds.ModuleManager`, `TaleWorlds.ObjectSystem` | Map module XML files to list ids, check active modules, validate against XSD, and merge overrides across modules. |

Load-time crashes originate almost exclusively in this pipeline:
`MBObjectManager.LoadXml` reads `id`; `BasicCultureObject` reads `name`; bad reference
prefixes throw `MBInvalidReferenceException`; invalid `<Flags>` names throw
`Enum.Parse`/`FormatException`. Everything else degrades to a *presumed* (non-ready)
object and crashes later at first use.

## 2. The culture classes themselves

| Class | File | Attributes / children it reads |
|---|---|---|
| `BasicCultureObject` | `TaleWorlds.Core\BasicCultureObject.cs` | `id`, `name`, `color`, `color2`, `cloth_alternative_color1/2`, `banner_background_color1/2`, `banner_foreground_color1/2`, `is_main_culture`, `encounter_background_mesh`, `faction_banner_key` (→ `Banner`), `is_bandit`, `can_have_settlement`. **`name` is read without a null check → NRE if missing.** |
| `CultureObject` | `TaleWorlds.CampaignSystem\CultureObject.cs` | `militia_bonus`, `prosperity_bonus`, `naval_factor`, `text`, `start_point_position_x/y`, `board_game_type`, `default_character_creation_body_property`, ~64 `NPCCharacter.*` role refs, 11 `PartyTemplate.*` refs, 5 `EquipmentRoster.*` refs; children `default_policies`, `male_names`, `female_names`, `clan_names`, `cultural_feats`, `possible_clan_banner_icon_ids`, `notable_templates`, `lord_templates`, `rebellion_hero_templates`, `tournament_team_templates_{one,two,four}_participant`, `vassal_reward_items`, `basic_mercenary_troops`, `banner_bearer_replacement_weapons`, `caravan_party_templates`, `elite_caravan_party_templates`, `available_ship_hulls`. |
| `Banner` | `TaleWorlds.Core\Banner.cs` | Parses the `faction_banner_key` string (`.`, int tokens). Empty key is an assert, malformed key can yield an empty banner data list that crashes banner getters. |

## 3. Referenced object types (deserialized as a side effect of a culture)

| Type | Element(s) | File | Notes |
|---|---|---|---|
| `CharacterObject` | `NPCCharacter` | `TaleWorlds.CampaignSystem\CharacterObject.cs` | Backs every role/troop ref. Its own `Deserialize` reads `culture="Culture.<id>"` back into the `CultureObject` (see section 4). |
| `BasicCharacterObject` | `NPCCharacter` | `TaleWorlds.Core\BasicCharacterObject.cs` | Reads `culture` attribute → `CultureObject`. |
| `PartyTemplateObject` | `MBPartyTemplate` (root `<partyTemplates>`) | `TaleWorlds.CampaignSystem\...\PartyTemplateObject.cs` | Reads `<stacks><PartyTemplateStack troop=... min_value max_value/>` and `<ship_hulls>`. `min_value`/`max_value` are read via `Convert.ToInt32` (NRE if missing). |
| `MBEquipmentRoster` | `EquipmentRoster` | `TaleWorlds.Core\MBEquipmentRoster.cs` | Reads `culture` (→ `BasicCultureObject`), `<EquipmentSet equipmentType|civilian>`, and `<Flags name="true"/>` attributes parsed as `EquipmentCategories` enum (`Enum.Parse` throws on unknown names). |
| `Equipment` | `EquipmentSet` / `Equipment` | `TaleWorlds.Core\Equipment.cs` | Per-slot gear; each `<Equipment slot= id="Item.x">` resolves an `ItemObject`. |
| `MBBodyProperty` | `BodyProperty` | `TaleWorlds.Core\MBBodyProperty.cs` | `default_character_creation_body_property` target; reads `BodyPropertiesMin/Max`, `hair_tags`/`beard_tags`/`tattoo_tags` (tag `name` = culture id). |
| `ItemObject` | `Item`, `CraftedItem` | `TaleWorlds.Core\ItemObject.cs` | `vassal_reward_items` / `banner_bearer_replacement_weapons` targets. Non-ready presumed items are filtered (`IsReady`). |
| `ShipHull` | `ShipHull` | `TaleWorlds.Core\ShipHull.cs` | `available_ship_hulls` target; requires `name`, `description` (NRE), plus `ShipSlot` refs via `GetObject<ShipSlot>`. |
| `FeatObject` / `PolicyObject` | inline `<feat>` / `Policy` | `TaleWorlds.CampaignSystem\...\FeatObject.cs`, `PolicyObject.cs` | Feats are created inline by `CultureObject`; policies are resolved via `GetObject<PolicyObject>` (policy objects are engine/code-defined, `DefaultPolicies`). |

## 4. Reverse references (types that pull a culture back during their own load)

| Type | Reference | Consequence of a missing culture |
|---|---|---|
| `CharacterObject` / `BasicCharacterObject` | `culture="Culture.<id>"` | Presumed `CultureObject`; later `CharacterObject.Culture.*` (equipment rosters, name lists) crash. |
| `MBEquipmentRoster` | `culture="Culture.<id>"` | `EquipmentCulture` null → warning only at load; broken at gear-assignment time. |
| `MBBodyProperty` | `hair_tags/beard_tags/tattoo_tags` `name="<culture>"` | Character-creation body selection misses this culture's body properties. |

## 5. Runtime consumers (where missing data actually crashes)

| Consumer | File | Culture field it dereferences |
|---|---|---|
| `DefaultEquipmentSelectionModel` | `TaleWorlds.CampaignSystem\...\DefaultEquipmentSelectionModel.cs` | Come-of-age/teen/child/new-ruler equipment — needs the per-culture `<Flags>` rosters (Battle + Civilian). **This is the new `equipment_templates_categories` check.** |
| `CharacterCreationManager` / `CharacterCreationCultureStageVM` | `TaleWorlds.CampaignSystem\...` | `StartingPoint`, `DefaultCharacterCreationBodyProperty`, name lists. |
| `DefaultEncounter`, `EncounterGameMenuBehavior`, `PlayerArmyWaitBehavior`, `MenuHelper` | `TaleWorlds.CampaignSystem\...` | `EncounterBackgroundMesh` (null mesh crashes menu background). |
| `MarriageSceneNotificationItem` | `TaleWorlds.CampaignSystem\...` | `MarriageBrideEquipmentRoster` (null-checked here, not everywhere). |

## 6. Validator coverage matrix

Legend: **REQ** = game crashes on load / guaranteed crash on use if missing ·
**OPT** = skipped when the attribute is absent, only harmful if present-but-broken ·
**INFO** = never fails.

| Culture data | Read by | Validator check | Status |
|---|---|---|---|
| `id` | `MBObjectBase` | `common_attrs` | REQ ✅ |
| `name` | `BasicCultureObject` | `common_attrs` | REQ ✅ |
| `color`, `color2` | `BasicCultureObject` | `main_culture_attrs` | REQ ✅ (presence; hex format not validated) |
| `cloth_alternative_color1/2`, `banner_*_color1/2` | `BasicCultureObject` | — | OPT, not in vanilla, not checked ⚠️ |
| `is_main_culture`, `is_bandit`, `can_have_settlement` | `BasicCultureObject` | classification | ✅ |
| `encounter_background_mesh` | `BasicCultureObject` | `main_culture_attrs`, `settlement_attrs` | REQ ✅ |
| `faction_banner_key` | `Banner` | `main_culture_attrs` | REQ ✅ (key format not validated ⚠️) |
| `militia_bonus`, `prosperity_bonus`, `naval_factor` | `CultureObject` | — | OPT (defaulted), not in vanilla ⚠️ |
| `text`, `start_point_position_x/y`, `board_game_type` | `CultureObject` | `main_culture_attrs` | REQ ✅ (enum not validated ⚠️) |
| `default_character_creation_body_property` | `CultureObject`→`MBBodyProperty` | `body_property_refs` | REQ ✅ |
| role/troop `NPCCharacter.*` refs (main) | `CultureObject` | `npc_character_refs` | REQ ✅ |
| `shipwright`, `shipyard_worker`, `militia_veteran_archer`, `gear_dummy` | `CultureObject` | `npc_character_refs` (resolved when present) | OPT, **added** ✅ |
| `PartyTemplate.*` refs (main) | `CultureObject` | `party_template_refs` | REQ ✅ |
| `fishing_party_template`, `settlement_patrol_template_coastal` | `CultureObject` | `party_template_refs` (resolved when present) | OPT, **added** ✅ |
| `EquipmentRoster.*` refs (battle/civilian/stealth/duel/marriage) | `CultureObject` | `equipment_roster_refs` | REQ ✅ |
| `<male_names>/<female_names>/<clan_names>` | `CultureObject` | `name_lists` | REQ ✅ |
| `<default_policies>` | `CultureObject` | `policy_refs` | INFO ✅ (code-defined) |
| `<cultural_feats>` | `CultureObject`→`FeatObject` | `feats_banner_icons_ship_hulls` + presence | INFO ✅ |
| `<possible_clan_banner_icon_ids>` | `CultureObject` | presence | INFO ✅ |
| template lists (`notable/lord/rebellion/tournament/mercenary`) | `CultureObject` | `main_culture_attrs` + `npc_character_refs` | REQ ✅ |
| `<vassal_reward_items>`, `<banner_bearer_replacement_weapons>` | `CultureObject`→`ItemObject` | `main_culture_attrs` + `item_refs` | REQ ✅ |
| `<caravan_party_templates>`, `<elite_caravan_party_templates>` | `CultureObject` | `main_culture_attrs` + `party_template_refs` | REQ ✅ |
| `<available_ship_hulls>` | `CultureObject`→`ShipHull` | `feats_banner_icons_ship_hulls` (count only) | INFO, ShipHull existence **not** resolved ⚠️ |
| `<Flags>` equipment categories | `MBEquipmentRoster` | `equipment_templates_categories` | REQ (main cultures) ✅ |
| reverse: `NPCCharacter.culture` | `CharacterObject` | `npc_culture_tags` | OPT ✅ |
| reverse: body-property culture tags | `MBBodyProperty` | `body_property_culture_tags` | OPT ✅ |

### Known gaps / limitations
1. **ShipHull existence** — `available_ship_hulls` entries are counted but never
   resolved (no check collects `ShipHull`-typed references, so the validator would
   not catch a broken `ShipHull.<id>` even if a NavalDLC `ModuleData` folder is
   passed). Safe today (vanilla main cultures list zero hulls), but worth a future
   check.
2. **Value formats** — `color`/`color2` (hex), `faction_banner_key`, `board_game_type`,
   and `<Flags>` attribute names are only checked for *presence*, not *validity*
   (a malformed hex color or unknown flag name crashes at load).
3. **Reverse references** (`npc_culture_tags`, `body_property_culture_tags`) are
   optional: they don't stop the culture from loading, but a culture that is referenced
   by other data must exist or the referencing objects become presumed and crash later.

## 7. Failure modes in short

- **Crash at load:** missing `id` / `name`; reference value without a `Type.` prefix
  (`MBInvalidReferenceException`); invalid `<Flags>` enum name; malformed hex color.
- **Silent degradation → crash on first use:** any `Type.id` reference that does not
  exist (presumed object, later NRE in character creation / encounters / marriages /
  equipment selection / settlement spawning / naval battles).
- **What the validator guarantees:** every required attribute/child present and every
  referenced `NPCCharacter` / `PartyTemplate` / `EquipmentRoster` / `BodyProperty` /
  `Item` existing, plus the `DefaultEquipmentSelectionModel` equipment-template
  combinations — i.e. the data set that keeps a campaign from crashing after load.
