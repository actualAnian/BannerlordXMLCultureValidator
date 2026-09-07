"""Scan ModuleData-style folders and build an index of all XML objects.

The index maps a reference type (e.g. "NPCCharacter", "PartyTemplate", "Item")
to a set of ids, so that references of the form "Type.id" used by Culture
elements can be resolved. It also records, per object type, which ids carry a
`culture="Culture.X"` attribute (or hair/beard/tattoo tags for BodyProperty),
so "reverse" checks (e.g. does an education character template exist for this
culture?) can be performed.

Only element tags at the ROOT level of each xml file are indexed (that is what
the game treats as object definitions), using ElementTree. Files that fail
strict parsing fall back to a lenient regex scan so broken/malformed xml does
not kill the whole run.
"""
import fnmatch
import os
import re
import xml.etree.ElementTree as ET

# Some xml files use a different element tag than the reference prefix.
# e.g. reference "PartyTemplate.x" points at <MBPartyTemplate id="x">.
ELEMENT_TYPE_MAP = {
    "MBPartyTemplate": "PartyTemplate",
    "CraftedItem": "Item",
}

# BodyProperty affinity to a culture is expressed via <hair_tag>/<beard_tag>/
# <tattoo_tag name="<culture_id>"> rather than a culture= attribute.
BODY_TAG_PARENTS = ("hair_tags", "beard_tags", "tattoo_tags")
BODY_TAG_ELEMENT = "BodyProperty"
EQUIP_ROSTER_ELEMENT = "EquipmentRoster"

# Member names of TaleWorlds.Core.EquipmentCategories. MBEquipmentRoster parses
# each <Flags> attribute name with Enum.Parse (case-sensitive) and crashes the
# load on anything unknown.
EQUIPMENT_CATEGORY_FLAGS = frozenset({
    "None", "IsFemaleTemplate", "IsLordTemplate", "IsChildEquipmentTemplate",
    "IsTeenagerEquipmentTemplate", "IsKingdomRulerTemplate",
})


_RE_TAG = re.compile(r"<\s*([A-Za-z_][\w.:-]*)\s+([^>]*?)>")
_RE_ATTR = re.compile(r'([A-Za-z_][\w.:-]*)\s*=\s*"([^"]*)"')


def _strip_culture_prefix(value):
    """'Culture.empire' -> 'empire'; bare 'empire' stays 'empire'."""
    if value is None:
        return None
    value = value.strip()
    if "." in value:
        return value.split(".", 1)[-1]
    return value


class ObjectIndex:
    def __init__(self):
        # reference_type -> { id: sorted(set of source file paths) }
        self.objects = {}
        # reference_type -> { culture_id: { id: [source files] } }
        self.tagged = {}
        # BodyProperty tag lists currently populate a raw dict for the
        # body_property_culture_tags check (strict parse only).
        # culture_id -> set of BodyProperty object ids
        self.body_property_tags = {}
        self.files_parsed = 0
        self.files_strict_failed = 0
        self.files_skipped = 0
        self.skipped = []
        self.fallback_files = []
        # Per-culture equipment-template rosters (used by DefaultEquipmentSelectionModel).
        # culture_id -> { frozenset(flags): [(obj_id, frozenset(equip_types), source_file)] }
        self.category_rosters = {}
        # culture_id -> [(obj_id, source_file, (flag_name, raw_value))]
        # Problems on an EquipmentRoster's <Flags>: unknown flag name or a value
        # that is not a valid boolean ("true"/"false").
        self.invalid_flags = {}
        # NPCCharacter id -> occupation attribute value (only when present).
        self.npc_occupations = {}
        # NPCCharacter ids that exist but lack an occupation attribute.
        self.npc_no_occupation = set()
        # NPCCharacter id -> is_template attribute value (only when present).
        self.npc_is_template = {}

    # ---- generic helpers ---------------------------------------------------

    def _add_object(self, ref_type, obj_id, source_file):
        ids = self.objects.setdefault(ref_type, {})
        ids.setdefault(obj_id, set()).add(source_file)

    def _add_tagged(self, ref_type, culture_id, obj_id, source_file):
        by_culture = self.tagged.setdefault(ref_type, {})
        entries = by_culture.setdefault(culture_id, {})
        entries.setdefault(obj_id, set()).add(source_file)

    def _add_body_property_tag(self, culture_id, obj_id):
        self.body_property_tags.setdefault(culture_id, set()).add(obj_id)

    def ref_type_for(self, element_tag):
        return ELEMENT_TYPE_MAP.get(element_tag, element_tag)

    def has(self, ref_type, obj_id):
        return obj_id in self.objects.get(ref_type, {})

    def where(self, ref_type, obj_id):
        return sorted(self.objects.get(ref_type, {}).get(obj_id, set()))

    def count(self, ref_type):
        return len(self.objects.get(ref_type, {}))

    def tagged_ids(self, ref_type, culture_id):
        return self.tagged.get(ref_type, {}).get(culture_id, {})

    def tagged_ids_in_files(self, ref_type, culture_id, patterns):
        """Tagged ids for a culture, optionally restricted to source files whose
        basename matches any of the given glob patterns."""
        all_ids = self.tagged_ids(ref_type, culture_id)
        if not patterns:
            return all_ids
        filtered = {}
        for obj_id, sources in all_ids.items():
            if any(fnmatch.fnmatch(os.path.basename(src), pat)
                   for src in sources for pat in patterns):
                filtered[obj_id] = sources
        return filtered

    def tagged_sources(self, ref_type, culture_id):
        by_id = self.tagged_ids(ref_type, culture_id)
        sources = set()
        for files in by_id.values():
            sources |= files
        return sorted(sources)

    def stats(self):
        """Return a sorted list of (ref_type, count) for the report footer."""
        return sorted(
            ((k, len(v)) for k, v in self.objects.items() if v),
            key=lambda kv: (-kv[1], kv[0]),
        )

    # ---- scanning ----------------------------------------------------------

    def index_folder(self, folder, data_patterns=("*.xml",), exclude_dirs=(), exclude_files=()):
        exclude_dirs = {d.lower() for d in exclude_dirs}
        exclude_files = {f.lower() for f in exclude_files}
        for root, dirs, files in os.walk(folder):
            dirs[:] = [
                d for d in dirs if d.lower() not in exclude_dirs
            ]
            for name in files:
                if name.lower() in exclude_files:
                    continue
                if not any(fnmatch.fnmatch(name.lower(), p.lower()) for p in data_patterns):
                    continue
                path = os.path.join(root, name)
                self.index_file(path)

    def index_file(self, path):
        self.files_parsed += 1
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                content = fh.read()
        except OSError:
            self.files_parsed -= 1
            self.files_skipped += 1
            self.skipped.append((path, "unreadable"))
            return

        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            self.files_strict_failed += 1
            self.fallback_files.append(path)
            self._index_via_regex(content, path)
            return

        tag = root.tag if isinstance(root.tag, str) else ""
        for child in root:
            child_tag = child.tag if isinstance(child.tag, str) else ""
            self._index_strict_element(child_tag, child, path)

    def _index_strict_element(self, element_tag, element, source_file):
        ref_type = self.ref_type_for(element_tag)
        obj_id = element.get("id")
        if not obj_id:
            return
        self._add_object(ref_type, obj_id, source_file)

        culture = element.get("culture")
        if culture:
            culture_id = _strip_culture_prefix(culture)
            sign = culture_id if culture_id and culture_id != obj_id else None
            if sign:
                self._add_tagged(ref_type, sign, obj_id, source_file)

        if element_tag == BODY_TAG_ELEMENT:
            for parent_name in BODY_TAG_PARENTS:
                parent = element.find(parent_name)
                if parent is None:
                    continue
                for tag_node in parent:
                    name = tag_node.get("name")
                    if name:
                        self._add_body_property_tag(name.strip(), obj_id)

        if element_tag == "NPCCharacter":
            occupation = element.get("occupation")
            if occupation:
                self.npc_occupations[obj_id] = occupation
            else:
                self.npc_no_occupation.add(obj_id)
            is_template = element.get("is_template")
            if is_template:
                self.npc_is_template[obj_id] = is_template.strip().lower() == "true"

        if element_tag == EQUIP_ROSTER_ELEMENT and culture:
            self._add_category_roster(culture_id, obj_id, element, source_file)

    def _add_category_roster(self, culture_id, obj_id, element, source_file):
        flags, problems = self._read_flags(element)
        for flag_name, raw_value in problems:
            self.invalid_flags.setdefault(culture_id, []).append(
                (obj_id, source_file, (flag_name, raw_value)))
        for flag_name in sorted(flags - EQUIPMENT_CATEGORY_FLAGS):
            self.invalid_flags.setdefault(culture_id, []).append(
                (obj_id, source_file, (flag_name, "true")))
        if not flags:
            return
        equip_types = self._read_equipment_set_types(element)
        by_flags = self.category_rosters.setdefault(culture_id, {})
        by_flags.setdefault(flags, []).append((obj_id, equip_types, source_file))

    @staticmethod
    def _read_flags(element):
        flags = set()
        problems = []
        flags_node = element.find("Flags")
        if flags_node is None:
            return flags, problems
        for name, value in flags_node.attrib.items():
            lowered = value.strip().lower()
            if lowered == "true":
                flags.add(name)
            elif lowered == "false":
                continue
            else:
                problems.append((name, value))
        return frozenset(flags), problems

    @staticmethod
    def _read_equipment_set_types(element):
        types = set()
        for set_node in element.findall("EquipmentSet"):
            if set_node.get("civilian", "").strip().lower() == "true":
                types.add("Civilian")
                continue
            eq_type = set_node.get("equipmentType")
            if eq_type:
                types.add(eq_type)
            else:
                types.add("Battle")
        return frozenset(types)

    def category_rosters_for(self, culture_id, flags):
        return self.category_rosters.get(culture_id, {}).get(flags, [])

    def _index_via_regex(self, content, source_file):
        for m in _RE_TAG.finditer(content):
            tag = m.group(1)
            ref_type = self.ref_type_for(tag)
            attrs = dict(_RE_ATTR.findall(m.group(2)))
            obj_id = attrs.get("id")
            if not obj_id:
                continue
            self._add_object(ref_type, obj_id, source_file)
            culture = attrs.get("culture")
            if culture:
                culture_id = _strip_culture_prefix(culture)
                if culture_id and culture_id != obj_id:
                    self._add_tagged(ref_type, culture_id, obj_id, source_file)
            if tag == "NPCCharacter":
                occupation = attrs.get("occupation")
                if occupation:
                    self.npc_occupations[obj_id] = occupation
                else:
                    self.npc_no_occupation.add(obj_id)
                is_template = attrs.get("is_template")
                if is_template:
                    self.npc_is_template[obj_id] = is_template.strip().lower() == "true"


def index_folders(folders, config):
    index = ObjectIndex()
    for folder in folders:
        index.index_folder(
            folder,
            data_patterns=config.get("data_file_patterns", ("*.xml",)),
            exclude_dirs=config.get("exclude_dirs", ()),
            exclude_files=config.get("exclude_files", ()),
        )
    return index