#!/usr/bin/env python3
"""Validate Bannerlord Culture definitions against ModuleData folders.

Usage:
  python culture_validator.py --data <folder> [<folder> ...] \
                              --cultures <culture.xml|folder> \
                              [--config checks_config.json] \
                              [--json-report <path>] [--no-color]

Only reads files. Never modifies them. Writes one optional JSON report.
Exit codes: 0 = all required checks passed,
            1 = at least one required check failed,
            2 = the tool could not run (bad paths / unreadable cultures file).
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

import culture_requirements as req
import object_index as oi
import report as rep


def die(message):
    print("ERROR: %s" % message, file=sys.stderr)
    sys.exit(2)


DEFAULT_CONFIG = {
    "culture_file_patterns": ["*.xml"],
    "data_file_patterns": ["*.xml"],
    "exclude_dirs": [
        "Languages", "GUI", "Scenes", "SceneData", "DistanceCaches", "Materials",
        "Movies", "NavigationData", "Atmospheres", "Particles", "Prefabs", "fonts",
    ],
    "exclude_files": ["project.mbproj"],
}


def load_config(path):
    if not path:
        return dict(DEFAULT_CONFIG)
    if not os.path.isfile(path):
        die("config file not found: %s" % path)
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            file_cfg = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        die("cannot read config %s: %s" % (path, exc))
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(file_cfg)
    return cfg


def find_culture_files(source):
    """--cultures can be a single xml file (parsed directly) or a folder
    (all xml files in it are parsed, cultures collected from each)."""
    if os.path.isfile(source):
        return [source]
    if os.path.isdir(source):
        patterns = ("*.xml",)
        return sorted(
            os.path.join(source, name)
            for name in os.listdir(source)
            if name.lower().endswith(".xml")
        )
    die("cultures source not found: %s" % source)


def parse_culture_files(paths):
    """Parse the given xml files, collecting every <Culture> element."""
    cultures = []
    files_parsed = 0
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            die("cannot read cultures file %s: %s" % (path, exc))
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            die("cultures file is not valid xml (%s): %s" % (path, exc))
        files_parsed += 1
        for child in root:
            tag = child.tag if isinstance(child.tag, str) else ""
            if tag == "Culture":
                cultures.append({"file": path, "elem": child})
    return cultures, {"files_parsed": files_parsed}


def culture_entry(culture, culture_type, check_configs, index):
    elem = culture["elem"]
    culture_id = elem.get("id")
    checks = req.run_checks(index, elem, culture_id, check_configs)
    entry = {
        "id": culture_id,
        "type": culture_type,
        "type_label": req.TYPE_LABELS[culture_type],
        "attrs": {k: elem.get(k) for k in elem.attrib},
        "checks": checks,
        "source_file": culture["file"],
    }
    entry["verdict"] = "PASS" if rep.verdict_for(entry) == "PASS" else "FAIL"
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate Bannerlord Culture definitions against ModuleData folders."
    )
    parser.add_argument("--data", nargs="+", required=True, metavar="FOLDER",
                        help="ModuleData folder(s) to build the object index from "
                             "(repeatable, e.g. SandBoxCore\\ModuleData SandBox\\ModuleData).")
    parser.add_argument("--cultures", required=True, metavar="PATH",
                        help="XML file containing the <Culture> objects to validate, "
                             "or a folder containing such files.")
    parser.add_argument("--config", metavar="FILE",
                        help="checks_config.json priority override (optional).")
    parser.add_argument("--json-report", metavar="PATH",
                        help="Where to write the JSON report (default: next to the "
                             "cultures file).")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colors in console output.")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    check_configs = req.resolve_config(config)

    for folder in args.data:
        if not os.path.isdir(folder):
            die("data folder not found: %s" % folder)

    index = oi.index_folders(args.data, config)

    culture_files = find_culture_files(args.cultures)
    parsed, parse_stats = parse_culture_files(culture_files)
    if not parsed:
        die("no <Culture> elements found in %s" % args.cultures)

    cultures = [culture_entry(c, req.classify_culture(c["elem"]), check_configs, index)
                for c in parsed]

    has_required_missing = any(
        c["verdict"] == "FAIL" for c in cultures
    )
    exit_code = 1 if has_required_missing else 0

    index_summary = ", ".join("%s=%d" % (t, n) for t, n in index.stats()[:12])
    if not index_summary:
        index_summary = "(no objects indexed!)"
    stats_text = index_summary
    stats_text += " | %d xml files parsed, %d with lenient fallback" % (
        index.files_parsed, index.files_strict_failed)

    context = {
        "data_folders": args.data,
        "cultures_source": args.cultures,
        "index_summary": stats_text,
        "cultures": cultures,
        "exit_code": exit_code,
        "parse_fallback_files": index.fallback_files,
    }

    json_doc = rep.assemble_json(context, check_configs, index)
    context["json"] = json_doc

    console = rep.Console(use_color=not args.no_color and sys.stdout.isatty())
    text = rep.build_text(context, console)
    print(text)

    json_path = args.json_report or rep.default_json_path(args.cultures)
    try:
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_doc, fh, indent=2, ensure_ascii=False)
        print("JSON report written to: %s" % json_path)
    except OSError as exc:
        print("WARNING: could not write JSON report to %s (%s)"
              % (json_path, exc), file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())