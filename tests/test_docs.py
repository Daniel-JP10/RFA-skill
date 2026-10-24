# -*- coding: utf-8 -*-
"""Documentation verification tests (offline, deterministic).

Tests:
D1: Relative links and backtick repository paths resolve to existing files/dirs.
D2: Execution of <!-- rfa:run --> blocks and verification of <!-- rfa:excerpt --> subsets.
D3: Generated docs tables are in sync with rfa_data.json.
D4: No emojis anywhere; no Spanish text in English docs outside code/tables/URLs.
D5: Parity between English and Spanish document pairs (headings, code blocks, URLs).
D6: SKILL.md front matter has name and description, <= 220 lines.
D7: skill.manifest.json is valid and all referenced paths exist.
D8: Integrity inventory keywords present in SKILL.md, README.md, PRIVACY.md.
D9: Commands outside rfa:run blocks reference valid scripts and known --help flags.
"""

import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import unicodedata
import yaml
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
ROOT = SKILL_DIR.parent

DOC_FILES_SCOPE = [
    SKILL_DIR / "SKILL.md",
    SKILL_DIR / "README.md",
    SKILL_DIR / "PRIVACY.md",
    SKILL_DIR / "references" / "workflow.md",
    SKILL_DIR / "references" / "data-sources.md",
]
for sub in ["router", "disclosure", "examples", "evals", "structure", "docs/es"]:
    sub_dir = SKILL_DIR / sub
    if sub_dir.exists():
        DOC_FILES_SCOPE.extend(sorted(sub_dir.glob("*.md")))


def _extract_urls(text: str) -> set[str]:
    return set(re.findall(r"https?://[^\s)\]]+", text))


def _extract_headings(text: str) -> dict[int, int]:
    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+", line)
        if m:
            level = len(m.group(1))
            counts[level] += 1
    return counts


def _extract_code_blocks(text: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL)


def test_d1_links_and_paths_resolve():
    """D1 every relative Markdown link and every path in backticks resolves."""
    broken = []
    for f in DOC_FILES_SCOPE:
        text = f.read_text(encoding="utf-8")

        # 1. Relative Markdown links [text](target)
        for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
            target = m.group(2).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = target.split("#")[0]
            if not target_path:
                continue
            candidates = [
                (SKILL_DIR / target_path).resolve(),
                (ROOT / target_path).resolve(),
                (f.parent / target_path).resolve(),
            ]
            if not any(c.exists() for c in candidates):
                broken.append(f"{f.relative_to(ROOT)}: broken link '{target}'")

        # 2. Backtick repo paths
        for m in re.finditer(r"`([^`]+)`", text):
            span = m.group(1).strip()
            if " " in span or span.startswith(("-", "http://", "https://", "application/", "[@")) or span in ("en", "es"):
                continue
            has_repo_ext = any(span.endswith(ext) for ext in (".md", ".py", ".json", ".yaml", ".txt", ".csl"))
            has_slash = "/" in span
            if not (has_repo_ext or has_slash):
                continue
            if span in ("doc.md", "items.csl.json", "J_Medline.txt", "nlm-citation-sequence.csl"):
                continue

            candidates = [
                (SKILL_DIR / span).resolve(),
                (ROOT / span).resolve(),
                (f.parent / span).resolve(),
                (ROOT / "rfa-core" / "05-references-spec" / span).resolve(),
                (SKILL_DIR / "scripts" / span).resolve(),
                (SKILL_DIR / "references" / "scripts" / span).resolve(),
                (SKILL_DIR / "references" / "tests" / span).resolve(),
            ]
            if not any(c.exists() for c in candidates):
                broken.append(f"{f.relative_to(ROOT)}: unresolved backtick path '{span}'")

    assert not broken, "Broken links or backtick paths found:\n" + "\n".join(broken)


def _is_subset(sub, full):
    if isinstance(sub, dict):
        if not isinstance(full, dict):
            return False
        for k, v in sub.items():
            if k not in full:
                return False
            if not _is_subset(v, full[k]):
                return False
        return True
    elif isinstance(sub, list):
        if not isinstance(full, list):
            return False
        if len(sub) > len(full):
            return False
        for i, sub_item in enumerate(sub):
            if not _is_subset(sub_item, full[i]):
                return False
        return True
    else:
        return sub == full


def test_d2_rfa_run_and_excerpt_blocks():
    """D2 rfa:run blocks execute successfully and rfa:excerpt blocks are valid subsets."""
    from format_reference import available_backends
    pandoc_available = bool(available_backends().get("pandoc"))

    executed_count = 0
    skipped_count = 0
    run_outputs = {}

    run_pattern = re.compile(
        r"<!--\s*rfa:run\s+([^>]+?)-->\s*\n```bash\s*\n(.*?)```",
        re.DOTALL
    )
    excerpt_pattern = re.compile(
        r"<!--\s*rfa:excerpt\s+of=([^\s>]+)\s*-->\s*\n```json\s*\n(.*?)```",
        re.DOTALL
    )

    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    # Execute all run blocks
    for f in DOC_FILES_SCOPE:
        text = f.read_text(encoding="utf-8")
        for m in run_pattern.finditer(text):
            meta_str, script_content = m.group(1).strip(), m.group(2).strip()

            meta = dict(re.findall(r'(\w+)(?:=([^\s]+))?', meta_str))
            run_id = meta.get("id")
            assert run_id, f"Missing id in rfa:run marker in {f}"
            needs = meta.get("needs")
            expect_exit = int(meta.get("expect-exit", 0))

            if needs == "pandoc" and not pandoc_available:
                skipped_count += 1
                continue

            cmd_lines = [l.strip() for l in script_content.splitlines() if l.strip() and not l.strip().startswith("#")]
            assert len(cmd_lines) == 1, f"Expected single command in block {run_id}"
            cmd = cmd_lines[0]
            assert cmd.startswith("python "), f"Command must start with 'python ' in {run_id}: {cmd}"

            args = shlex.split(cmd)[1:]
            full_cmd = [sys.executable, "-X", "utf8"] + args

            res = subprocess.run(
                full_cmd,
                cwd=SKILL_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            assert res.returncode == expect_exit, (
                f"Block {run_id} exited with {res.returncode}, expected {expect_exit}.\nStderr: {res.stderr}\nStdout: {res.stdout}"
            )
            out_json = json.loads(res.stdout)
            run_outputs[run_id] = out_json
            executed_count += 1

    # Verify all excerpt blocks
    for f in DOC_FILES_SCOPE:
        text = f.read_text(encoding="utf-8")
        for m in excerpt_pattern.finditer(text):
            target_id, excerpt_content = m.group(1).strip(), m.group(2).strip()
            if target_id not in run_outputs:
                continue
            excerpt_json = json.loads(excerpt_content)
            full_json = run_outputs[target_id]
            assert _is_subset(excerpt_json, full_json), (
                f"Excerpt of {target_id} in {f.name} is not a valid subset of real output:\n"
                f"Excerpt: {json.dumps(excerpt_json, indent=2)}\n"
                f"Full output: {json.dumps(full_json, indent=2)}"
            )

    print(f"\nD2: Executed {executed_count} blocks, skipped {skipped_count} blocks.")
    assert executed_count > 0, "No rfa:run blocks were executed."


@pytest.mark.skipif(not (ROOT / "tools" / "render_docs_tables.py").exists(), reason="repository-only test: tools/ is absent")
def test_d3_render_docs_tables_check():
    """D3 generated tables are in sync with rfa_data.json for en and es."""
    cmd = [sys.executable, str(ROOT / "tools" / "render_docs_tables.py"), "--check"]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, f"render_docs_tables.py --check failed:\n{res.stdout}\n{res.stderr}"


def test_d4_no_emoji_and_language_hygiene():
    """D4 no emojis anywhere; no Spanish function words in English docs outside code/tables/URLs."""
    all_md_files = list(SKILL_DIR.rglob("*.md")) + list(ROOT.glob("README*.md"))
    for f in all_md_files:
        text = f.read_text(encoding="utf-8")
        for idx, ch in enumerate(text):
            cat = unicodedata.category(ch)
            code = ord(ch)
            is_emoji = (
                (0x1F300 <= code <= 0x1FAFF)
                or (0x2600 <= code <= 0x27BF)
                or (cat == "So" and code > 0x2000)
            )
            assert not is_emoji, f"Emoji character '{ch}' (U+{code:04X}) found in {f.relative_to(ROOT)} at index {idx}"

    english_docs = [
        f for f in DOC_FILES_SCOPE
        if "docs/es" not in str(f).replace("\\", "/") and f.name != "es-essay-humanities.md"
    ]

    spanish_words = re.compile(r"\b(el|la|los|de|que|para|con)\b", re.IGNORECASE)
    spanish_chars = re.compile(r"[áéíóúñÁÉÍÓÚÑ¿¡]")

    for f in english_docs:
        lines = f.read_text(encoding="utf-8").splitlines()
        in_code_block = False
        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            if line.strip().startswith("|") and line.strip().endswith("|"):
                continue

            clean_line = re.sub(r"`[^`]+`", "", line)
            clean_line = re.sub(r"https?://[^\s)\]]+", "", clean_line)
            clean_line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_line)

            m_char = spanish_chars.search(clean_line)
            assert not m_char, (
                f"Spanish accented character '{m_char.group(0)}' in {f.relative_to(ROOT)}:{line_num}:\n{line}"
            )

            m_word = spanish_words.search(clean_line)
            assert not m_word, (
                f"Spanish word '{m_word.group(0)}' in English doc {f.relative_to(ROOT)}:{line_num}:\n{line}"
            )


def test_d5_parity_english_spanish_pairs():
    """D5 parity for all 4 English/Spanish doc pairs."""
    pairs = [
        (SKILL_DIR / "README.md", SKILL_DIR / "docs" / "es" / "README.md"),
        (SKILL_DIR / "PRIVACY.md", SKILL_DIR / "docs" / "es" / "privacy.md"),
        (SKILL_DIR / "references" / "workflow.md", SKILL_DIR / "docs" / "es" / "workflow.md"),
        (SKILL_DIR / "disclosure" / "when-to-disclose.md", SKILL_DIR / "docs" / "es" / "disclosure.md"),
    ]

    for en_path, es_path in pairs:
        assert en_path.exists(), f"Missing English file: {en_path}"
        assert es_path.exists(), f"Missing Spanish file: {es_path}"

        en_text = en_path.read_text(encoding="utf-8")
        es_text = es_path.read_text(encoding="utf-8")

        en_h = _extract_headings(en_text)
        es_h = _extract_headings(es_text)
        assert en_h == es_h, f"Headings mismatch between {en_path.name} and {es_path.name}: en={en_h}, es={es_h}"

        en_cb = len(_extract_code_blocks(en_text))
        es_cb = len(_extract_code_blocks(es_text))
        assert en_cb == es_cb, f"Code blocks count mismatch between {en_path.name} and {es_path.name}: en={en_cb}, es={es_cb}"

        en_urls = _extract_urls(en_text)
        es_urls = _extract_urls(es_text)
        assert en_urls == es_urls, f"URL sets mismatch between {en_path.name} and {es_path.name}:\nen_urls={en_urls}\nes_urls={es_urls}"


def test_d6_skill_md_limits():
    """D6 SKILL.md has name and description in front matter and <= 220 lines."""
    skill_file = SKILL_DIR / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) <= 220, f"SKILL.md exceeds 220 lines (got {len(lines)})"

    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert m, "SKILL.md missing front matter"
    fm = yaml.safe_load(m.group(1))
    assert "name" in fm and fm["name"], "SKILL.md front matter missing 'name'"
    assert "description" in fm and fm["description"], "SKILL.md front matter missing 'description'"


def test_d7_skill_manifest_valid():
    """D7 skill.manifest.json parses and every path it names exists."""
    manifest_file = SKILL_DIR / "skill.manifest.json"
    assert manifest_file.exists(), "skill.manifest.json not found"
    data = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert data.get("name") == "rfa-scholarly-writing"
    assert data.get("version") == "0.1.0"
    assert "description" in data
    assert data.get("languages") == ["en", "es"]

    for p in data.get("entry_points", {}).keys():
        full_p = SKILL_DIR / p
        assert full_p.exists(), f"Manifest entry point path does not exist: {p}"

    data_file = data.get("data", {}).get("file")
    assert data_file, "Manifest missing data.file"
    assert (SKILL_DIR / data_file).exists(), f"Manifest data.file does not exist: {data_file}"

    for doc_k, doc_p in data.get("docs", {}).items():
        assert (SKILL_DIR / doc_p).exists(), f"Manifest docs.{doc_k} path does not exist: {doc_p}"


def test_d8_integrity_inventory():
    """D8 integrity inventory keywords present in SKILL.md, README.md, PRIVACY.md."""
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").lower()
    for kw in ["never invent", "do not help conceal ai use", "never choose for the user", "needs_review", "data snapshot"]:
        assert kw in skill_text, f"SKILL.md missing keyword: '{kw}'"

    readme_text = (SKILL_DIR / "README.md").read_text(encoding="utf-8").lower()
    for kw in ["does not help conceal ai use", "no telemetry", "requirements-dev.txt"]:
        assert kw in readme_text, f"README.md missing keyword: '{kw}'"

    privacy_text = (SKILL_DIR / "PRIVACY.md").read_text(encoding="utf-8").lower()
    for kw in ["data.crosscite.org", "no telemetry"]:
        assert kw in privacy_text, f"PRIVACY.md missing keyword: '{kw}'"


def test_d9_commands_in_docs_use_valid_flags():
    """D9 every command starting with python scripts/ or python references/scripts/ uses known flags."""
    run_block_cmd_pattern = re.compile(r"<!--\s*rfa:run.*?-->\s*\n```bash\s*\n(.*?)```", re.DOTALL)

    help_flags = {}

    def get_flags(script_rel: str) -> set[str]:
        if script_rel not in help_flags:
            full_path = SKILL_DIR / script_rel
            res = subprocess.run([sys.executable, str(full_path), "--help"], capture_output=True, text=True, encoding="utf-8")
            assert res.returncode == 0, f"Failed to run --help on {script_rel}"
            flags = set(re.findall(r"(--[a-zA-Z0-9-]+|-[a-zA-Z0-9])", res.stdout))
            help_flags[script_rel] = flags
        return help_flags[script_rel]

    for f in DOC_FILES_SCOPE:
        text = f.read_text(encoding="utf-8")
        text_without_runs = run_block_cmd_pattern.sub("", text)

        for line in text_without_runs.splitlines():
            line_s = line.strip()
            m = re.match(r"^python\s+((?:references/)?scripts/[a-zA-Z0-9_]+\.py)\s*(.*)$", line_s)
            if m:
                script_rel = m.group(1)
                args_str = m.group(2)
                script_path = SKILL_DIR / script_rel
                assert script_path.exists(), f"Command in {f.name} references non-existent script: {script_rel}"

                flags = get_flags(script_rel)
                tokens = args_str.split()
                for tok in tokens:
                    if tok.startswith("-") and not re.match(r"^-\d+$", tok):
                        flag_name = tok.split("=")[0]
                        assert flag_name in flags, f"Flag '{flag_name}' used in {f.name} for {script_rel} not found in its --help"


def _table_rows(text: str) -> list[list[str]]:
    """Cells of every Markdown table row, header and separator rows excluded."""
    rows = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")) or set(s) <= set("|-: "):
            continue
        is_header = i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: ") and lines[i + 1].strip().startswith("|")
        if is_header:
            continue
        rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


def test_d10_privacy_matches_code():
    """D10 PRIVACY hosts equal ALLOWED_HOSTS (en and es) and every environment variable read by the tools is documented."""
    import ast
    from _common import ALLOWED_HOSTS

    host_re = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+")
    for path in (SKILL_DIR / "PRIVACY.md", SKILL_DIR / "docs" / "es" / "privacy.md"):
        rows = _table_rows(path.read_text(encoding="utf-8"))
        hosts = {h for row in rows for h in host_re.findall(row[0])}
        assert hosts == ALLOWED_HOSTS, f"{path.name}: hosts {sorted(hosts)} != ALLOWED_HOSTS {sorted(ALLOWED_HOSTS)}"

    name_re = re.compile(r"^(RFA_[A-Z0-9_]+|[A-Z0-9]+_API_KEY)$")

    def is_environ(node):
        return isinstance(node, ast.Attribute) and node.attr == "environ"

    names = set()
    py_files = sorted((SKILL_DIR / "scripts").glob("*.py")) + sorted((SKILL_DIR / "references" / "scripts").glob("*.py"))
    assert py_files, "No scripts found"
    for py in py_files:
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                func = node.func
                if (isinstance(func, ast.Attribute) and func.attr == "get" and is_environ(func.value)) or \
                        (isinstance(func, ast.Attribute) and func.attr == "getenv"):
                    names.add(node.args[0].value)
            elif isinstance(node, ast.Subscript) and is_environ(node.value) and isinstance(node.slice, ast.Constant):
                names.add(node.slice.value)
            elif isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant) and \
                    any(isinstance(op, ast.In) for op in node.ops) and any(is_environ(c) for c in node.comparators):
                names.add(node.left.value)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and name_re.match(node.value):
                names.add(node.value)
    assert names, "No environment variable names found in the scripts"
    privacy = (SKILL_DIR / "PRIVACY.md").read_text(encoding="utf-8")
    undocumented = sorted(n for n in names if f"`{n}`" not in privacy)
    assert not undocumented, f"Environment variables not documented in PRIVACY.md: {undocumented}"


def test_d11_eval_test_names_exist():
    """D11 every backticked test name in evals/*.md is defined in the skill test suites."""
    defined = set()
    for tests_dir in (SKILL_DIR / "tests", SKILL_DIR / "references" / "tests"):
        for py in tests_dir.glob("*.py"):
            defined |= set(re.findall(r"^def (test_[a-z0-9_]+)\(", py.read_text(encoding="utf-8"), re.MULTILINE))
    cited = set()
    for md in sorted((SKILL_DIR / "evals").glob("*.md")):
        cited |= set(re.findall(r"`(test_[a-z0-9_]+)`", md.read_text(encoding="utf-8")))
    assert cited, "No test names cited in evals/"
    missing = sorted(cited - defined)
    assert not missing, f"Eval documents cite tests that do not exist: {missing}"


def test_d12_excerpts_have_runs():
    """D12 every rfa:excerpt has an rfa:run with the same id in the same file."""
    checked = 0
    for f in DOC_FILES_SCOPE:
        text = f.read_text(encoding="utf-8")
        run_ids = set(re.findall(r"<!--\s*rfa:run\s+id=([^\s>]+)", text))
        for target in re.findall(r"<!--\s*rfa:excerpt\s+of=([^\s>]+)\s*-->", text):
            checked += 1
            assert target in run_ids, f"{f.name}: rfa:excerpt of={target} has no rfa:run id={target} in the same file"
    assert checked > 0, "No rfa:excerpt blocks found"


def test_d13_eval_arguments_run():
    """D13 every argument set of evals/structure-conformity.md runs: status ok or denied, exit 0 (or 1 when denied)."""
    text = (SKILL_DIR / "evals" / "structure-conformity.md").read_text(encoding="utf-8")
    header = next(l for l in text.splitlines() if l.strip().startswith("|") and "Tool arguments" in l)
    col = [c.strip() for c in header.strip().strip("|").split("|")].index("Tool arguments")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    ran = 0
    for row in _table_rows(text):
        m = re.fullmatch(r"`(--[^`]*)`", row[col]) if len(row) > col else None
        if not m:
            continue
        res = subprocess.run([sys.executable, "-X", "utf8", "scripts/recommend.py", *shlex.split(m.group(1))],
                             cwd=SKILL_DIR, capture_output=True, text=True, encoding="utf-8", env=env)
        out = json.loads(res.stdout)
        assert out["status"] in ("ok", "denied"), f"{row[0]}: status {out['status']}: {out.get('errors')}"
        expected = 1 if out["status"] == "denied" else 0
        assert res.returncode == expected, f"{row[0]}: exit {res.returncode}, expected {expected}"
        ran += 1
    assert ran > 0, "No argument sets found in evals/structure-conformity.md"


def test_d14_paths_resolve_inside_skill():
    """D14 backtick paths in the user-facing docs resolve inside rfa-skill/ alone."""
    files = [SKILL_DIR / "SKILL.md", SKILL_DIR / "README.md", SKILL_DIR / "PRIVACY.md",
             SKILL_DIR / "references" / "workflow.md", SKILL_DIR / "references" / "data-sources.md"]
    for sub in ("router", "disclosure", "examples"):
        files.extend(sorted((SKILL_DIR / sub).glob("*.md")))
    skipped = {"doc.md", "items.csl.json", "J_Medline.txt", "nlm-citation-sequence.csl", "requirements-dev.txt"}
    broken = []
    checked = 0
    for f in files:
        for m in re.finditer(r"`([^`]+)`", f.read_text(encoding="utf-8")):
            span = m.group(1).strip()
            if " " in span or span.startswith(("-", "http://", "https://", "application/", "[@")) or span in ("en", "es"):
                continue
            if not (any(span.endswith(ext) for ext in (".md", ".py", ".json", ".yaml", ".txt", ".csl")) or "/" in span):
                continue
            if span in skipped:
                continue
            checked += 1
            candidates = [SKILL_DIR / span, f.parent / span, SKILL_DIR / "scripts" / span,
                          SKILL_DIR / "references" / "scripts" / span, SKILL_DIR / "references" / "tests" / span]
            if not any(c.resolve().exists() for c in candidates):
                broken.append(f"{f.relative_to(SKILL_DIR)}: '{span}' does not resolve inside rfa-skill/")
    assert checked > 0, "No paths checked"
    assert not broken, "\n".join(broken)


def test_d15_csl_notice_is_shipped():
    """D15 the CSL license notice ships with the skill, identical to the rfa-core copy."""
    shipped = SKILL_DIR / "references" / "csl" / "NOTICE.md"
    assert shipped.exists(), "rfa-skill/references/csl/NOTICE.md is missing"
    source = ROOT / "rfa-core" / "05-references-spec" / "csl" / "NOTICE.md"
    if source.exists():
        assert shipped.read_bytes() == source.read_bytes(), "NOTICE.md differs from the rfa-core copy"
