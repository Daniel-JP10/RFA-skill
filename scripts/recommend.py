"""Recommend a reference standard, reporting guidelines, sections and AI-disclosure needs.

Behavior is driven by rfa_data.json (rules, defaults, study designs and the AI policy registry
from rfa-core). The tool never infers a missing field: it asks through open_questions, and it
never silently resolves conflicting recommendations. No network access, no environment reads.

Exit codes: 0 ok, 1 denied or invalid input, 2 usage error. Output is JSON on stdout.
"""

import argparse
import json
import sys

from _data import (
    AI_USE_KINDS,
    CONFIDENCE_RANK,
    METHODS_CODES,
    csl_style_key,
    dedupe,
    disclosure_requirement,
    known_ids,
    load_data,
    parse_language,
    REGISTRY_SOURCE,
    resolve_id,
    suggest,
    write_json,
)

QUERY_FIELDS = (
    "discipline", "document_type", "language", "standard", "standard_variant",
    "standard_source", "study_design", "reporting_guideline", "policy", "ai_use", "ai_author",
)
STANDARD_SOURCES = ("institution", "journal", "user")
LIST_KINDS = (
    "disciplines", "document_types", "standards", "study_designs", "reporting_guidelines",
    "policies", "languages",
)
# Rule `when` key -> the query field a user must provide for it.
WHEN_KEY_FIELD = {
    "document_type": "document_type",
    "document_type_group": "document_type",
    "discipline": "discipline",
    "discipline_area": "discipline",
    "standard": "standard",
    "standard_variant": "standard_variant",
    "language": "language",
    "language_not": "language",
    "language_variant": "language",
    "ai_use_kind": "ai_use",
    "ai_listed_as_author": "ai_author",
    "reporting_guideline": "reporting_guideline",
}
INSTITUTION_QUESTION = "Does your institution or journal impose its own norm?"


def _empty_output(data: dict) -> dict:
    return {
        "status": "ok",
        "errors": [],
        "reference_style": {
            "selection": "unknown",
            "chosen": None,
            "candidates": [],
            "allowed": [],
            "check_first": [],
            "alternatives": [],
        },
        "reporting": {
            "required": [],
            "recommended": [],
            "any_of": [],
            "study_design": None,
            "study_design_note": None,
            "details": [],
        },
        "sections": {"required": [], "recommended": []},
        "ai_disclosure": None,
        "rules_applied": [],
        "warnings": [],
        "denials": [],
        "open_questions": [],
        "ask_first": None,
        "data_caveats": [],
        "data_snapshot": {
            "core_version": data["meta"]["core_version"],
            "rfa_version": data["meta"]["rfa_version"],
            "snapshot_dates": json.loads(json.dumps(data["meta"]["snapshot_dates"])),
        },
    }


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize(query: dict, data: dict):
    """Validate the query. Returns (normalized dict, errors)."""
    errors = []
    q = {f: None for f in QUERY_FIELDS}
    q["language_variant"] = None
    if not isinstance(query, dict):
        return q, [{"code": "invalid_query", "message": "The query must be a JSON object."}]
    for key in query:
        if key not in QUERY_FIELDS:
            errors.append({"code": "unknown_field", "message": f"Unknown query field: {key}",
                           "suggestions": suggest(str(key), QUERY_FIELDS)})

    def raw(field):
        v = query.get(field)
        return None if _blank(v) else v

    for field in ("discipline", "document_type", "standard", "study_design",
                  "reporting_guideline", "policy"):
        v = raw(field)
        if v is None:
            continue
        resolved = resolve_id(field, v, data)
        if isinstance(resolved, str):
            q[field] = resolved
        else:
            errors.append({"code": f"unknown_{field}",
                           "message": f"Unknown {field.replace('_', ' ')}: {v}",
                           "suggestions": resolved})

    lang = raw("language")
    if lang is not None:
        base, variant = parse_language(lang, data)
        if base is None:
            errors.append({"code": "unknown_language", "message": f"Unknown language: {lang}",
                           "suggestions": known_ids("language", data)})
        else:
            q["language"], q["language_variant"] = base, variant

    variant = raw("standard_variant")
    if variant is not None:
        variant = str(variant).strip().lower()
        if raw("standard") is None:
            errors.append({"code": "variant_without_standard",
                           "message": "standard_variant requires standard."})
        elif q["standard"] is not None:
            variants = data["standards"][q["standard"]]["variants"]
            if variant in variants:
                q["standard_variant"] = variant
            else:
                errors.append({"code": "unknown_standard_variant",
                               "message": f"Unknown variant '{variant}' for {q['standard']}",
                               "suggestions": variants})

    source = raw("standard_source")
    if source is not None:
        source = str(source).strip().lower()
        if source not in STANDARD_SOURCES:
            errors.append({"code": "unknown_standard_source",
                           "message": f"Unknown standard_source: {source}",
                           "suggestions": list(STANDARD_SOURCES)})
        elif raw("standard") is None:
            errors.append({"code": "source_without_standard",
                           "message": "standard_source requires standard."})
        else:
            q["standard_source"] = source

    ai_use = raw("ai_use")
    if ai_use is not None:
        ai_use = str(ai_use).strip().lower()
        if ai_use in AI_USE_KINDS:
            q["ai_use"] = ai_use
        else:
            errors.append({"code": "unknown_ai_use", "message": f"Unknown ai_use: {ai_use}",
                           "suggestions": list(AI_USE_KINDS)})

    ai_author = query.get("ai_author")
    if isinstance(ai_author, bool):
        q["ai_author"] = ai_author
    elif not _blank(ai_author):
        text = str(ai_author).strip().lower()
        if text in ("true", "false"):
            q["ai_author"] = text == "true"
        else:
            errors.append({"code": "invalid_ai_author",
                           "message": f"ai_author must be true or false, got: {ai_author}",
                           "suggestions": ["true", "false"]})
    return q, errors


def _context(q: dict, data: dict) -> dict:
    dt, disc = q["document_type"], q["discipline"]
    return {
        "document_type": dt,
        "document_type_group": data["document_types"][dt]["group"] if dt else None,
        "discipline": disc,
        "discipline_area": data["disciplines"][disc]["area"] if disc else None,
        "standard": q["standard"],
        "standard_variant": q["standard_variant"],
        "language": q["language"],
        "language_variant": q["language_variant"],
        "ai_use_kind": q["ai_use"],
        "ai_listed_as_author": q["ai_author"],
        "reporting_guideline": q["reporting_guideline"],
    }


def _condition(key: str, expected, ctx: dict):
    """True or False when evaluable; None when the needed input was not provided."""
    if key == "language_not":
        lang = ctx["language"]
        return None if lang is None else lang != expected
    if key == "language_variant":
        variant = ctx["language_variant"]
        return None if variant is None else variant.lower() == str(expected).lower()
    actual = ctx.get(key)
    if actual is None:
        return None
    if expected == "any":
        return True
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def _match_rules(ctx: dict, data: dict):
    """Return (matched rules, near misses as (rule, field))."""
    matched, near = [], []
    for rule in data["rules"]:
        results = {k: _condition(k, v, ctx) for k, v in rule["when"].items()}
        if all(r is True for r in results.values()):
            matched.append(rule)
            continue
        missing = [k for k, r in results.items() if r is None]
        if len(missing) == 1 and all(r is True for k, r in results.items() if k != missing[0]):
            near.append((rule, WHEN_KEY_FIELD.get(missing[0], missing[0])))
    return matched, near


def _applied(rule: dict) -> dict:
    return {"id": rule["id"], "effect": rule["effect"], "confidence": rule.get("confidence"),
            "reason": rule.get("reason")}


def _field_options(field: str, q: dict, data: dict):
    if field == "ai_use":
        return list(AI_USE_KINDS)
    if field == "ai_author":
        return [True, False]
    if field == "language":
        if q["language"]:
            return list(data["languages"]["variants_planned"].get(q["language"], []))
        return known_ids("language", data)
    if field == "standard_variant" and q["standard"]:
        return list(data["standards"][q["standard"]]["variants"])
    return None


def _add_question(out: dict, field: str, why: str, options=None, priority="informational",
                  rules=None) -> None:
    for existing in out["open_questions"]:
        if existing["field"] == field and existing["why"] == why:
            return
    item = {"field": field, "why": why, "priority": priority}
    if rules:
        item["rules"] = rules
    if options:
        item["options"] = options
    out["open_questions"].append(item)


def _near_miss_questions(out: dict, near: list, q: dict, data: dict) -> None:
    """One short question per missing field, listing the rules the answer would decide."""
    rs = out.get("reference_style", {})
    selection = rs.get("selection")
    relevant_standards = set()
    if selection in ("single_recommendation", "user_choice"):
        if rs.get("chosen") and isinstance(rs["chosen"], dict) and rs["chosen"].get("standard_id"):
            relevant_standards.add(rs["chosen"]["standard_id"])
        for c in rs.get("candidates") or []:
            if isinstance(c, dict) and c.get("standard_id"):
                relevant_standards.add(c["standard_id"])
        for a in rs.get("allowed") or []:
            if isinstance(a, str):
                relevant_standards.add(a)
            elif isinstance(a, dict) and a.get("standard_id"):
                relevant_standards.add(a["standard_id"])

    by_field = {}
    for rule, field in near:
        if field == "standard" and selection in ("single_recommendation", "user_choice"):
            rule_stds = rule.get("when", {}).get("standard")
            if isinstance(rule_stds, str):
                rule_stds_list = [rule_stds]
            elif isinstance(rule_stds, (list, tuple, set)):
                rule_stds_list = list(rule_stds)
            else:
                rule_stds_list = []
            if not any(s in relevant_standards for s in rule_stds_list):
                continue
        by_field.setdefault(field, []).append(rule)

    for field, rules in by_field.items():
        ids = dedupe(r["id"] for r in rules)
        # A require/deny rule waiting on this field blocks, except the AI fields (asked later).
        blocking = field not in ("ai_use", "ai_author") and any(
            r["effect"] in ("require", "deny") for r in rules)
        _add_question(out, field,
                      f"Not provided: {field}. It decides whether these rules apply: {', '.join(ids)}.",
                      _field_options(field, q, data), "blocking" if blocking else "informational", ids)


def _finish(out: dict) -> dict:
    """Blocking questions first (stable), and ask_first = the first blocking question's text."""
    out["open_questions"].sort(key=lambda item: item["priority"] != "blocking")
    first = out["open_questions"][0] if out["open_questions"] else None
    out["ask_first"] = first["why"] if first and first["priority"] == "blocking" else None
    return out


def _candidate(standard_id, variant, source, data, confidence=None, evidence=None,
               sample_n=None, notes=None) -> dict:
    s = data["standards"][standard_id]
    return {
        "standard_id": standard_id,
        "variant": variant,
        "source": source,
        "confidence": confidence,
        "evidence": evidence,
        "sample_n": sample_n,
        "notes": notes,
        "meta": {
            "edition": s.get("edition"),
            "official_source": s.get("official_source"),
            "verified_on": s.get("verified_on"),
            "needs_review": s.get("needs_review"),
        },
        "csl_style_key": csl_style_key(standard_id, variant, data),
    }


def _sample_text(candidate: dict) -> str:
    n = candidate.get("sample_n")
    return f" (journal sample of {n})" if n is not None else ""


def _guideline_details(ids: list, data: dict) -> list:
    details = []
    for gid in ids:
        g = data["reporting_guidelines"][gid]
        details.append({
            "id": gid,
            "version": g.get("version"),
            "official_url": g.get("official_url"),
            "license_claimed": g.get("license_claimed"),
            "redistribution_claimed": g.get("redistribution_claimed"),
            "needs_review": g.get("needs_review"),
        })
    return details


def _reference_style(out, q, data, rule_candidates, check_first, check_rules, alternatives):
    rs = out["reference_style"]
    disc = q["discipline"]
    default = data["defaults"].get(disc) if disc else None
    rs["allowed"] = list(default["allowed"]) if default else []
    rs["check_first"] = dedupe(check_first)
    rs["alternatives"] = dedupe(alternatives)

    if q["standard"]:
        source = q["standard_source"]
        notes = f"Provided by the user; imposed by: {source}." if source else "Provided by the user."
        cand = _candidate(q["standard"], q["standard_variant"], "user_choice", data, notes=notes)
        rs.update(selection="user_choice", chosen=cand, candidates=[cand])
        if default and q["standard"] not in default["allowed"]:
            if source in ("institution", "journal"):
                tail = (f"The {source} requirement takes precedence over the discipline "
                        f"default (precedence: reference_format).")
            else:
                tail = "Confirm that the venue or institution accepts it."
            out["warnings"].append({
                "code": "standard_not_in_allowed",
                "message": f"{q['standard']} is not in the allowed list for {disc}: "
                           f"{', '.join(default['allowed'])}. {tail}",
            })
    else:
        cands = []
        if default and default.get("default"):
            cands.append(_candidate(default["default"], default.get("variant"), "discipline_default",
                                    data, default.get("confidence"), default.get("evidence"),
                                    default.get("sample_n"), default.get("note")))
        for rule, standard_id in rule_candidates:
            cands.append(_candidate(standard_id, None, f"rule:{rule['id']}", data,
                                    rule.get("confidence"), None, None, rule.get("reason")))
        order = sorted(range(len(cands)),
                       key=lambda i: (CONFIDENCE_RANK.get(cands[i]["confidence"], 3), i))
        cands = [cands[i] for i in order]
        rs["candidates"] = cands
        distinct = dedupe(c["standard_id"] for c in cands)
        if not cands:
            rs["selection"] = "unknown"
            if not disc:
                _add_question(out, "discipline",
                              "A discipline is needed to recommend a reference standard.",
                              None)
        elif len(distinct) == 1:
            chosen = dict(cands[0])
            if chosen["variant"] is None:
                chosen["variant"] = next((c["variant"] for c in cands if c["variant"]), None)
                chosen["csl_style_key"] = csl_style_key(chosen["standard_id"], chosen["variant"], data)
            rs.update(selection="single_recommendation", chosen=chosen)
            if chosen["confidence"] == "low":
                _add_question(
                    out, "standard",
                    f"The recommended norm ({chosen['standard_id']}) has low confidence"
                    f"{_sample_text(chosen)}. Which norm does your target venue or institution "
                    f"require?",
                    rs["allowed"] or None)
        else:
            rs["selection"] = "needs_confirmation"
            sources = "; ".join(f"{c['standard_id']} ({c['source']}, {c['confidence']})" for c in cands)
            _add_question(
                out, "standard",
                f"Recommendations conflict: {sources}. Which norm does your institution or "
                f"journal require?",
                distinct, "blocking")

    chosen = rs["chosen"]
    if chosen:
        s = data["standards"][chosen["standard_id"]]
        if s["variants"] and not chosen["variant"]:
            _add_question(out, "standard_variant",
                          f"{chosen['standard_id']} has several variants; which one applies?",
                          list(s["variants"]))
        if not s["csl_style_keys"]:
            out["data_caveats"].append(
                f"No CSL style is bundled for {chosen['standard_id']}; formatted references "
                f"cannot be generated automatically for it.")
        elif chosen["variant"] and chosen["csl_style_key"] is None:
            out["data_caveats"].append(
                f"No CSL style is bundled for the {chosen['variant']} variant of "
                f"{chosen['standard_id']}; formatted references cannot be generated "
                f"automatically for it.")

    for c in rs["candidates"]:
        reasons = []
        if c["confidence"] == "low":
            reasons.append(f"confidence is low{_sample_text(c)}")
        if c["meta"]["needs_review"]:
            reasons.append("its metadata needs review")
        if reasons:
            caveat = f"{c['standard_id']} ({c['source']}): {' and '.join(reasons)}."
            if caveat not in out["data_caveats"]:
                out["data_caveats"].append(caveat)

    if rs["check_first"] and q["standard_source"] not in ("institution", "journal"):
        _add_question(
            out, "standard",
            f"{INSTITUTION_QUESTION} Rules {', '.join(dedupe(check_rules))} say to check "
            f"{', '.join(rs['check_first'])} first.",
            None, "blocking" if rs["selection"] == "needs_confirmation" else "informational")


def _ai_disclosure(out, q, data, policy_blocking=False):
    kind = q["ai_use"]
    if kind is None or kind == "none":
        return
    policy = q["policy"]
    if policy is None:
        out["ai_disclosure"] = {
            "required": "conditional", "kind": kind, "policy": None, "placements": [],
            "exemptions": [], "policy_url": None, "policy_date": None, "verified_on": None,
            "needs_review": None, "note": None,
        }
        _add_question(out, "policy",
                      "Whether and where AI use must be disclosed depends on the target venue's "
                      "policy. Which journal, publisher or organization applies?",
                      known_ids("policy", data), "blocking" if policy_blocking else "informational")
        return
    entry = data["ai_policies"][policy]
    required, placements = disclosure_requirement(entry, kind)
    out["ai_disclosure"] = {
        "required": required,
        "kind": kind,
        "policy": policy,
        "placements": placements,
        "exemptions": list(entry.get("exempt") or []),
        "policy_url": entry.get("policy_url"),
        "policy_date": entry.get("policy_date"),
        "verified_on": entry.get("verified_on"),
        "needs_review": entry.get("needs_review"),
        "note": entry.get("note"),
    }
    out["data_caveats"].append(
        f"AI policy '{policy}' is a snapshot dated {entry.get('policy_date')} and verified on "
        f"{entry.get('verified_on')}; check the current text at {entry.get('policy_url')}.")
    if entry.get("needs_review"):
        out["data_caveats"].append(f"AI policy '{policy}' needs review: {entry.get('note')}")
    elif entry.get("note"):
        out["data_caveats"].append(f"AI policy '{policy}' note: {entry.get('note')}")
    if kind == "research_conduct" and required is True and \
            not any(c in METHODS_CODES for c in entry.get("locations") or []):
        out["data_caveats"].append(
            f"AI policy '{policy}' lists no methods location; the methods placement follows the "
            f"compatibility rule for AI used to conduct the research.")


def _guideline_scope(q: dict, sd: dict, data: dict) -> str:
    """INV-01 valid set: protocol_reporting for protocol document types when it is not empty."""
    if q["document_type"] in data.get("protocol_document_types", []) and sd.get("protocol_reporting"):
        return "protocol_reporting"
    return "reporting"


def _deny(out: dict, denials: list, applied: list) -> dict:
    out["status"] = "denied"
    out["denials"] = denials
    out["rules_applied"] = applied
    return out


def recommend(query: dict, data=None) -> dict:
    """Evaluate a query against the rules and data. See the module docstring for the contract."""
    data = data if data is not None else load_data()
    out = _empty_output(data)
    q, errors = _normalize(query, data)
    if errors:
        out["status"] = "invalid_input"
        out["errors"] = errors
        for e in errors:
            if e["code"].startswith("unknown_") and e.get("suggestions") is not None:
                field = e["code"][len("unknown_"):]
                _add_question(out, field if field in QUERY_FIELDS else "query", e["message"],
                              e["suggestions"] or None, "blocking")
        return _finish(out)

    ctx = _context(q, data)
    matched, near = _match_rules(ctx, data)

    denies = [r for r in matched if r["effect"] == "deny"]
    if denies:
        return _deny(out, [{"rule": r["id"], "reason": r.get("reason")} for r in denies],
                     [_applied(r) for r in denies])

    variant = q["language_variant"]
    if variant and variant not in data["languages"]["variants_planned"].get(q["language"], []):
        out["warnings"].append({
            "code": "unplanned_language_variant",
            "message": f"{variant} is not among the planned variants of {q['language']}; rules "
                       f"that name a specific variant will not match it.",
        })

    rep, sec = out["reporting"], out["sections"]
    rule_designs, rule_candidates = [], []
    check_first, check_rules, alternatives = [], [], []
    for rule in matched:
        out["rules_applied"].append(_applied(rule))
        effect, then = rule["effect"], rule.get("then") or {}
        if effect == "warn":
            out["warnings"].append({"code": "rule_warning", "message": rule.get("reason"),
                                    "rule": rule["id"]})
        if "resolve_from" in then and then["resolve_from"] != REGISTRY_SOURCE:
            out["data_caveats"].append(
                f"Rule {rule['id']} asks to resolve from {then['resolve_from']}, which this tool "
                f"does not read; the result for that rule is incomplete.")
        target = "required" if effect == "require" else "recommended"
        if "reporting_guideline" in then:
            rep[target].append(then["reporting_guideline"])
        if "reporting_guideline_any_of" in then:
            rep["any_of"].append(list(then["reporting_guideline_any_of"]))
        if "study_design" in then:
            rule_designs.append((then["study_design"], rule["id"]))
        if "section" in then:
            sec[target].append(then["section"])
        if "check_first" in then:
            check_first.append(then["check_first"])
            check_rules.append(rule["id"])
        if "alternative" in then:
            alternatives.append(then["alternative"])
        for key in ("default_standard", "standard"):
            if key in then:
                rule_candidates.append((rule, then[key]))

    # Study design: the user's value wins, but a disagreement with the rules is surfaced.
    derived = dedupe(sd for sd, _ in rule_designs)
    design = q["study_design"] or (derived[0] if len(derived) == 1 else None)
    if q["study_design"] and derived and q["study_design"] not in derived:
        out["warnings"].append({
            "code": "study_design_conflict",
            "message": f"The study design {q['study_design']} differs from the one implied by "
                       f"rules {', '.join(r for _, r in rule_designs)}: {', '.join(derived)}.",
        })
        _add_question(out, "study_design", "The provided study design conflicts with the "
                      "document type. Which design describes the study?",
                      dedupe([q["study_design"]] + derived))
    elif len(derived) > 1 and not q["study_design"]:
        _add_question(out, "study_design", "Rules imply several study designs; which applies?",
                      derived)

    # Invariant INV-01: a provided reporting guideline must be valid for the study design.
    guideline = q["reporting_guideline"]
    if guideline:
        if design is None:
            _add_question(out, "study_design",
                          "Needed to check the reporting guideline against invariant INV-01.",
                          None, "blocking")
        else:
            sd = data["study_designs"][design]
            scope = _guideline_scope(q, sd, data)
            valid = list(sd.get(scope) or [])
            if guideline not in valid:
                return _deny(
                    _empty_output(data),
                    [{"rule": "INV-01",
                      "reason": f"Reporting guideline {guideline} is not valid for study design "
                                f"{design} ({scope}: {', '.join(valid) or 'none'})."}],
                    [])

    if design:
        sd = data["study_designs"][design]
        rep["recommended"].extend(sd.get(_guideline_scope(q, sd, data)) or [])
        rep["study_design_note"] = sd.get("note")
    rep["study_design"] = design
    rep["required"] = dedupe(rep["required"])
    rep["recommended"] = [g for g in dedupe(rep["recommended"]) if g not in rep["required"]]
    sec["required"] = dedupe(sec["required"])
    sec["recommended"] = [s for s in dedupe(sec["recommended"]) if s not in sec["required"]]
    listed = rep["required"] + rep["recommended"] + [g for group in rep["any_of"] for g in group]
    if guideline:
        listed.append(guideline)
    rep["details"] = _guideline_details(dedupe(listed), data)
    unreviewed = [d["id"] for d in rep["details"] if d["needs_review"]]
    if unreviewed:
        out["data_caveats"].append(
            f"License claims for {', '.join(unreviewed)} have not been independently verified "
            f"(needs review); link to the official source instead of reproducing checklists.")

    _reference_style(out, q, data, rule_candidates, check_first, check_rules, alternatives)
    # A matched require rule that resolves from the registry needs the policy to proceed.
    _ai_disclosure(out, q, data, any(r["effect"] == "require" and "resolve_from" in (r.get("then") or {})
                                     for r in matched))
    _near_miss_questions(out, near, q, data)
    return _finish(out)


def list_items(kind: str, data: dict) -> dict:
    """Return the ids (and display names where available) for --list."""
    if kind == "languages":
        langs = data["languages"]
        return {"kind": kind, "items": [
            {"id": lang, "variants": langs["variants_planned"].get(lang, [])}
            for lang in langs["languages"]
        ]}
    collection = {"policies": "ai_policies"}.get(kind, kind)
    items = []
    for item_id in sorted(data[collection]):
        entry = data[collection][item_id]
        item = {"id": item_id}
        if isinstance(entry, dict):
            for key in ("display_name", "name", "area", "group", "version"):
                if key in entry:
                    item[key] = entry[key]
        items.append(item)
    return {"kind": kind, "items": items}


def _bool_arg(value: str) -> bool:
    v = value.strip().lower()
    if v not in ("true", "false"):
        raise argparse.ArgumentTypeError("expected true or false")
    return v == "true"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Recommend a reference standard, reporting guidelines, sections and "
                    "AI-disclosure needs from the RFA data layer. Output is JSON.")
    p.add_argument("--discipline", help="Discipline id or unique last segment (e.g. psychology)")
    p.add_argument("--document-type", help="Document type id (e.g. systematic-review)")
    p.add_argument("--language", help="Language tag: es, en, es-CO, pt-BR ...")
    p.add_argument("--standard", help="Citation standard chosen by the user (e.g. apa-7)")
    p.add_argument("--standard-variant", help="Variant of the chosen standard (e.g. author-date)")
    p.add_argument("--standard-source", choices=STANDARD_SOURCES,
                   help="Who imposes the chosen standard")
    p.add_argument("--study-design", help="Study design id (e.g. rct, cohort)")
    p.add_argument("--reporting-guideline", help="Reporting guideline id (e.g. consort-2025)")
    p.add_argument("--policy", help="AI policy registry key (e.g. springer-nature)")
    p.add_argument("--ai-use", choices=AI_USE_KINDS, help="Kind of AI use")
    p.add_argument("--ai-author", nargs="?", const=True, type=_bool_arg,
                   help="Whether an AI tool is listed as an author (bare flag means true)")
    p.add_argument("--json-in", help="Read the query from a JSON file (CLI flags override it)")
    p.add_argument("--list", choices=LIST_KINDS, help="List valid ids of a kind and exit")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    data = load_data()

    if args.list:
        write_json(list_items(args.list, data))
        return 0

    query = {}
    if args.json_in:
        try:
            with open(args.json_in, "r", encoding="utf-8") as f:
                query = json.load(f)
        except (OSError, ValueError) as e:
            sys.stderr.write(f"Cannot read --json-in file: {e}\n")
            return 2
        if not isinstance(query, dict):
            sys.stderr.write("--json-in must contain a JSON object\n")
            return 2
    for field in QUERY_FIELDS:
        value = getattr(args, field)
        if value is not None:
            query[field] = value
    if not query:
        parser.print_usage(sys.stderr)
        sys.stderr.write("recommend.py: error: provide at least one query field, --json-in or --list\n")
        return 2

    result = recommend(query, data)
    write_json(result)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
