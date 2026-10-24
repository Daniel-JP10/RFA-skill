"""Build AI-use disclosure statements driven by the AI policy registry.

Statements are produced only when every required field is present; a missing value is never
filled in. Each statement asserts facts about what the authors did, so the assertions are
returned in assertions_to_confirm and the calling agent must have the user confirm them before
presenting the text as final. No network access, no environment reads.

Exit codes: 0 ok, 1 missing fields or invalid input, 2 usage error. Output is JSON on stdout.
"""

import argparse
import re
import sys

from _data import (
    AI_USE_KINDS,
    METHODS_CODES,
    dedupe,
    disclosure_requirement,
    known_ids,
    load_data,
    load_templates,
    resolve_id,
    write_json,
)

LANGS = ("en", "es")
# Registry location code -> statement template. Dedicated declaration sections use the
# acknowledgments template, which is a general declaration text.
TEMPLATE_FOR = {
    "acknowledgments": "acknowledgments",
    "separate_section_before_references": "acknowledgments",
    "dedicated_section": "acknowledgments",
    "dedicated_declaration": "acknowledgments",
    "disclosure_section": "acknowledgments",
    "methods": "methods",
    "materials_and_methods": "methods",
    "methodology": "methods",
    "cover_letter": "cover_letter",
}
STATEMENT_ORDER = ("acknowledgments", "methods", "cover_letter")
DATE_CLAUSE = {"en": " on {date}", "es": " el {date}"}
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
USER_FIELDS = ("tool", "version", "developer", "purpose", "date", "verification")


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _fill(template: str, values: dict) -> str:
    """Fill {name} placeholders in a single pass, so user text is never re-scanned."""
    missing = [m.group(1) for m in PLACEHOLDER.finditer(template) if m.group(1) not in values]
    if missing:
        raise RuntimeError(f"unfilled placeholder(s) in template: {missing}")
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def render(policy, kind, tool, version, developer, purpose, date=None, verification=None,
           lang="en", data=None, statements=None) -> dict:
    """Build disclosure statements for one AI use under one registry policy.

    statements: optional list of statement types to produce; None keeps the policy-driven default.
    """
    data = data if data is not None else load_data()
    templates = load_templates()
    out = {
        "status": "ok",
        "required": None,
        "placements": [],
        "statements_requested": None if statements is None else list(statements),
        "statements": {},
        "exemptions": [],
        "assertions_to_confirm": [],
        "source": None,
        "notes": [],
        "errors": [],
    }

    lang = (lang or "").strip().lower()
    if lang not in LANGS:
        out["errors"].append({"code": "unsupported_language",
                              "message": f"Unsupported language: {lang}",
                              "suggestions": list(LANGS)})
    kind = (kind or "").strip().lower()
    if kind not in AI_USE_KINDS:
        out["errors"].append({"code": "unknown_kind", "message": f"Unknown AI-use kind: {kind}",
                              "suggestions": list(AI_USE_KINDS)})
    supplied = {"tool": tool, "version": version, "developer": developer, "purpose": purpose,
                "date": date, "verification": verification}
    braces = [f for f in USER_FIELDS
              if not _blank(supplied[f]) and re.search(r"[{}]", str(supplied[f]))]
    if braces:
        out["errors"].append({"code": "invalid_characters",
                              "message": "Braces are not allowed in statement fields: "
                                         f"{', '.join(braces)}. Ask the user to rephrase.",
                              "fields": braces})
    if statements is not None:
        invalid = [s for s in statements if s not in STATEMENT_ORDER]
        if invalid or not statements:
            out["errors"].append({"code": "invalid_statements",
                                  "message": f"Invalid statement types: {', '.join(invalid) or 'none given'}",
                                  "suggestions": list(STATEMENT_ORDER)})
    policy_key = None
    if _blank(policy):
        out["errors"].append({"code": "missing_policy",
                              "message": "A policy registry key is required.",
                              "suggestions": known_ids("policy", data)})
    else:
        resolved = resolve_id("policy", policy, data)
        if isinstance(resolved, str):
            policy_key = resolved
        else:
            out["errors"].append({"code": "unknown_policy", "message": f"Unknown policy: {policy}",
                                  "suggestions": resolved})
    if out["errors"]:
        out["status"] = "invalid_input"
        return out

    entry = data["ai_policies"][policy_key]
    out["source"] = {
        "policy": policy_key,
        "policy_url": entry.get("policy_url"),
        "policy_date": entry.get("policy_date"),
        "verified_on": entry.get("verified_on"),
        "needs_review": entry.get("needs_review"),
    }
    out["exemptions"] = list(entry.get("exempt") or [])
    out["notes"].append(
        f"The policy entry is a snapshot dated {entry.get('policy_date')} and verified on "
        f"{entry.get('verified_on')}; check the current text before submission.")
    if entry.get("needs_review"):
        out["notes"].append(f"This policy entry needs review: {entry.get('note')}")
    elif entry.get("note"):
        out["notes"].append(f"Policy note: {entry.get('note')}")

    required, codes = disclosure_requirement(entry, kind)
    out["required"] = required
    labels = templates["locations"]
    out["placements"] = [{"code": c, "label": labels.get(c, {}).get(lang)} for c in codes]
    if kind == "none":
        out["notes"].append("No AI use was declared; there is nothing to disclose.")
        return out
    if required is False:
        out["notes"].append("The policy does not require disclosing this kind of use.")
        return out
    if required == "conditional":
        out["notes"].append(
            "Disclosure is required unless the use falls entirely under the policy's exemptions "
            f"({', '.join(out['exemptions']) or 'none listed'}); confirm with the user before "
            "omitting the statement.")

    codes_for = {}
    for code in codes:
        t = TEMPLATE_FOR.get(code)
        if t is None:
            out["notes"].append(
                f"No statement template for the '{code}' placement; follow the policy's "
                f"instructions for it.")
            continue
        codes_for.setdefault(t, []).append(code)
    if kind == "research_conduct":
        codes_for = {"methods": codes_for.get("methods") or ["methods"]}
        if not any(c in METHODS_CODES for c in entry.get("locations") or []):
            out["notes"].append(
                "The policy entry lists no methods location; the methods placement follows the "
                "compatibility rule for AI used to conduct the research.")
    if "acknowledgments" in codes_for and any(c != "acknowledgments" for c in codes_for["acknowledgments"]):
        out["notes"].append(
            "The acknowledgments template is used as the general declaration text for "
            "dedicated declaration sections.")
    types = [t for t in STATEMENT_ORDER if t in codes_for]

    missing = []
    if statements is None:
        manuscript_codes = [c for c in codes if TEMPLATE_FOR.get(c) in ("acknowledgments", "methods")
                            and TEMPLATE_FOR.get(c) in types]
        if "cover_letter" in types and not manuscript_codes:
            types.remove("cover_letter")
            out["notes"].append("A cover-letter statement needs a manuscript section to refer to; "
                                "none applies, so it was not produced.")
    else:
        for t in statements:
            if t not in types:
                codes_for.setdefault(t, [])
                out["notes"].append(f"'{t}' is not among this policy's listed placements; it was "
                                    f"produced because it was requested.")
        if kind == "research_conduct" and "methods" not in statements:
            out["notes"].append("AI used to conduct the research is normally described in the methods.")
        types = [t for t in STATEMENT_ORDER if t in statements]
        manuscript_codes = [c for c in codes if TEMPLATE_FOR.get(c) in ("acknowledgments", "methods")]
        if "cover_letter" in types and not manuscript_codes:
            missing.append("placement")

    fields = supplied
    needed = list(templates["required_fields"]) + (["verification"] if "methods" in types else [])
    missing = [f for f in needed if _blank(fields[f])] + missing
    if missing:
        out["status"] = "missing_fields"
        out["missing_fields"] = missing
        for f in missing:
            message = (f"Missing required field: {f}. Ask the user; do not guess." if f != "placement"
                       else "The cover letter must name the manuscript section where the use is "
                            "disclosed, and this policy lists none; ask the user which section.")
            out["errors"].append({"code": "missing_field", "field": f, "message": message})
        return out
    if not types:
        out["notes"].append("No statement template matches this policy's placements.")
        return out

    values = {k: str(v).strip() for k, v in fields.items() if not _blank(v)}
    values["date_clause"] = DATE_CLAUSE[lang].replace("{date}", values["date"]) if "date" in values else ""
    if manuscript_codes:
        values["placement"] = labels[manuscript_codes[0]][lang]
    assertions = []
    for t in types:
        out["statements"][t] = {
            "text": _fill(templates["templates"][t][lang], values),
            "placements": codes_for[t],
            "labels": [labels[c][lang] for c in codes_for[t]],
        }
        assertions.extend(templates["assertions"][t][lang])
    out["assertions_to_confirm"] = dedupe(assertions)
    out["notes"].append(
        "Policies list acceptable locations; use the one(s) the venue's instructions require.")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build AI-use disclosure statements from the RFA policy registry. "
                    "Output is JSON.")
    p.add_argument("--policy", help="AI policy registry key (e.g. springer-nature)")
    p.add_argument("--kind", choices=AI_USE_KINDS, help="Kind of AI use")
    p.add_argument("--tool", help="Tool name (e.g. the assistant's product name)")
    p.add_argument("--version", help="Tool version or model identifier")
    p.add_argument("--developer", help="Tool developer or vendor")
    p.add_argument("--purpose", help="What the tool was used for")
    p.add_argument("--date", help="Date or period of use (optional)")
    p.add_argument("--verification", help="How the output was verified (required for methods)")
    p.add_argument("--lang", choices=LANGS, default="en", help="Statement language (default: en)")
    p.add_argument("--statements",
                   help="Comma-separated statement types to produce: "
                        f"{','.join(STATEMENT_ORDER)} (default: driven by the policy placements)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    statements = None if args.statements is None else [
        s.strip() for s in args.statements.split(",") if s.strip()]
    result = render(args.policy, args.kind, args.tool, args.version, args.developer,
                    args.purpose, date=args.date, verification=args.verification, lang=args.lang,
                    statements=statements)
    write_json(result)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
