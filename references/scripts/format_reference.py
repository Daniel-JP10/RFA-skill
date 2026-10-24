# -*- coding: utf-8 -*-
"""Format bibliographic references using pandoc or citeproc-py."""

import argparse
import functools
import html as html_lib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from order_references import family_from_csl, order_for_style
from _common import first_author_family, normalize_text, redact

STYLE_MAP = {
    "apa-7": "apa-7.csl",
    "mla-9": "mla-9.csl",
    "chicago-18:author-date": "chicago-18-author-date.csl",
    "chicago-18:notes-bibliography": "chicago-18-notes.csl",
    "ieee": "ieee-2024.csl",
    "vancouver-nlm": "vancouver.csl",
    "ama-11": "ama-11.csl",
    "acs": "acs.csl",
    "cse:citation-sequence": "cse-citation-sequence.csl",
    "cse:name-year": "cse-name-year.csl",
    "cse:citation-name": "cse-citation-name.csl",
}


class BackendUnavailable(Exception):
    """Raised when the requested formatting backend is not installed."""
    pass


def _is_valid_executable(path_str: str | None) -> bool:
    if not path_str:
        return False
    try:
        return os.path.isfile(path_str) and os.access(path_str, os.X_OK)
    except Exception:
        return False


def _find_pandoc() -> str | None:
    # 1. RFA_PANDOC
    rfa_pandoc = os.environ.get("RFA_PANDOC")
    if _is_valid_executable(rfa_pandoc):
        return rfa_pandoc

    # 2. shutil.which("pandoc")
    which_pandoc = shutil.which("pandoc")
    path_cand = which_pandoc if _is_valid_executable(which_pandoc) else None

    # 3. pypandoc
    pyp_cand = None
    try:
        import pypandoc
        p_path = pypandoc.get_pandoc_path()
        if _is_valid_executable(p_path):
            pyp_cand = p_path
        else:
            exe_path = str(pathlib.Path(p_path).with_suffix(".exe"))
            if _is_valid_executable(exe_path):
                pyp_cand = exe_path
    except Exception:
        pass

    # PATH wins unless its known version is older than the tested one and the pypandoc copy meets it
    if path_cand and pyp_cand and path_cand != pyp_cand:
        v_path = pandoc_version(path_cand)
        v_pyp = pandoc_version(pyp_cand)
        if v_path is not None and v_path < (3, 9) and v_pyp is not None and v_pyp >= (3, 9):
            return pyp_cand
    return path_cand or pyp_cand


def pandoc_diagnostics() -> list[str]:
    """Return plain-English diagnostic messages for rejected pandoc candidates."""
    diagnostics = []

    # Check RFA_PANDOC
    if "RFA_PANDOC" in os.environ:
        cand = os.environ["RFA_PANDOC"]
        if not os.path.exists(cand):
            diagnostics.append(f"RFA_PANDOC points to a file that does not exist: {cand}")
        elif not os.path.isfile(cand):
            diagnostics.append(f"RFA_PANDOC points to a path that is not a regular file: {cand}")
        elif not os.access(cand, os.X_OK):
            diagnostics.append(f"RFA_PANDOC points to a file that is not executable: {cand}")

    # Check PATH
    which_pandoc = shutil.which("pandoc")
    if which_pandoc:
        if not _is_valid_executable(which_pandoc):
            diagnostics.append(f"pandoc found on PATH is not a valid executable file: {which_pandoc}")
    else:
        diagnostics.append("pandoc was not found on PATH")

    # Check pypandoc
    try:
        import pypandoc
        p_path = pypandoc.get_pandoc_path()
        exe_path = str(pathlib.Path(p_path).with_suffix(".exe"))
        if not (_is_valid_executable(p_path) or _is_valid_executable(exe_path)):
            diagnostics.append(f"pypandoc pandoc path is not a valid executable file: {p_path}")
    except Exception as e:
        diagnostics.append(f"pypandoc could not locate pandoc: {e}")

    return diagnostics


@functools.lru_cache(maxsize=None)
def pandoc_version(path: str) -> tuple[int, ...] | None:
    """Return the version of the pandoc at path as an integer tuple, or None if it cannot be read."""
    try:
        res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
        first = (res.stdout or "").splitlines()[0]
        m = re.search(r"pandoc(?:\.exe)?\s+(\d+(?:\.\d+)*)", first)
        return tuple(int(x) for x in m.group(1).split(".")) if m else None
    except Exception:
        return None


def _post_warnings(items: list[dict], pandoc_path: str | None) -> list[dict]:
    """Warnings appended after the existing ones: pandoc_version_untested, then unverified_item in input order."""
    warnings = []
    if pandoc_path:
        version = pandoc_version(pandoc_path)
        if version is None or version < (3, 9):
            v = ".".join(str(x) for x in version) if version else "unknown"
            warnings.append({
                "code": "pandoc_version_untested",
                "message": f"pandoc {v} is older than the tested version 3.9; names and in-text citations may be "
                           "formatted incorrectly. Use pandoc 3.9 or later, or run with --cross-check.",
                "version": v,
            })
    for it in items:
        if (it.get("x-rfa") or {}).get("status") != "verified":
            warnings.append({
                "code": "unverified_item",
                "id": it.get("id"),
                "message": "No verified provenance (x-rfa.status is not 'verified'). "
                           "Verify it with resolve_metadata.py before delivering it.",
            })
    return warnings


def available_backends() -> dict:
    """Detect available formatting backends and return their paths/versions."""
    pandoc_path = _find_pandoc()

    citeproc_ver = None
    try:
        import importlib.metadata
        citeproc_ver = importlib.metadata.version("citeproc-py")
    except Exception:
        pass

    return {
        "pandoc": pandoc_path,
        "citeproc-py": citeproc_ver,
    }


def html_to_text(html: str) -> str:
    """Convert CSL HTML output to clean plain text with Markdown italics."""
    if not html:
        return ""
    text = re.sub(r"<(?:em|i)>(.*?)</(?:em|i)>", r"*\1*", html)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


from html.parser import HTMLParser


class _CSLEntryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.current_id = None
        self.depth = 0
        self.entry_parts = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "div" and attr_dict.get("id", "").startswith("ref-") and "csl-entry" in attr_dict.get("class", ""):
            self.current_id = attr_dict["id"][4:]
            self.depth = 1
            self.entry_parts = []
            return

        if self.current_id:
            self.depth += 1
            attr_str = " ".join(f'{k}="{v}"' for k, v in attrs)
            self.entry_parts.append(f"<{tag} {attr_str}>" if attr_str else f"<{tag}>")

    def handle_endtag(self, tag):
        if self.current_id:
            self.depth -= 1
            if self.depth == 0:
                raw_html = "".join(self.entry_parts).strip()
                self.entries.append({
                    "id": self.current_id,
                    "html": raw_html,
                    "text": html_to_text(raw_html),
                })
                self.current_id = None
            else:
                self.entry_parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self.current_id:
            self.entry_parts.append(data)

    def handle_entityref(self, name):
        if self.current_id:
            self.entry_parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.current_id:
            self.entry_parts.append(f"&#{name};")


def _extract_csl_entries(html_output: str) -> list[dict]:
    parser = _CSLEntryParser()
    parser.feed(html_output)
    return parser.entries


def _format_pandoc(items: list[dict], csl_path: pathlib.Path, locale: str, pandoc_exe: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        md_file = tmp_path / "in.md"
        bib_file = tmp_path / "items.csl.json"

        keys = [f"@{it['id']}" for it in items if "id" in it]
        nocite_block = "\n".join(f"  {k}" for k in keys)
        md_content = f"---\nnocite: |\n{nocite_block}\n---\n\n::: {{#refs}}\n:::\n"
        md_file.write_text(md_content, encoding="utf-8")

        bib_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

        cmd = [
            pandoc_exe,
            str(md_file),
            "-f", "markdown",
            "-t", "html",
            "--wrap=none",
            "--citeproc",
            "--bibliography", str(bib_file),
            "--csl", str(csl_path),
            "-M", f"lang={locale}",
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Pandoc execution failed (code {res.returncode}): {redact(res.stderr)}")

        return _extract_csl_entries(res.stdout)


def _format_citeproc(items: list[dict], csl_path: pathlib.Path, locale: str) -> tuple[list[dict], list[dict]]:
    from citeproc import Citation, CitationItem, CitationStylesBibliography, CitationStylesStyle, formatter
    from citeproc.source.json import CiteProcJSON
    from _common import first_author_family

    family = family_from_csl(csl_path)
    ordered_items = order_for_style(items, family)

    warnings = []
    if family == "author-date":
        # Check for items sharing (first_author_family, year)
        groups = {}
        for it in ordered_items:
            fam = normalize_text(first_author_family(it) or "")
            issued = it.get("issued") or {}
            parts = issued.get("date-parts") or []
            year = parts[0][0] if parts and parts[0] else ""
            key = (fam, str(year))
            groups.setdefault(key, []).append(it["id"])

        for key, ids in groups.items():
            if len(ids) > 1:
                warnings.append({
                    "code": "year_suffix_not_applied",
                    "message": "citeproc-py does not apply year suffixes in author-date styles",
                    "id": ids,
                })

    bib_source = CiteProcJSON(ordered_items)
    style = CitationStylesStyle(str(csl_path), locale=locale, validate=False)
    bib = CitationStylesBibliography(style, bib_source, formatter.html)

    for it in ordered_items:
        c = Citation([CitationItem(it["id"])])
        bib.register(c)

    rendered = bib.bibliography()
    entries = []
    for idx, raw in enumerate(rendered):
        raw_html = "".join(raw) if isinstance(raw, (list, tuple)) else str(raw)
        text = html_to_text(raw_html)
        entries.append({
            "id": ordered_items[idx]["id"],
            "html": raw_html,
            "text": text,
        })

    return entries, warnings


def format_bibliography(
    items: list[dict],
    csl_path,
    locale: str = "en-US",
    backend: str = "auto",
    cross_check: bool = False,
) -> dict:
    """Format a bibliography using pandoc or citeproc-py."""
    csl_path = pathlib.Path(csl_path)
    backends = available_backends()

    if backend == "auto":
        chosen_backend = "pandoc" if backends["pandoc"] else ("citeproc-py" if backends["citeproc-py"] else None)
    else:
        chosen_backend = backend

    if chosen_backend == "pandoc" and not backends.get("pandoc"):
        diags = "\n".join(f"- {d}" for d in pandoc_diagnostics())
        raise BackendUnavailable(
            f"Formatting backend 'pandoc' is unavailable.\n"
            f"Diagnostics:\n{diags}\n"
            f"Pandoc can be installed with `pip install pypandoc_binary` or a system package."
        )

    if not chosen_backend or not backends.get(chosen_backend):
        raise BackendUnavailable(f"Formatting backend '{chosen_backend}' is unavailable.")

    warnings = []
    if chosen_backend == "citeproc-py":
        warnings.append({
            "code": "partial_csl_support",
            "message": "citeproc-py has partial CSL support; pandoc is recommended.",
        })

    if chosen_backend == "pandoc":
        entries = _format_pandoc(items, csl_path, locale, backends["pandoc"])
    elif chosen_backend == "citeproc-py":
        entries, cp_warn = _format_citeproc(items, csl_path, locale)
        warnings.extend(cp_warn)
    else:
        raise BackendUnavailable(f"Unknown backend: {chosen_backend}")

    pandoc_used = chosen_backend == "pandoc"
    cross_check_info = None
    if cross_check:
        if backends.get("pandoc") and backends.get("citeproc-py"):
            pandoc_used = True
            entries_p = _format_pandoc(items, csl_path, locale, backends["pandoc"])
            entries_c, _ = _format_citeproc(items, csl_path, locale)

            map_p = {e["id"]: e["text"] for e in entries_p}
            map_c = {e["id"]: e["text"] for e in entries_c}

            disagreements = []
            for item_id, text_p in map_p.items():
                text_c = map_c.get(item_id, "")
                norm_p = re.sub(r"^\[?\d+\]?\.?\s*", "", text_p).strip()
                norm_c = re.sub(r"^\[?\d+\]?\.?\s*", "", text_c).strip()
                if norm_p != norm_c:
                    disagreements.append({
                        "id": item_id,
                        "pandoc": text_p,
                        "citeproc": text_c,
                    })
                    warnings.append({
                        "code": "backend_disagreement",
                        "message": f"Backend disagreement for '{item_id}'",
                        "id": item_id,
                        "pandoc": text_p,
                        "citeproc": text_c,
                    })
            cross_check_info = {"disagreements": disagreements}
        else:
            warnings.append({
                "code": "cross_check_unavailable",
                "message": "Cross-check unavailable: both backends are required.",
            })

    warnings.extend(_post_warnings(items, backends["pandoc"] if pandoc_used else None))

    return {
        "entries": entries,
        "backend": chosen_backend,
        "warnings": warnings,
        "cross_check": cross_check_info,
    }


def render_document(markdown_text: str, items: list[dict], csl_path, locale: str = "en-US") -> dict:
    """Render a full markdown document with in-text citations and bibliography."""
    backends = available_backends()
    pandoc_exe = backends.get("pandoc")
    if not pandoc_exe:
        diags = "\n".join(f"- {d}" for d in pandoc_diagnostics())
        raise BackendUnavailable(
            f"render_document requires pandoc; use format_bibliography or install pandoc.\n"
            f"Diagnostics:\n{diags}\n"
            f"Pandoc can be installed with `pip install pypandoc_binary` or a system package."
        )

    csl_path = pathlib.Path(csl_path)

    # Detect missing keys
    from validate_citations import extract_pandoc_keys
    cited_keys = extract_pandoc_keys(markdown_text)
    known_keys = {it["id"] for it in items if "id" in it}

    warnings = []
    for k in cited_keys:
        if k not in known_keys:
            warnings.append({
                "code": "missing_key",
                "message": f"Cited key not found in items: {k}",
                "id": k,
            })

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        doc_file = tmp_path / "doc.md"
        bib_file = tmp_path / "items.csl.json"

        doc_file.write_text(markdown_text, encoding="utf-8")
        bib_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

        # 1. Render Markdown with smart quotes/dashes
        cmd_md = [
            pandoc_exe,
            str(doc_file),
            "-f", "markdown",
            "-t", "markdown-smart-citations",
            "--wrap=none",
            "--citeproc",
            "--bibliography", str(bib_file),
            "--csl", str(csl_path),
            "-M", f"lang={locale}",
        ]
        res_md = subprocess.run(cmd_md, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res_md.returncode != 0:
            raise RuntimeError(redact(res_md.stderr or "pandoc error in markdown render"))
        rendered_text = res_md.stdout

        # 2. Get HTML entries
        cmd_html = [
            pandoc_exe,
            str(doc_file),
            "-f", "markdown",
            "-t", "html",
            "--wrap=none",
            "--citeproc",
            "--bibliography", str(bib_file),
            "--csl", str(csl_path),
            "-M", f"lang={locale}",
        ]
        res_html = subprocess.run(cmd_html, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res_html.returncode != 0:
            raise RuntimeError(redact(res_html.stderr or "pandoc error in html render"))
        entries = _extract_csl_entries(res_html.stdout)

        # Extract missing citation warnings from stderr
        combined_stderr = f"{res_md.stderr or ''}\n{res_html.stderr or ''}"
        for m in re.finditer(r"Citeproc:\s+citation\s+(\S+)\s+not\s+found", combined_stderr, re.IGNORECASE):
            missing_k = m.group(1).strip()
            if not any(w.get("code") == "missing_key" and w.get("id") == missing_k for w in warnings):
                warnings.append({
                    "code": "missing_key",
                    "message": f"Cited key not found in items: {missing_k}",
                    "id": missing_k,
                })

    warnings.extend(_post_warnings(items, pandoc_exe))

    return {
        "text": rendered_text,
        "entries": entries,
        "warnings": warnings,
    }


def main(argv=None):
    """CLI entry point for format_reference."""
    parser = argparse.ArgumentParser(description="Format references with pandoc or citeproc-py.")
    parser.add_argument("--items", required=True, help="Path to CSL-JSON items file")
    parser.add_argument("--style", required=True, help="Style identifier (key of STYLE_MAP or file name)")
    parser.add_argument("--csl-dir", help="Directory containing CSL files")
    parser.add_argument("--locale", default="en-US", help="Locale for citation formatting (default: en-US)")
    parser.add_argument("--backend", choices=["auto", "pandoc", "citeproc-py"], default="auto")
    parser.add_argument("--cross-check", action="store_true", help="Compare pandoc and citeproc-py")
    parser.add_argument("--doc", help="Path to markdown document for render_document mode")
    parser.add_argument("--out", help="Output file (default stdout)")

    args = parser.parse_args(argv)

    try:
        with open(args.items, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception as e:
        sys.stderr.write(f"Error loading items: {e}\n")
        return 2

    csl_filename = STYLE_MAP.get(args.style, args.style)
    csl_dir = pathlib.Path(args.csl_dir) if args.csl_dir else pathlib.Path(__file__).parent.parent / "csl"
    csl_path = csl_dir / csl_filename
    if not csl_path.exists():
        sys.stderr.write(f"CSL file not found: {csl_path}\n")
        return 2

    try:
        if args.doc:
            with open(args.doc, "r", encoding="utf-8") as f:
                doc_text = f.read()
            res = render_document(doc_text, items, csl_path, locale=args.locale)
        else:
            res = format_bibliography(
                items,
                csl_path,
                locale=args.locale,
                backend=args.backend,
                cross_check=args.cross_check,
            )
    except BackendUnavailable as e:
        sys.stderr.write(f"Backend error: {e}\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"Execution error: {e}\n")
        return 2

    out_json = json.dumps(res, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        sys.stdout.write(out_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
