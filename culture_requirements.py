"""Requirement catalog: what a Culture element needs, derived from the game XML.

A Culture is classified into one of four buckets:
  main    - is_main_culture="true"      (full attribute set + template lists)
  minor   - can_have_settlement="true"  (reduced attribute set)
  bandit  - is_bandit="true"            (bandit-specific attributes)
  neutral - none of the above           (minimal)

The checks reference three kinds of data:
  * "resolve" checks: collect every Type.id the culture points at and verify
    each exists in the indexed data folders.
  * "presence" checks: verify required attributes / child elements exist on the
    Culture element itself (absent attributes can never be caught by resolve).
  * "tagged" checks: verify auxiliary xml files contain objects tagged with the
    culture (e.g. education character templates, NPC characters, body tags).

Each check has a default priority; checks_config.json can override it.
"""
import fnmatch
import os

# --------------------------------------------------------------------------
# Culture classification
# --------------------------------------------------------------------------

MAIN = "main"
MINOR = "minor"
BANDIT = "bandit"
NEUTRAL = "neutral"

TYPE_LABELS = {
    MAIN: "main culture (is_main_culture=true)",
    MINOR: "minor culture (can_have_settlement=true)",
    BANDIT: "bandit culture (is_bandit=true)",
    NEUTRAL: "neutral culture",
}


def classify_culture(elem):
    if _attr_is_true(elem, "is_bandit"):
        return BANDIT
    if _attr_is_true(elem, "is_main_culture"):
        return MAIN
    if _attr_is_true(elem, "can_have_settlement"):
        return MINOR
    return NEUTRAL


def _attr_is_true(elem, attr):
    """Convert.ToBoolean in the game is case-insensitive; mirror that."""
    return elem.get(attr, "").strip().lower() == "true"


# --------------------------------------------------------------------------
# Reference sources in the Culture XML (attribute -> object type)
# --------------------------------------------------------------------------

NPC_ATTRS_ROLE = (
    "elite_basic_troop", "basic_troop", "melee_militia_troop",
    "ranged_militia_troop", "melee_elite_militia_troop",
    "ranged_elite_militia_troop", "tournament_master", "villager",
    "caravan_master", "caravan_guard", "veteran_caravan_guard", "prison_guard",
    "guard", "blacksmith", "weaponsmith", "townswoman", "townswoman_infant",
    "townswoman_child", "townswoman_teenager", "townsman", "townsman_infant",
    "townsman_child", "village_woman", "villager_male_child",
    "villager_male_teenager", "villager_female_child", "villager_female_teenager",
    "townsman_teenager", "ransom_broker", "gangleader_bodyguard",
    "merchant_notary", "artisan_notary", "preacher_notary",
    "rural_notable_notary", "shop_worker", "tavernkeeper", "taverngamehost",
    "musician", "tavern_wench", "armorer", "horseMerchant", "barber", "merchant",
    "beggar", "female_beggar", "female_dancer",
    # Optional but deserialized by CultureObject; resolved only when present.
    "shipwright", "shipyard_worker", "militia_veteran_archer", "gear_dummy",
)
NPC_ATTRS_BANDIT = ("bandit_bandit", "bandit_chief", "bandit_raider", "bandit_boss")
NPC_ATTRS = NPC_ATTRS_ROLE + NPC_ATTRS_BANDIT

PARTY_ATTRS = (
    "villager_party_template", "default_party_template",
    "settlement_patrol_template_level_1", "settlement_patrol_template_level_2",
    "settlement_patrol_template_level_3", "militia_party_template",
    "rebels_party_template", "vassal_reward_party_template",
    "bandit_boss_party_template",
    # Optional but deserialized by CultureObject; resolved only when present.
    "fishing_party_template", "settlement_patrol_template_coastal",
)
EQUIPMENT_ATTRS = (
    "default_battle_equipment_roster", "default_civilian_equipment_roster",
    "default_stealth_equipment_roster", "duel_preset_equipment_roster",
    "marriage_bride_equipment_roster",
)
BODY_ATTRS = ("default_character_creation_body_property",)

# parent element -> child element that carries an npc reference
TEMPLATE_LIST_PARENTS = {
    "lord_templates": "template",
    "notable_templates": "template",
    "rebellion_hero_templates": "template",
    "tournament_team_templates_one_participant": "template",
    "tournament_team_templates_two_participant": "template",
    "tournament_team_templates_four_participant": "template",
    "basic_mercenary_troops": "template",
}
CARAVAN_PARENTS = ("caravan_party_templates", "elite_caravan_party_templates")
ITEM_PARENTS = ("vassal_reward_items", "banner_bearer_replacement_weapons")

# --------------------------------------------------------------------------
# Expected occupation values for NPCCharacter roles referenced by cultures.
# Maps culture attribute name -> expected occupation string in spnpccharacters.xml.
# --------------------------------------------------------------------------

OCCUPATION_MAP = {
    "townsman": "Townsfolk",
    "townsman_infant": "Townsfolk",
    "townsman_child": "Townsfolk",
    "townsman_teenager": "Townsfolk",
    "townswoman": "Townsfolk",
    "townswoman_infant": "Townsfolk",
    "townswoman_child": "Townsfolk",
    "townswoman_teenager": "Townsfolk",
    "villager": "Villager",
    "villager_male_child": "Villager",
    "villager_male_teenager": "Villager",
    "villager_female_child": "Villager",
    "villager_female_teenager": "Villager",
    "village_woman": "Villager",
    "blacksmith": "Blacksmith",
    "weaponsmith": "Weaponsmith",
    "tavernkeeper": "Tavernkeeper",
    "taverngamehost": "TavernGameHost",
    "musician": "Musician",
    "tavern_wench": "TavernWench",
    "armorer": "Armorer",
    "horseMerchant": "HorseTrader",
    "barber": "Townsfolk",
    "merchant": "GoodsTrader",
    "beggar": "Townsfolk",
    "female_beggar": "Townsfolk",
    "female_dancer": "Townsfolk",
    "shop_worker": "ShopWorker",
    "ransom_broker": "RansomBroker",
    "gangleader_bodyguard": "Townsfolk",
    "merchant_notary": "Townsfolk",
    "artisan_notary": "Townsfolk",
    "preacher_notary": "Townsfolk",
    "rural_notable_notary": "Townsfolk",
    "caravan_master": "CaravanGuard",
    "caravan_guard": "CaravanGuard",
    "veteran_caravan_guard": "CaravanGuard",
    "prison_guard": "PrisonGuard",
    "tournament_master": "ArenaMaster",
}

# Expected occupation types among notable_templates characters.
# Each main culture must have at least one notable template per type.
NOTABLE_OCCUPATION_TYPES = frozenset({
    "Merchant", "Artisan", "Preacher", "GangLeader", "RuralNotable", "Headman"
})

# --------------------------------------------------------------------------
# Required attributes / child elements by culture bucket
# --------------------------------------------------------------------------

MAIN_REQUIRED_ATTRS = (
    "elite_basic_troop", "basic_troop", "melee_militia_troop",
    "ranged_militia_troop", "melee_elite_militia_troop",
    "ranged_elite_militia_troop", "can_have_settlement", "villager_party_template",
    "default_party_template", "settlement_patrol_template_level_1",
    "settlement_patrol_template_level_2", "settlement_patrol_template_level_3",
    "militia_party_template", "rebels_party_template", "vassal_reward_party_template",
    "encounter_background_mesh", "faction_banner_key",
    "color", "color2", "text", "board_game_type", "default_battle_equipment_roster",
    "default_civilian_equipment_roster", "default_stealth_equipment_roster",
    "duel_preset_equipment_roster", "marriage_bride_equipment_roster",
    "default_character_creation_body_property", "start_point_position_x",
    "start_point_position_y", "tournament_master", "villager", "caravan_master",
    "caravan_guard", "veteran_caravan_guard", "prison_guard", "guard",
    "blacksmith", "weaponsmith", "townswoman", "townswoman_infant",
    "townswoman_child", "townswoman_teenager", "townsman", "townsman_infant",
    "townsman_child", "village_woman", "villager_male_child",
    "villager_male_teenager", "villager_female_child", "villager_female_teenager",
    "townsman_teenager", "ransom_broker", "gangleader_bodyguard",
    "merchant_notary", "artisan_notary", "preacher_notary",
    "rural_notable_notary", "shop_worker", "tavernkeeper", "taverngamehost",
    "musician", "tavern_wench", "armorer", "horseMerchant", "barber", "merchant",
    "beggar", "female_beggar", "female_dancer",
)

MAIN_REQUIRED_CHILDREN = (
    "available_ship_hulls", "possible_clan_banner_icon_ids", "cultural_feats",
    "default_policies", "male_names", "female_names", "clan_names",
    "lord_templates", "notable_templates", "rebellion_hero_templates",
    "vassal_reward_items", "banner_bearer_replacement_weapons",
    "caravan_party_templates", "elite_caravan_party_templates",
    "basic_mercenary_troops",
)
TOURNAMENT_PARENTS = (
    "tournament_team_templates_one_participant",
    "tournament_team_templates_two_participant",
    "tournament_team_templates_four_participant",
)

SETTLEMENT_REQUIRED_ATTRS = (
    "encounter_background_mesh", "villager_party_template",
    "militia_party_template", "settlement_patrol_template_level_1",
    "settlement_patrol_template_level_2", "settlement_patrol_template_level_3",
)
SETTLEMENT_REQUIRED_CHILDREN = ("caravan_party_templates",)

BANDIT_REQUIRED_ATTRS = (
    "elite_basic_troop", "basic_troop", "can_have_settlement",
    "encounter_background_mesh",
)
BANDIT_RECOMMENDED_ATTRS = (
    "bandit_bandit", "bandit_chief", "bandit_raider", "bandit_boss",
    "bandit_boss_party_template",
)


# --------------------------------------------------------------------------
# Reference collection
# --------------------------------------------------------------------------

def split_ref(value):
    """'PartyTemplate.x' -> ('PartyTemplate', 'x'); 'x' -> (None, 'x')."""
    if "." in value:
        prefix, obj_id = value.split(".", 1)
        return prefix, obj_id
    return None, value


def collect_refs(elem):
    """Return (refs, unknown).

    refs:   {intended_type: [(obj_id, display_string), ...]}
    unknown: [(obj_id, display, where)] for values whose prefix does not match
            the attribute/child they were found in (likely a typo).
    """
    refs = {}
    unknown = []

    def add(where, intended_type, value):
        if not value:
            return
        prefix, obj_id = split_ref(value)
        if prefix is None or prefix == intended_type:
            refs.setdefault(intended_type, []).append((obj_id, value))
        else:
            unknown.append((obj_id, value, where))

    for attr in NPC_ATTRS:
        add("attribute %s" % attr, "NPCCharacter", elem.get(attr))
    for attr in PARTY_ATTRS:
        add("attribute %s" % attr, "PartyTemplate", elem.get(attr))
    for attr in EQUIPMENT_ATTRS:
        add("attribute %s" % attr, "EquipmentRoster", elem.get(attr))
    for attr in BODY_ATTRS:
        add("attribute %s" % attr, "BodyProperty", elem.get(attr))

    for parent, child_tag in TEMPLATE_LIST_PARENTS.items():
        node = elem.find(parent)
        if node is None:
            continue
        for child in node.findall(child_tag):
            add("%s/%s" % (parent, child_tag), "NPCCharacter",
                child.get("name") or child.get("id"))

    for parent in CARAVAN_PARENTS:
        node = elem.find(parent)
        if node is None:
            continue
        for child in node.findall("caravan_party_template"):
            add("%s/caravan_party_template" % parent, "PartyTemplate", child.get("id"))

    for parent in ITEM_PARENTS:
        node = elem.find(parent)
        if node is None:
            continue
        for child in node.findall("item"):
            add("%s/item" % parent, "Item", child.get("id"))

    for node in elem.findall("default_policies"):
        for child in node.findall("policy"):
            add("default_policies/policy", "Policy", child.get("id"))

    return refs, unknown


# --------------------------------------------------------------------------
# Check helpers
# --------------------------------------------------------------------------

def _resolve(index, refs_by_type, unknown, expected_type):
    entries = refs_by_type.get(expected_type, [])
    found = 0
    missing = []
    for obj_id, display in entries:
        if index.has(expected_type, obj_id):
            found += 1
        else:
            missing.append(display)
    note = ""
    if unknown:
        note = ("mismatched type prefix(es): "
                + ", ".join(sorted({display for _, display, _ in unknown})))
    return {"found": found, "total": len(entries), "missing": missing, "note": note}


def _presence(elem, attrs, children=(), name=None):
    missing = []
    for attr in attrs:
        if not elem.get(attr):
            missing.append(attr)
    for child in children:
        if elem.find(child) is None:
            missing.append("<%s/>" % child)
    if name:
        if elem.find(name) is None:
            missing.append("<%s/>" % name)
    total = len(attrs) + len(children) + (1 if name else 0)
    return {"found": total - len(missing), "total": total, "missing": missing, "note": ""}


def _tagged(index, culture_id, ref_type, patterns):
    ids = index.tagged_ids_in_files(ref_type, culture_id, patterns)
    if ids:
        return {
            "found": len(ids), "total": len(ids), "missing": [],
            "note": "%d object(s) matching culture '%s'" % (len(ids), culture_id),
        }
    return {
        "found": 0, "total": 1, "missing": [culture_id],
        "note": "0 objects matching culture '%s'" % culture_id,
    }


def _matches_files(patterns, source_files):
    if not patterns:
        return True
    return any(
        fnmatch.fnmatch(os.path.basename(src), pat)
        for src in source_files
        for pat in patterns
    )


# --------------------------------------------------------------------------
# Check registry
# --------------------------------------------------------------------------

def _run_common_attrs(index, elem, culture_id, config_entry):
    return _presence(elem, ("id", "name"))


def _run_main_attrs(index, elem, culture_id, config_entry):
    result = _presence(elem, MAIN_REQUIRED_ATTRS, MAIN_REQUIRED_CHILDREN)
    if not any(elem.find(p) is not None for p in TOURNAMENT_PARENTS):
        result["missing"].append("tournament_team_templates_* (at least one)")
        result["found"] -= 1
        # keep total consistent: +1 for the synthetic required entry
    return result


def _run_settlement_attrs(index, elem, culture_id, config_entry):
    result = _presence(elem, SETTLEMENT_REQUIRED_ATTRS, SETTLEMENT_REQUIRED_CHILDREN)
    caravan = elem.find("caravan_party_templates")
    if caravan is not None and not caravan.findall("caravan_party_template"):
        result["missing"].append("caravan_party_templates/caravan_party_template*")
        result["found"] -= 1
    return result


def _run_bandit_attrs(index, elem, culture_id, config_entry):
    result = _presence(elem, BANDIT_REQUIRED_ATTRS)
    recommended_missing = [a for a in BANDIT_RECOMMENDED_ATTRS if not elem.get(a)]
    note = ""
    if recommended_missing:
        note = "recommended (not mandatory): " + ", ".join(recommended_missing)
    result["note"] = note
    return result


def _run_npc_refs(index, elem, culture_id, config_entry):
    refs, unknown = collect_refs(elem)
    return _resolve(index, refs, unknown, "NPCCharacter")


def _run_party_refs(index, elem, culture_id, config_entry):
    refs, unknown = collect_refs(elem)
    return _resolve(index, refs, unknown, "PartyTemplate")


def _run_equipment_refs(index, elem, culture_id, config_entry):
    refs, unknown = collect_refs(elem)
    return _resolve(index, refs, unknown, "EquipmentRoster")


def _run_body_refs(index, elem, culture_id, config_entry):
    refs, unknown = collect_refs(elem)
    return _resolve(index, refs, unknown, "BodyProperty")


def _run_item_refs(index, elem, culture_id, config_entry):
    refs, unknown = collect_refs(elem)
    return _resolve(index, refs, unknown, "Item")


def _run_name_lists(index, elem, culture_id, config_entry):
    male = len(elem.findall("male_names/name"))
    female = len(elem.findall("female_names/name"))
    missing = []
    if male < 1:
        missing.append("male_names (none defined)")
    if female < 1:
        missing.append("female_names (none defined)")
    return {
        "found": male + female,
        "total": male + female,
        "missing": missing,
        "note": "male=%d female=%d" % (male, female),
    }


# EquipmentCategories flag sets DefaultEquipmentSelectionModel selects on.
# Each combo lists the exact <Flags> required and the EquipmentSet kinds the
# game needs available for it (per Decimals/vanilla: come-of-age/companion-to-
# lord/teen/child/new-ruler). See TaleWorlds.Core.EquipmentCategories.cs.
_EQUIPMENT_COMBOS = (
    (frozenset({"IsLordTemplate"}), ("Battle", "Civilian"), "IsLordTemplate"),
    (frozenset({"IsLordTemplate", "IsChildEquipmentTemplate"}), ("Civilian",),
     "IsLordTemplate|IsChildEquipmentTemplate"),
    (frozenset({"IsLordTemplate", "IsTeenagerEquipmentTemplate"}), ("Civilian",),
     "IsLordTemplate|IsTeenagerEquipmentTemplate"),
    (frozenset({"IsKingdomRulerTemplate"}), ("Battle", "Civilian"),
     "IsKingdomRulerTemplate"),
)


def _run_equipment_template_categories(index, elem, culture_id, config_entry):
    total = 0
    found = 0
    missing = []
    for flags, required_types, label in _EQUIPMENT_COMBOS:
        for variant, variant_flags in (
                ("male", flags), ("female", flags | {"IsFemaleTemplate"})):
            total += 1
            rosters = index.category_rosters_for(culture_id, variant_flags)
            have_types = set()
            for _rid, equip_types, _src in rosters:
                have_types |= set(equip_types)
            if not rosters:
                missing.append("%s (%s)" % (label, variant))
                continue
            lacking = [t for t in required_types if t not in have_types]
            if lacking:
                missing.append("%s (%s) - missing equipment type(s): %s"
                               % (label, variant, ", ".join(lacking)))
            else:
                found += 1
    note = "%d of %d required roster combos present" % (found, total)
    return {"found": found, "total": total, "missing": missing, "note": note}


# --------------------------------------------------------------------------
# Character creation equipment roster requirements
# --------------------------------------------------------------------------
# CharacterCreationCampaignBehavior.cs constructs equipment roster IDs at
# runtime using these patterns:
#   Parent:    {mother|father}_char_creation_{template}_{culture}
#   Childhood: player_char_creation_childhood_age_{culture}_{template}_{gender}
#   Education: player_char_creation_education_age_{culture}_{template}_{gender}
#   Player:    player_char_creation_{culture}_{template}_{gender}
#   Default:   player_char_creation_default
#
# Not every culture uses every template.  The universal ones (used by ALL
# vanilla cultures) are required; the rest are optional with warnings.

# Parent templates used by ALL 6 vanilla cultures.
_CHAR_CREATION_UNIVERSAL_PARENT = ("retainer", "farmer")

# Player (youth/adult) templates used by ALL 6 vanilla cultures.
_CHAR_CREATION_UNIVERSAL_PLAYER = ("guard", "infantry")

# All parent templates across all vanilla cultures.
_CHAR_CREATION_PARENT_TEMPLATES = (
    "retainer", "merchant", "farmer", "artisan", "hunter", "vagabond",
    "healer", "herder", "mercenary", "physician", "bard",
)

# All player (youth/adult) templates across all vanilla cultures.
_CHAR_CREATION_PLAYER_TEMPLATES = (
    "retainer", "mercenary", "guard", "hunter", "infantry",
    "skirmisher", "kern", "bard",
)


def _build_char_creation_required_ids(culture_id):
    """Build the set of *required* char_creation roster IDs.

    These are the universal templates that every culture must provide for
    character creation to work (retainer/farmer for parents, guard/infantry
    for the player, plus the default fallback).
    """
    ids = []
    # Parent stage (mother + father)
    for t in _CHAR_CREATION_UNIVERSAL_PARENT:
        ids.append("mother_char_creation_%s_%s" % (t, culture_id))
        ids.append("father_char_creation_%s_%s" % (t, culture_id))
    # Childhood age (both genders)
    for t in _CHAR_CREATION_UNIVERSAL_PARENT:
        ids.append("player_char_creation_childhood_age_%s_%s_m" % (culture_id, t))
        ids.append("player_char_creation_childhood_age_%s_%s_f" % (culture_id, t))
    # Education age (both genders)
    for t in _CHAR_CREATION_UNIVERSAL_PARENT:
        ids.append("player_char_creation_education_age_%s_%s_m" % (culture_id, t))
        ids.append("player_char_creation_education_age_%s_%s_f" % (culture_id, t))
    # Player adult (both genders)
    for t in _CHAR_CREATION_UNIVERSAL_PLAYER:
        ids.append("player_char_creation_%s_%s_m" % (culture_id, t))
        ids.append("player_char_creation_%s_%s_f" % (culture_id, t))
    # Default fallback (culture-independent)
    ids.append("player_char_creation_default")
    return ids


def _build_char_creation_optional_ids(culture_id):
    """Build the set of *optional* char_creation roster IDs.

    These are templates used by some but not all vanilla cultures.  If a
    culture uses one of these parent/youth options in its
    CharacterCreationCampaignBehavior the corresponding rosters must exist.
    """
    ids = []
    # Parent stage - non-universal templates
    for t in _CHAR_CREATION_PARENT_TEMPLATES:
        if t not in _CHAR_CREATION_UNIVERSAL_PARENT:
            ids.append("mother_char_creation_%s_%s" % (t, culture_id))
            ids.append("father_char_creation_%s_%s" % (t, culture_id))
    # Childhood age - non-universal templates
    for t in _CHAR_CREATION_PARENT_TEMPLATES:
        if t not in _CHAR_CREATION_UNIVERSAL_PARENT:
            ids.append("player_char_creation_childhood_age_%s_%s_m" % (culture_id, t))
            ids.append("player_char_creation_childhood_age_%s_%s_f" % (culture_id, t))
    # Education age - non-universal templates
    for t in _CHAR_CREATION_PARENT_TEMPLATES:
        if t not in _CHAR_CREATION_UNIVERSAL_PARENT:
            ids.append("player_char_creation_education_age_%s_%s_m" % (culture_id, t))
            ids.append("player_char_creation_education_age_%s_%s_f" % (culture_id, t))
    # Player adult - non-universal templates
    for t in _CHAR_CREATION_PLAYER_TEMPLATES:
        if t not in _CHAR_CREATION_UNIVERSAL_PLAYER:
            ids.append("player_char_creation_%s_%s_m" % (culture_id, t))
            ids.append("player_char_creation_%s_%s_f" % (culture_id, t))
    return ids


def _run_char_creation_equipment(index, elem, culture_id, config_entry):
    """Check that universal character creation equipment rosters exist.

    These rosters are constructed at runtime by CharacterCreationCampaignBehavior
    and are required for every main culture that participates in character creation.
    """
    required_ids = _build_char_creation_required_ids(culture_id)
    found = 0
    missing = []
    for roster_id in required_ids:
        if index.has("EquipmentRoster", roster_id):
            found += 1
        else:
            missing.append(roster_id)
    note = ("%d of %d required character creation rosters present"
            % (found, len(required_ids)))
    return {"found": found, "total": len(required_ids),
            "missing": missing, "note": note}


def _run_char_creation_equipment_optional(index, elem, culture_id, config_entry):
    """Warn about optional character creation equipment rosters.

    These rosters are only needed if the culture uses the corresponding
    parent/youth options in CharacterCreationCampaignBehavior.cs.
    """
    optional_ids = _build_char_creation_optional_ids(culture_id)
    found = 0
    missing = []
    for roster_id in optional_ids:
        if index.has("EquipmentRoster", roster_id):
            found += 1
        else:
            missing.append(roster_id)
    note = ("%d of %d optional character creation rosters present. "
            "Missing rosters are only needed if your culture uses them "
            "in CharacterCreationCampaignBehavior."
            % (found, len(optional_ids)))
    return {"found": found, "total": len(optional_ids),
            "missing": missing, "note": note}


# --------------------------------------------------------------------------
# Culture string requirements
# --------------------------------------------------------------------------
# GameTexts.FindText("str_...", culture.StringId) resolves to string IDs of
# the form "str_{base}.{culture}".  Every main culture must provide these
# strings or the game crashes / shows ERROR_MISSING_NAME at runtime.

_CULTURE_STRING_PATTERNS = (
    "str_culture_description.{culture}",
    "str_culture_rich_name.{culture}",
    "str_faction_official.{culture}",
    "str_faction_official.{culture}_f",
    "str_faction_ruler.{culture}",
    "str_faction_ruler.{culture}_f",
    "str_faction_ruler_name_with_title.{culture}",
    "str_faction_noble_name_with_title.{culture}",
    "str_faction_formal_name_for_culture.{culture}",
    "str_faction_informal_name_for_culture.{culture}",
    "str_adjective_for_culture.{culture}",
    "str_neutral_term_for_culture.{culture}",
)


def _run_culture_strings(index, elem, culture_id, config_entry):
    """Check that all required culture strings exist in the data files.

    The game resolves these via GameTexts.FindText() with the culture's
    StringId as the variable argument.  A missing string causes a crash
    or displays ERROR_MISSING_NAME in the UI.
    """
    total = 0
    found = 0
    missing = []
    for pattern in _CULTURE_STRING_PATTERNS:
        string_id = pattern.format(culture=culture_id)
        total += 1
        if index.has_string(string_id):
            found += 1
        else:
            missing.append(string_id)
    note = "%d of %d required culture strings present" % (found, total)
    return {"found": found, "total": total, "missing": missing, "note": note}


# Attributes parsed by BasicCultureObject with Convert.ToUInt32(value, 16) -
# a non-hex value throws FormatException during campaign boot.
_HEX_COLOR_ATTRS = (
    "color", "color2", "cloth_alternative_color1", "cloth_alternative_color2",
    "banner_background_color1", "banner_foreground_color1",
    "banner_background_color2", "banner_foreground_color2",
)

# Attributes parsed with Convert.ToBoolean - anything but true/false throws.
_BOOL_ATTRS = ("is_main_culture", "is_bandit", "can_have_settlement")


def _run_culture_value_validity(index, elem, culture_id, config_entry):
    missing = []
    present = 0
    for attr in _BOOL_ATTRS:
        value = elem.get(attr)
        if value is None:
            continue
        present += 1
        if value.strip().lower() not in ("true", "false"):
            missing.append('%s="%s" is not true/false' % (attr, value))
    for attr in _HEX_COLOR_ATTRS:
        value = elem.get(attr)
        if value is None:
            continue
        present += 1
        try:
            parsed = int(value, 16)
        except ValueError:
            missing.append('%s="%s" is not a valid hex color' % (attr, value))
            continue
        if not 0 <= parsed <= 0xFFFFFFFF:
            missing.append('%s="%s" exceeds uint32 range' % (attr, value))
    note = "%d scalar attribute(s) validated" % present
    return {"found": present - len(missing), "total": present,
            "missing": missing, "note": note}


def _run_equipment_roster_flags(index, elem, culture_id, config_entry):
    rows = index.invalid_flags.get(culture_id, [])
    if not rows:
        return {"found": 1, "total": 1, "missing": [],
                "note": "all EquipmentRoster <Flags> names/values are valid"}
    missing = []
    for obj_id, source_file, (flag_name, raw_value) in rows:
        missing.append("%s [%s]: %s=%r"
                       % (obj_id, os.path.basename(source_file), flag_name, raw_value))
    return {"found": 0, "total": len(missing), "missing": missing,
            "note": "%d EquipmentRoster <Flags> problem(s)" % len(missing)}


def _run_education_character(index, elem, culture_id, config_entry):
    return _tagged(index, culture_id, "NPCCharacter", config_entry.get("files"))


def _run_npc_tags(index, elem, culture_id, config_entry):
    ids = index.tagged_ids("NPCCharacter", culture_id)
    if ids:
        return {
            "found": len(ids), "total": len(ids), "missing": [],
            "note": "%d NPC characters tagged with culture '%s'" % (len(ids), culture_id),
        }
    return {
        "found": 0, "total": 1, "missing": [culture_id],
        "note": "no NPC characters tagged with culture '%s'" % culture_id,
    }


def _run_body_tags(index, elem, culture_id, config_entry):
    ids = index.body_property_tags.get(culture_id, set())
    if ids:
        return {
            "found": len(ids), "total": len(ids), "missing": [],
            "note": "%d body properties carry %s hair/beard/tattoo tags"
                   % (len(ids), culture_id),
        }
    return {
        "found": 0, "total": 1, "missing": [culture_id],
        "note": "no body properties carry %s hair/beard/tattoo tags" % culture_id,
    }


def _run_policy_refs(index, elem, culture_id, config_entry):
    refs, unknown = collect_refs(elem)
    count = len(refs.get("Policy", []))
    note = ("%d policy id(s) listed; policy objects live in engine code and "
            "cannot be resolved against XML" % count)
    if unknown:
        note += " [mismatched prefix(es): %s]" % ", ".join(
            sorted({display for _, display, _ in unknown}))
    return {"found": count, "total": count, "missing": [], "note": note}


def _run_feats_icons(index, elem, culture_id, config_entry):
    feats = len(elem.findall("cultural_feats/feat"))
    icons = len(elem.findall("possible_clan_banner_icon_ids/icon"))
    hulls = len(elem.findall("available_ship_hulls/ship_hull"))
    present = 1 if (feats or icons or hulls) else 0
    note = ("feats=%d clan-banner-icon-ids=%d ship-hulls=%d "
            "(informational; catalogs live in code)" % (feats, icons, hulls))
    return {
        "found": present, "total": 1, "missing": [] if present else ["no lists present"],
        "note": note,
    }


def _run_npc_occupations(index, elem, culture_id, config_entry):
    total = 0
    found = 0
    missing = []
    for attr, expected_occ in OCCUPATION_MAP.items():
        ref_value = elem.get(attr)
        if not ref_value:
            continue
        _prefix, obj_id = split_ref(ref_value)
        total += 1
        actual_occ = index.npc_occupations.get(obj_id)
        if actual_occ is None:
            if not index.has("NPCCharacter", obj_id):
                missing.append("%s (character not found)" % ref_value)
            else:
                missing.append("%s (no occupation attribute; expected %s)"
                               % (ref_value, expected_occ))
        elif actual_occ != expected_occ:
            missing.append("%s (occupation=%s, expected %s)"
                           % (ref_value, actual_occ, expected_occ))
        else:
            found += 1
    note = "%d of %d role characters have correct occupation" % (found, total)
    return {"found": found, "total": total, "missing": missing, "note": note}


def _run_notable_template_occupations(index, elem, culture_id, config_entry):
    """Verify notable_templates cover all expected occupation types."""
    notable_node = elem.find("notable_templates")
    if notable_node is None:
        return {
            "found": 0, "total": len(NOTABLE_OCCUPATION_TYPES),
            "missing": ["<notable_templates/> element missing"],
            "note": "no notable_templates element",
        }
    found_occupations = set()
    missing = []
    total_templates = 0
    for child in notable_node.findall("template"):
        ref_value = child.get("name")
        if not ref_value:
            continue
        total_templates += 1
        _prefix, obj_id = split_ref(ref_value)
        occ = index.npc_occupations.get(obj_id)
        if occ:
            found_occupations.add(occ)
    missing_types = sorted(NOTABLE_OCCUPATION_TYPES - found_occupations)
    for occ_type in missing_types:
        missing.append("no notable template with occupation=%s" % occ_type)
    found = len(NOTABLE_OCCUPATION_TYPES) - len(missing_types)
    note = ("%d of %d expected occupation types covered by %d notable templates"
            % (found, len(NOTABLE_OCCUPATION_TYPES), total_templates))
    return {"found": found, "total": len(NOTABLE_OCCUPATION_TYPES),
            "missing": missing, "note": note}


def _run_notable_template_is_template(index, elem, culture_id, config_entry):
    """Verify every notable template character has is_template="true"."""
    notable_node = elem.find("notable_templates")
    if notable_node is None:
        return {
            "found": 0, "total": 0,
            "missing": [],
            "note": "no notable_templates element",
        }
    total = 0
    found = 0
    missing = []
    for child in notable_node.findall("template"):
        ref_value = child.get("name")
        if not ref_value:
            continue
        total += 1
        _prefix, obj_id = split_ref(ref_value)
        is_tmpl = index.npc_is_template.get(obj_id)
        if is_tmpl is True:
            found += 1
        elif is_tmpl is False:
            missing.append("%s (is_template=false)" % ref_value)
        else:
            if not index.has("NPCCharacter", obj_id):
                missing.append("%s (character not found)" % ref_value)
            else:
                missing.append("%s (is_template attribute missing)" % ref_value)
    note = "%d of %d notable templates have is_template=true" % (found, total)
    return {"found": found, "total": total, "missing": missing, "note": note}


class CheckSpec:
    def __init__(self, check_id, label, description, default_priority,
                 applies, run):
        self.check_id = check_id
        self.label = label
        self.description = description
        self.default_priority = default_priority
        self.applies = applies
        self.run = run


def _applies_always(elem):
    return True


def _applies_main(elem):
    return classify_culture(elem) == MAIN


def _applies_settlement(elem):
    return classify_culture(elem) in (MAIN, MINOR)


def _applies_bandit(elem):
    return classify_culture(elem) == BANDIT


def _applies_equipment(elem):
    return classify_culture(elem) in (MAIN, MINOR, NEUTRAL) or any(
        elem.get(a) for a in EQUIPMENT_ATTRS
    )


def _applies_body(elem):
    return any(elem.get(a) for a in BODY_ATTRS)


def _applies_items(elem):
    return any(
        elem.find(p) is not None and elem.find(p).findall("item")
        for p in ITEM_PARENTS
    )


def _applies_names(elem):
    return classify_culture(elem) in (MAIN, MINOR, BANDIT)


CHECKS = {
    "common_attrs": CheckSpec(
        "common_attrs", "Common attributes (id, name)",
        "Base attributes every culture must carry.",
        "required", _applies_always, _run_common_attrs),
    "main_culture_attrs": CheckSpec(
        "main_culture_attrs", "Main-culture attributes and template lists",
        "Full attribute/child set shared by the vanilla is_main_culture=true cultures.",
        "required", _applies_main, _run_main_attrs),
    "settlement_attrs": CheckSpec(
        "settlement_attrs", "Settlement attributes",
        "Attributes needed when the culture can own settlements "
        "(villager/militia/patrol templates, encounter background, caravans).",
        "required", _applies_settlement, _run_settlement_attrs),
    "bandit_attrs": CheckSpec(
        "bandit_attrs", "Bandit attributes",
        "Attributes needed for is_bandit=true cultures.",
        "required", _applies_bandit, _run_bandit_attrs),
    "npc_character_refs": CheckSpec(
        "npc_character_refs", "NPC character references",
        "Every NPCCharacter.<id> pointed to by troop/role attributes and "
        "template lists must exist in the data folders.",
        "required", _applies_always, _run_npc_refs),
    "party_template_refs": CheckSpec(
        "party_template_refs", "Party template references",
        "Every PartyTemplate.<id> (villager/militia/patrol/caravan/...) must exit.",
        "required", _applies_always, _run_party_refs),
    "equipment_roster_refs": CheckSpec(
        "equipment_roster_refs", "Equipment roster references",
        "default_battle/civilian/stealth/duel/marriage EquipmentRoster.<id> must exist.",
        "required", _applies_equipment, _run_equipment_refs),
    "body_property_refs": CheckSpec(
        "body_property_refs", "Body property references",
        "default_character_creation_body_property BodyProperty.<id> must exist.",
        "required", _applies_body, _run_body_refs),
    "item_refs": CheckSpec(
        "item_refs", "Item references",
        "vassal_reward_items and banner_bearer_replacement_weapons Item.<id>s must exist.",
        "required", _applies_items, _run_item_refs),
    "name_lists": CheckSpec(
        "name_lists", "Name lists (male/female)",
        "At least one male and one female name must be defined.",
        "required", _applies_names, _run_name_lists),
    "equipment_templates_categories": CheckSpec(
        "equipment_templates_categories", "Equipment template categories (DefaultEquipmentSelectionModel)",
        "For each EquipmentCategories flag set DefaultEquipmentSelectionModel "
        "selects on, main cultures must have at least one <Flags> EquipmentRoster; "
        "Lord/KingdomRuler need both a Battle and a Civilian equipment set, "
        "Child/Teen a Civilian set.",
        "required", _applies_main, _run_equipment_template_categories),
    "equipment_roster_flags": CheckSpec(
        "equipment_roster_flags", "EquipmentRoster <Flags> validity",
        "MBEquipmentRoster parses each <Flags> attribute name with "
        "Enum.Parse(EquipmentCategories) and its value with bool.Parse - an "
        "unknown flag name or a non-boolean value throws at load time.",
        "required", _applies_always, _run_equipment_roster_flags),
    "culture_value_validity": CheckSpec(
        "culture_value_validity", "Culture attribute value validity",
        "BasicCultureObject parses is_main_culture/is_bandit/can_have_settlement "
        "with Convert.ToBoolean and the color attributes with "
        "Convert.ToUInt32(value, 16); malformed values throw during campaign boot.",
        "required", _applies_always, _run_culture_value_validity),
    "education_character_templates": CheckSpec(
        "education_character_templates", "Education character templates",
        "Per-culture NPCCharacter templates for child education. Missing is fine.",
        "optional", _applies_always, _run_education_character),
    "npc_culture_tags": CheckSpec(
        "npc_culture_tags", "NPC characters tagged with culture",
        "NPCCharacter entries carrying culture='Culture.<id>' give the culture "
        "its people. Missing is usually fine for bandit/neutral cultures.",
        "optional", _applies_always, _run_npc_tags),
    "body_property_culture_tags": CheckSpec(
        "body_property_culture_tags", "Body properties tagged with culture",
        "BodyProperty hair/beard/tattoo tags referencing the culture id.",
        "optional", _applies_always, _run_body_tags),
    "policy_refs": CheckSpec(
        "policy_refs", "Default policies",
        "default_policies/policy ids. Informational only: policies live in engine code.",
        "info", _applies_main, _run_policy_refs),
    "feats_banner_icons_ship_hulls": CheckSpec(
        "feats_banner_icons_ship_hulls", "Feats / clan banner icons / ship hulls",
        "Informational counts of cultural_feats, possible_clan_banner_icon_ids "
        "and available_ship_hulls. These catalogs are engine-side.",
        "info", _applies_main, _run_feats_icons),
    "npc_occupations": CheckSpec(
        "npc_occupations", "NPC character occupation values",
        "Each NPCCharacter role referenced by the culture must have the correct "
        "occupation attribute in spnpccharacters.xml (e.g. townsman requires "
        "occupation=\"Townsfolk\").",
        "required", _applies_always, _run_npc_occupations),
    "notable_template_occupations": CheckSpec(
        "notable_template_occupations", "Notable template occupation coverage",
        "Each main culture's notable_templates must include at least one "
        "template for each expected occupation type (Merchant, Artisan, "
        "Preacher, GangLeader, RuralNotable).",
        "required", _applies_main, _run_notable_template_occupations),
    "notable_template_is_template": CheckSpec(
        "notable_template_is_template", "Notable templates have is_template flag",
        "Every NPCCharacter referenced by a culture's notable_templates must "
        "carry is_template=\"true\" so the engine can identify them as templates.",
        "warning", _applies_main, _run_notable_template_is_template),
    "char_creation_equipment": CheckSpec(
        "char_creation_equipment", "Character creation equipment rosters (required)",
        "CharacterCreationCampaignBehavior.cs constructs equipment roster IDs at "
        "runtime. Universal templates (retainer/farmer for parents, guard/infantry "
        "for the player) and the default fallback must exist in the data folders.",
        "required", _applies_main, _run_char_creation_equipment),
    "char_creation_equipment_optional": CheckSpec(
        "char_creation_equipment_optional",
        "Character creation equipment rosters (optional)",
        "Non-universal character creation equipment rosters that are only needed "
        "if the culture uses the corresponding parent/youth options in "
        "CharacterCreationCampaignBehavior.cs (e.g. physician, herder, bard, kern, "
        "vagabond, healer, mercenary, skirmisher).",
        "warning", _applies_main, _run_char_creation_equipment_optional),
    "culture_strings": CheckSpec(
        "culture_strings", "Culture strings (module_strings.xml)",
        "Every main culture needs str_culture_description, str_culture_rich_name, "
        "str_faction_official, str_faction_ruler, str_faction_ruler_name_with_title, "
        "str_faction_noble_name_with_title, str_faction_formal_name_for_culture, "
        "str_faction_informal_name_for_culture, str_adjective_for_culture, and "
        "str_neutral_term_for_culture (male + female variants where applicable). "
        "GameTexts.FindText() crashes or shows ERROR_MISSING_NAME on missing strings.",
        "required", _applies_main, _run_culture_strings),
}

DEFAULT_PRIORITIES = {check_id: spec.default_priority for check_id, spec in CHECKS.items()}


def resolve_config(cfg):
    """cfg is the raw parsed checks_config.json ('checks' dict) or None.

    Returns {check_id: {"priority": str, "files": list|None, "enabled": bool}}
    """
    raw = (cfg or {}).get("checks", {})
    resolved = {}
    for check_id, spec in CHECKS.items():
        entry = raw.get(check_id, spec.default_priority)
        if isinstance(entry, dict):
            priority = entry.get("priority", spec.default_priority)
            files = entry.get("files")
        else:
            priority = entry
            files = None
        resolved[check_id] = {
            "priority": priority,
            "files": files,
            "enabled": priority != "disabled",
        }
    return resolved


def run_checks(index, culture_elem, culture_id, check_configs):
    """Run every applicable check for one culture.

    Returns a list of dicts: {id, label, priority, status, found, total,
    missing, note, applicable}.
    """
    results = []
    for check_id, spec in CHECKS.items():
        conf = check_configs[check_id]
        base = {
            "id": check_id, "label": spec.label, "priority": conf["priority"],
            "description": spec.description,
        }
        if not spec.applies(culture_elem):
            results.append(dict(base, status="not_applicable", found=0, total=0,
                                missing=[], note="", applicable=False))
            continue
        if not conf["enabled"]:
            results.append(dict(base, status="disabled", found=0, total=0,
                                missing=[], note="check disabled in checks_config.json",
                                applicable=True))
            continue
        data = spec.run(index, culture_elem, culture_id, conf)
        status = "ok"
        if data["found"] < data["total"]:
            status = "missing"
        if data["missing"] and data["total"] == 0:
            status = "missing"
        results.append(dict(base, status=status, found=data["found"],
                            total=data["total"], missing=data["missing"],
                            note=data["note"], applicable=True))
    return results


def file_matches(patterns, source_files):
    return _matches_files(patterns, source_files)