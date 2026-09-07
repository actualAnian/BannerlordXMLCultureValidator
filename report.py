"""Console + JSON reporting for the culture validator."""
import datetime
import json
import os

# ANSI colors (used only when the terminal supports them).
_COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "bright_yellow": "\033[1;93m",
    "cyan": "\033[96m",
    "dim": "\033[2m",
}


class Console:
    def __init__(self, use_color):
        self.color = use_color

    def paint(self, text, style):
        if not self.color:
            return text
        return "%s%s%s" % (_COLORS[style], text, _COLORS["reset"])

    def ok(self, text):
        return self.paint(text, "green")

    def fail(self, text):
        return self.paint(text, "red")

    def warn(self, text):
        return self.paint(text, "yellow")

    def warn_bright(self, text):
        return self.paint(text, "bright_yellow")

    def head(self, text):
        return self.paint(text, "bold")

    def info(self, text):
        return self.paint(text, "cyan")

    def dim(self, text):
        return self.paint(text, "dim")


PRIMARY_STATUS = {
    "required": "MISS ",
    "warning": "WARN ",
    "optional": "OPT* ",
    "info": "INFO ",
}
OK_STATUS = " OK  "
SKIP_STATUS = "SKIP "


def _row_status_text(check, console):
    priority = check["priority"]
    if check["status"] == "disabled":
        return ("[" + SKIP_STATUS + "] " + console.dim("skip   ")), "dim"
    if check["status"] != "ok":
        if priority == "required":
            return ("[" + PRIMARY_STATUS[priority] + "] "
                    + console.fail("%-7s" % priority)), "fail"
        if priority == "warning":
            if check["status"] != "ok":
                return ("[" + PRIMARY_STATUS[priority] + "] "
                        + console.warn_bright("%-7s" % priority)), "warn_bright"
            return ("[" + OK_STATUS + "] " + console.ok("%-7s" % priority)), "ok"
        if priority == "optional":
            return ("[" + PRIMARY_STATUS[priority] + "] "   
                    + console.warn("%-7s" % priority)), "warn"
        return ("[" + PRIMARY_STATUS.get(priority, "MISS ") + "] "
                + console.fail("%-7s" % priority)), "warn"
    if priority == "warning":
        return ("[" + OK_STATUS + "] " + console.warn_bright("%-7s" % priority)), "warn_bright"
    return ("[" + OK_STATUS + "] " + console.ok("%-7s" % priority)), "ok"


def _summary_counts(check):
    """For summary purposes: required problems / warnings / optional warnings / info rows."""
    if check["status"] in ("not_applicable", "disabled"):
        return 0, 0, 0, 0
    priority = check["priority"]
    if priority == "info":
        return 0, 0, 0, 1
    if check["status"] == "missing":
        if priority == "optional":
            return 0, 0, 1, 0
        if priority == "warning":
            return 0, 1, 0, 0
        return 1, 0, 0, 0  # required (or unknown priority)
    return 0, 0, 0, 0


def verdict_for(culture_entry):
    for check in culture_entry["checks"]:
        if check["status"] == "missing" and check["priority"] == "required":
            return "FAIL"
    return "PASS"


def build_text(context, console):
    lines = []
    w = console
    data_folders = context["data_folders"]
    cultures = context["cultures"]

    lines.append(w.head("=" * 78))
    lines.append(w.head("  BANNERLORD CULTURE VALIDATOR"))
    lines.append(w.head("=" * 78))
    if data_folders:
        lines.append("  data folders (%d):" % len(data_folders))
        for f in data_folders:
            lines.append("    - " + f)
    lines.append("  culture source:  " + context["cultures_source"])
    lines.append("  objects indexed: " + context["index_summary"])
    lines.append("")
    lines.append(w.dim("Legend:"))
    lines.append(w.dim("  [%s] required check passed" % OK_STATUS.strip()))
    lines.append(w.dim("  [MISS] required check failed - culture missing data needed to work"))
    lines.append(w.dim("  [WARN] warning - not required but recommended (see note)"))
    lines.append(w.dim("  [%s] optional check found nothing - culture still works (see note)" % "OPT*"))
    lines.append(w.dim("  [INFO] informational only, never fails"))
    lines.append("")

    failures = 0
    warnings = 0
    optional_warnings = 0
    info_rows = 0
    status_map = {}

    for i, culture in enumerate(cultures, start=1):
        cid = culture["id"]
        label = culture["type_label"]
        lines.append(w.head("#### %d/%d  \"%s\"  (%s)" % (i, len(cultures), cid, label)))
        extra_flags = []
        if culture.get("attrs", {}).get("is_main_culture") == "true":
            extra_flags.append("is_main_culture=true")
        if culture.get("attrs", {}).get("can_have_settlement") == "true":
            extra_flags.append("can_have_settlement=true")
        if culture.get("attrs", {}).get("is_bandit") == "true":
            extra_flags.append("is_bandit=true")
        if extra_flags:
            lines.append(w.dim("    flags: " + ", ".join(extra_flags)))

        culture_fail = False
        for check in culture["checks"]:
            if not check["applicable"]:
                continue

            if check["status"] == "not_applicable":
                continue

            tag_text, style = _row_status_text(check, w)
            row = "%s %s" % (tag_text, check["label"].ljust(50))
            if check["status"] == "disabled":
                lines.append(row + "  " + w.dim("(disabled)"))
                continue

            row += "  %s/%s" % (check["found"], check["total"])
            if check["note"]:
                row += "  " + w.dim("(%s)" % check["note"])
            lines.append(row)

            if check["status"] == "missing":
                for item in check["missing"]:
                    if check["priority"] == "optional":
                        lines.append("        missing: " + w.warn(item))
                    elif check["priority"] == "warning":
                        lines.append("        missing: " + w.warn_bright(item))
                    else:
                        lines.append("        missing: " + w.fail(item))
                if check["priority"] == "required":
                    culture_fail = True
                elif check["priority"] == "warning":
                    lines.append("        " + w.warn_bright("WARNING - %s (not required but recommended)."
                                                           % check.get("description", "")))
                elif check["priority"] == "optional":
                    lines.append("        " + w.warn("OPTIONAL - %s (culture still works)."
                                                     % check.get("description", "")))

        # roll up counts
        for check in culture["checks"]:
            rp, wc, ow, inf = _summary_counts(check)
            if rp:
                failures += 1
            if wc:
                warnings += 1
            if ow:
                optional_warnings += 1
            if inf:
                info_rows += 1

        verdict = "FAIL" if culture_fail else "PASS"
        status_map[cid] = verdict
        line = "    VERDICT: " + (w.fail(verdict) if culture_fail else w.ok(verdict))
        lines.append(line)
        lines.append("")

    lines.append(w.head("=" * 78))
    lines.append(w.head("  SUMMARY"))
    lines.append("  cultures checked : %d" % len(cultures))
    passes = sum(1 for v in status_map.values() if v == "PASS")
    lines.append("  PASS / FAIL      : %d / %d" % (passes, len(cultures) - passes))
    lines.append("  required problems: %d" % failures)
    lines.append("  warnings         : %d" % warnings)
    lines.append("  optional warnings : %d" % optional_warnings)
    lines.append("  info rows         : %d" % info_rows)
    if context.get("parse_fallback_files"):
        lines.append(w.warn("  files parsed with lenient regex fallback: %d"
                            % len(context["parse_fallback_files"])))
    lines.append(w.head("=" * 78))
    lines.append("  exit code: %d   (%s)" % (
        context["exit_code"],
        "0 => all required checks passed, "
        "1 => required data missing, "
        "2 => tool could not run",
    ))
    return "\n".join(lines)


def strip_ansi(text):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)


def build_json(context):
    return json.dumps(context["json"], indent=2, ensure_ascii=False)


def assemble_json(context, check_configs, index):
    cultures_json = []
    for culture in context["cultures"]:
        cultures_json.append({
            "id": culture["id"],
            "type": culture["type"],
            "type_label": culture["type_label"],
            "attrs": culture["attrs"],
            "verdict": culture["verdict"],
            "checks": [
                {
                    "id": c["id"],
                    "label": c["label"],
                    "description": c.get("description", ""),
                    "priority": c["priority"],
                    "status": c["status"],
                    "found": c["found"],
                    "total": c["total"],
                    "missing": c["missing"],
                    "note": c.get("note", ""),
                    "applicable": c["applicable"],
                }
                for c in culture["checks"]
            ],
        })
    return {
        "tool": "bannerlord_culture_validator",
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "data_folders": context["data_folders"],
        "cultures_source": context["cultures_source"],
        "config_priorities": {
            check_id: cfg["priority"] for check_id, cfg in check_configs.items()
        },
        "index": {
            "counts": {k: len(v) for k, v in index.objects.items() if v},
            "files_parsed": index.files_parsed,
            "files_strict_failed": index.files_strict_failed,
        },
        "summary": {
            "cultures": len(cultures_json),
            "pass": sum(1 for c in cultures_json if c["verdict"] == "PASS"),
            "fail": sum(1 for c in cultures_json if c["verdict"] == "FAIL"),
            "required_problems": sum(
                sum(1 for ch in c["checks"]
                    if ch["status"] == "missing" and ch["priority"] == "required")
                for c in cultures_json),
            "warnings": sum(
                sum(1 for ch in c["checks"]
                    if ch["status"] == "missing" and ch["priority"] == "warning")
                for c in cultures_json),
            "optional_warnings": sum(
                sum(1 for ch in c["checks"]
                    if ch["status"] == "missing" and ch["priority"] == "optional")
                for c in cultures_json),
        },
        "cultures": cultures_json,
    }


def default_json_path(cultures_source):
    # Write the report in the working directory, never next to the source file
    # (which may live inside the game or a mod folder we must not touch).
    return os.path.join(os.getcwd(), "culture_validation_report.json")