#!/usr/bin/env python3
"""Prepare a file or a web app for a push to Jinkō as a raw file.

The skill calls this command for the work that must be the same at each run:
read the input, choose the form, make the bundle, check it, and report. It is
an implementation detail, not a CLI for users to learn.

Input, one of: a file of any kind, one HTML file (alone or with the files it
links to), a directory, or a zip archive.

Form, in the report:

- ``file``: the input goes to Jinkō as it is.
- ``html``: the HTML file goes as it is, as an HTML raw file.
- ``application``: the command writes a zip bundle with a ``manifest.json``
  at its top level. Jinkō runs it as an embedded application.

The command never changes the input. It corrects links in the copy that it
writes to the bundle. It prints a JSON report, and exits with 1 when it stops
(``ok`` is false, and ``error`` gives a code and the reason).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import posixpath
import re
import sys
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

# The upload limit of the Jinkō interface for a raw file.
SIZE_LIMIT_BYTES = 210 * 10**6
MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
# The only "$schema" value that the Jinkō interface accepts in a manifest.
MANIFEST_SCHEMA_URL = (
    "https://jinko.ai/schemas/embedded-application-manifest.schema.json"
)

HTML_SUFFIXES = {".html", ".htm"}
CSS_SUFFIXES = {".css"}
SCRIPT_SUFFIXES = {".js", ".mjs"}
EXCLUDED_FILE_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDED_DIRECTORY_NAMES = {"__MACOSX"}
PRUNED_DIRECTORY_NAMES = {".git"}

_ATTRIBUTE_RE = re.compile(
    r"""(?<![\w:.-])(src|href|poster|data|srcset|style)\s*=\s*"""
    r"""(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""",
    re.IGNORECASE,
)
_CSS_URL_RE = re.compile(
    r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"\s]+))\s*\)""", re.IGNORECASE
)
_CSS_IMPORT_RE = re.compile(r"""@import\s+(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_SCRIPT_IMPORT_RE = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*)(["'])(\.{1,2}/[^"'\n]+)\1"""
)
_SCRIPT_ROOT_PATH_RE = re.compile(r"""(["'`])(/[^"'`\s]+)\1""")
_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")


class BundleError(Exception):
    """A reason to stop, with a stable code for the caller."""

    def __init__(self, code: str, message: str, **details) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


# --------------------------------------------------------------------------- #
# Checks, the same as the Jinkō interface
# --------------------------------------------------------------------------- #


def parse_manifest(text: bytes | str) -> dict:
    """Return the manifest when the Jinkō interface accepts it, else stop."""
    try:
        manifest = json.loads(text)
    except (ValueError, UnicodeDecodeError) as error:
        raise BundleError(
            "manifest_invalid_json", f"manifest.json is not valid JSON: {error}"
        ) from error
    is_object = isinstance(manifest, dict)
    version = (
        manifest["version"] if is_object and "version" in manifest else MANIFEST_VERSION
    )
    if (
        isinstance(version, bool)
        or not isinstance(version, (int, float))
        or version != MANIFEST_VERSION
    ):
        raise BundleError(
            "manifest_version_unsupported",
            f"manifest.json has the version {version!r}; Jinkō supports the "
            f"version {MANIFEST_VERSION} only.",
        )
    if not is_object:
        raise BundleError("manifest_invalid", "manifest.json must be a JSON object.")
    if not isinstance(manifest.get("main"), str):
        raise BundleError(
            "manifest_invalid",
            'manifest.json must give the entry page as a text value, "main".',
        )
    if "$schema" in manifest and manifest["$schema"] != MANIFEST_SCHEMA_URL:
        raise BundleError(
            "manifest_schema_unsupported",
            f'manifest.json has an unsupported "$schema"; remove it or use '
            f"{MANIFEST_SCHEMA_URL}.",
        )
    return manifest


def check_size(path: Path, size_limit: int | None = None) -> int:
    limit = SIZE_LIMIT_BYTES if size_limit is None else size_limit
    size = path.stat().st_size
    if size > limit:
        raise BundleError(
            "too_large",
            f"The file to push has {size} bytes; the limit of Jinkō is {limit} "
            "bytes. Remove or compress large files.",
            size_bytes=size,
            size_limit_bytes=limit,
        )
    return size


def check_bundle(path: Path | str, size_limit: int | None = None) -> dict:
    """Check a bundle as the Jinkō interface does, and check its size.

    The manifest exists at the top level, it is valid, and its entry page is in
    the archive. Return the manifest, or stop with the reason.
    """
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            manifest_bytes = (
                archive.read(MANIFEST_NAME) if MANIFEST_NAME in names else None
            )
    except (zipfile.BadZipFile, OSError) as error:
        raise BundleError(
            "invalid_archive", f"{path.name} is not a readable zip archive: {error}"
        ) from error
    if manifest_bytes is None:
        raise BundleError(
            "manifest_missing",
            "The archive has no manifest.json at its top level.",
        )
    manifest = parse_manifest(manifest_bytes)
    if manifest["main"] not in names:
        raise BundleError(
            "entry_missing",
            f"manifest.json names the entry page '{manifest['main']}', which is "
            "not in the archive.",
        )
    check_size(path, size_limit)
    return manifest


# --------------------------------------------------------------------------- #
# Links
# --------------------------------------------------------------------------- #


class _Link:
    """One link in a text file: its position, and its value as written."""

    __slots__ = ("start", "end", "raw", "url")

    def __init__(self, start: int, end: int, raw: str, url: str | None = None):
        self.start = start
        self.end = end
        self.raw = raw
        self.url = raw if url is None else url


def _css_links(text: str, offset: int = 0) -> list[_Link]:
    links = []
    for pattern in (_CSS_URL_RE, _CSS_IMPORT_RE):
        for match in pattern.finditer(text):
            group = match.lastindex
            links.append(
                _Link(
                    offset + match.start(group),
                    offset + match.end(group),
                    match.group(group),
                )
            )
    return links


def _srcset_links(value: str, offset: int) -> list[_Link]:
    links = []
    position, length = 0, len(value)
    while position < length:
        while position < length and (
            value[position].isspace() or value[position] == ","
        ):
            position += 1
        start = position
        while position < length and not value[position].isspace():
            position += 1
        url = value[start:position]
        stripped = url.rstrip(",")
        if stripped:
            links.append(
                _Link(offset + start, offset + start + len(stripped), stripped)
            )
        if stripped == url:
            # A descriptor follows ("2x", "480w"): skip to the next candidate.
            while position < length and value[position] != ",":
                position += 1
    return links


class _HtmlScanner(HTMLParser):
    """Find the links of an HTML page, with their positions in the text."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self._text = text
        self._line_starts = [0]
        for match in re.finditer("\n", text):
            self._line_starts.append(match.end())
        self._in_style = False
        self.links: list[_Link] = []
        self.has_script = False
        self.has_base = False

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[line - 1] + column

    def handle_starttag(self, tag, attrs):
        self._tag(tag)
        if tag == "style":
            self._in_style = True

    def handle_startendtag(self, tag, attrs):
        self._tag(tag)

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if not self._in_style:
            return
        offset = self._offset()
        if self._text.startswith(data, offset):
            self.links.extend(_css_links(data, offset))

    def _tag(self, tag: str) -> None:
        if tag == "script":
            self.has_script = True
        if tag == "base":
            self.has_base = True
            return
        raw_tag = self.get_starttag_text() or ""
        offset = self._offset()
        if not self._text.startswith(raw_tag, offset):
            return
        for match in _ATTRIBUTE_RE.finditer(raw_tag):
            name = match.group(1).lower()
            if name == "data" and tag != "object":
                continue
            group = match.lastindex
            value = match.group(group)
            start = offset + match.start(group)
            if name == "style":
                links = _css_links(value, start)
            elif name == "srcset":
                links = _srcset_links(value, start)
            else:
                stripped = value.strip()
                lead = len(value) - len(value.lstrip())
                links = [_Link(start + lead, start + lead + len(stripped), stripped)]
            for link in links:
                link.url = html.unescape(link.raw)
            self.links.extend(links)


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="surrogateescape")


def _encode(text: str) -> bytes:
    return text.encode("utf-8", errors="surrogateescape")


def _kind(name: str) -> str | None:
    suffix = posixpath.splitext(name)[1].lower()
    if suffix in HTML_SUFFIXES:
        return "html"
    if suffix in CSS_SUFFIXES:
        return "css"
    if suffix in SCRIPT_SUFFIXES:
        return "script"
    return None


def _scan(name: str, text: str) -> tuple[list[_Link], bool, bool]:
    """Return the links of a text file, and for a page: has script, has base."""
    kind = _kind(name)
    if kind == "html":
        scanner = _HtmlScanner(text)
        try:
            scanner.feed(text)
            scanner.close()
        except Exception:  # A page that the parser refuses keeps its links.
            pass
        links = sorted(scanner.links, key=lambda link: link.start)
        return links, scanner.has_script, scanner.has_base
    if kind == "css":
        return sorted(_css_links(text), key=lambda link: link.start), False, False
    if kind == "script":
        links = [
            _Link(match.start(2), match.end(2), match.group(2))
            for match in _SCRIPT_IMPORT_RE.finditer(text)
        ]
        return links, False, False
    return [], False, False


def _classify(url: str) -> str:
    """Return external, root, relative, or ignore."""
    url = url.strip()
    if not url or url.startswith("#"):
        return "ignore"
    if url.startswith("//"):
        return "external"
    scheme = _SCHEME_RE.match(url)
    if scheme:
        return "external" if scheme.group(1).lower() in {"http", "https"} else "ignore"
    return "root" if url.startswith("/") else "relative"


def _target(url: str, file_name: str, kind: str) -> str | None:
    """Return the bundle path that a local link names.

    ``""`` is the top of the bundle or the link has no path; ``None`` is a path
    outside the bundle.
    """
    path = unquote(re.split(r"[?#]", url.strip(), maxsplit=1)[0])
    if kind == "root":
        joined = posixpath.normpath(path.lstrip("/") or ".")
    elif not path:
        return ""
    else:
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(file_name), path))
    if joined == ".":
        return ""
    if joined == ".." or joined.startswith("../") or joined.startswith("/"):
        return None
    return joined


class _Analysis:
    def __init__(self) -> None:
        self.rewritten: list[dict] = []
        self.external: list[dict] = []
        self.missing: list[dict] = []
        self.warnings: list[str] = []

    @staticmethod
    def _add(items: list[dict], item: dict) -> None:
        if item not in items:
            items.append(item)

    def process(
        self, name: str, data: bytes, files: set[str], *, rewrite: bool
    ) -> bytes:
        """Record the links of one file, and return its content for the bundle."""
        kind = _kind(name)
        if kind is None:
            return data
        text = _decode(data)
        if kind == "script":
            for match in _SCRIPT_ROOT_PATH_RE.finditer(text):
                path = match.group(2)
                if _target(path, name, "root") in files:
                    warning = (
                        f"{name}: the script names '{path}' from the root. The "
                        "bundle does not correct paths in scripts; make this "
                        "path relative if the app does not find the file."
                    )
                    if warning not in self.warnings:
                        self.warnings.append(warning)
            return data
        links, _, has_base = _scan(name, text)
        if has_base:
            self.warnings.append(
                f"{name}: the page has a <base> element, which changes how the "
                "browser reads its relative links."
            )
        depth = name.count("/")
        edits = []
        for link in links:
            link_kind = _classify(link.url)
            if link_kind == "ignore":
                continue
            if link_kind == "external":
                self._add(self.external, {"file": name, "url": link.url.strip()})
                continue
            target = _target(link.url, name, link_kind)
            if target is None:
                reason = "outside the bundle"
            elif target == "" or any(item.startswith(target + "/") for item in files):
                reason = "not a file"
            elif target not in files:
                reason = "not found"
            else:
                if link_kind == "root" and rewrite and link.raw.startswith("/"):
                    new = "../" * depth + link.raw[1:]
                    if depth == 0 and ":" in new.split("/", 1)[0]:
                        new = "./" + new
                    edits.append((link, new))
                    self._add(
                        self.rewritten, {"file": name, "from": link.raw, "to": new}
                    )
                continue
            if target == "" and link_kind == "relative":
                continue
            self._add(
                self.missing, {"file": name, "link": link.url.strip(), "reason": reason}
            )
        if not edits:
            return data
        for link, new in sorted(edits, key=lambda edit: edit[0].start, reverse=True):
            text = text[: link.start] + new + text[link.end :]
        return _encode(text)


# --------------------------------------------------------------------------- #
# Collecting the files
# --------------------------------------------------------------------------- #


def _walk(root: Path) -> tuple[dict[str, Path], list[str]]:
    files: dict[str, Path] = {}
    excluded: list[str] = []
    for directory, directory_names, file_names in os.walk(root):
        for pruned in sorted(PRUNED_DIRECTORY_NAMES.intersection(directory_names)):
            directory_names.remove(pruned)
            excluded.append(
                (Path(directory) / pruned).relative_to(root).as_posix() + "/"
            )
        for file_name in file_names:
            path = Path(directory) / file_name
            name = path.relative_to(root).as_posix()
            if (
                file_name in EXCLUDED_FILE_NAMES
                or EXCLUDED_DIRECTORY_NAMES.intersection(name.split("/")[:-1])
                or path.is_symlink()
                or not path.is_file()
            ):
                excluded.append(name)
            else:
                files[name] = path
    return files, sorted(excluded)


def _linked_files(page: Path) -> dict[str, Path]:
    """Return the page and the local files that it links to, at any depth."""
    root = page.parent
    files = {page.name: page}
    queue = [page.name]
    while queue:
        name = queue.pop()
        if _kind(name) is None:
            continue
        links, _, _ = _scan(name, _decode(files[name].read_bytes()))
        for link in links:
            link_kind = _classify(link.url)
            if link_kind not in {"root", "relative"}:
                continue
            target = _target(link.url, name, link_kind)
            if not target or target in files:
                continue
            path = root / target
            if path.is_file():
                files[target] = path
                queue.append(target)
    return files


def _extract(archive_path: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                name = info.filename
                if info.is_dir():
                    continue
                parts = name.replace("\\", "/").split("/")
                if (
                    name.startswith(("/", "\\"))
                    or ".." in parts
                    or (parts and ":" in parts[0])
                ):
                    raise BundleError(
                        "unsafe_archive",
                        f"The archive has an unsafe file path, '{name}'. Make "
                        "the archive again with relative paths.",
                    )
                target = destination.joinpath(*[part for part in parts if part])
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, open(target, "wb") as output:
                    while chunk := source.read(1 << 20):
                        output.write(chunk)
    except (zipfile.BadZipFile, OSError) as error:
        raise BundleError(
            "invalid_archive",
            f"{archive_path.name} is not a readable zip archive: {error}",
        ) from error


# --------------------------------------------------------------------------- #
# Building
# --------------------------------------------------------------------------- #


def _new_report(input_path: Path | str) -> dict:
    return {
        "ok": False,
        "input": str(input_path),
        "input_kind": None,
        "form": None,
        "form_reason": None,
        "entry_page": None,
        "manifest": None,
        "files": [],
        "files_excluded": [],
        "links_rewritten": [],
        "external_links": [],
        "missing_links": [],
        "warnings": [],
        "output_path": None,
        "size_bytes": None,
        "size_limit_bytes": SIZE_LIMIT_BYTES,
        "error": None,
    }


def _as_it_is(report: dict, path: Path, form: str, reason: str) -> dict:
    report.update(
        ok=True,
        form=form,
        form_reason=reason,
        files=[path.name],
        size_bytes=check_size(path),
        output_path=str(path),
    )
    return report


def _resolve_output(output: Path | str | None, source: Path) -> Path:
    stem = source.name if source.is_dir() else source.stem
    if output is None:
        directory = Path(tempfile.mkdtemp(prefix="jinko-webapp-"))
        return directory / f"{stem}.zip"
    path = Path(os.path.abspath(output))
    resolved, resolved_source = path.resolve(), source.resolve()
    if resolved == resolved_source:
        raise BundleError(
            "output_is_input",
            "The output path is the input. Give another output path.",
        )
    if source.is_dir() and resolved_source in resolved.parents:
        raise BundleError(
            "output_in_input",
            "The output path is in the input directory. Give an output path "
            "outside it.",
        )
    return path


def _choose_entry(
    files: dict[str, Path], entry: str | None, warnings: list[str]
) -> tuple[str, str, bytes]:
    """Return the entry page, the manifest action, and the manifest content."""
    existing = files.get(MANIFEST_NAME)
    invalid_reason = None
    if existing is not None:
        content = existing.read_bytes()
        try:
            manifest = parse_manifest(content)
        except BundleError as error:
            invalid_reason = error.message
        else:
            if entry is None or entry == manifest["main"]:
                if manifest["main"] not in files:
                    raise BundleError(
                        "entry_missing",
                        f"manifest.json names the entry page '{manifest['main']}', "
                        "which is not in the bundle. Correct manifest.json, or "
                        "give the entry page with --entry.",
                    )
                return manifest["main"], "kept", content
            invalid_reason = f"its entry page is not '{entry}'"

    if entry is not None:
        if entry not in files:
            raise BundleError(
                "entry_missing",
                f"The entry page '{entry}' is not in the bundle.",
            )
    else:
        pages = sorted(name for name in files if _kind(name) == "html")
        if "index.html" in files:
            entry = "index.html"
        elif len(pages) == 1:
            entry = pages[0]
        elif not pages:
            raise BundleError(
                "no_entry_page",
                "The input has no HTML file, so it has no entry page.",
            )
        else:
            raise BundleError(
                "entry_ambiguous",
                "The input has several HTML files and no index.html at its top "
                "level. Give the entry page with --entry.",
                candidates=pages,
            )
    if existing is not None:
        warnings.append(
            f"The bundle gets a new manifest.json in place of the one of the "
            f"input ({invalid_reason}). The input is not changed."
        )
    content = json.dumps({"main": entry, "version": MANIFEST_VERSION}, indent=2)
    return entry, "replaced" if existing is not None else "added", content.encode()


def _write_bundle(
    report: dict,
    files: dict[str, Path],
    entry: str | None,
    output: Path,
) -> dict:
    warnings = report["warnings"]
    entry_page, action, manifest_content = _choose_entry(files, entry, warnings)
    names = sorted(name for name in files if name != MANIFEST_NAME)
    analysis = _Analysis()
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, manifest_content)
            for name in names:
                if _kind(name) is None:
                    archive.write(files[name], name)
                    continue
                data = files[name].read_bytes()
                archive.writestr(
                    name, analysis.process(name, data, set(names), rewrite=True)
                )
        check_bundle(partial)
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    warnings.extend(analysis.warnings)
    report.update(
        ok=True,
        entry_page=entry_page,
        manifest={"action": action, "content": json.loads(manifest_content)},
        files=[MANIFEST_NAME, *names],
        links_rewritten=analysis.rewritten,
        external_links=analysis.external,
        missing_links=analysis.missing,
        output_path=str(output),
        size_bytes=output.stat().st_size,
    )
    return report


def _build_from_page(
    report: dict, page: Path, output: Path | str | None, form: str
) -> dict:
    report["input_kind"] = "html"
    files = _linked_files(page)
    beside = sorted(name for name in files if name != page.name)
    data = page.read_bytes()
    _, has_script, _ = _scan(page.name, _decode(data))
    if form == "auto":
        if has_script:
            chosen, reason = "application", "The page has a script."
        elif beside:
            chosen = "application"
            reason = f"The page links to files beside it: {', '.join(beside)}."
        else:
            chosen = "html"
            reason = "The page has no script and no link to a file beside it."
    else:
        chosen = form
        name = "embedded application" if form == "application" else "HTML raw file"
        reason = f"The {name} form was requested."

    if chosen == "html":
        analysis = _Analysis()
        analysis.process(page.name, data, set(files), rewrite=False)
        report.update(
            external_links=analysis.external,
            missing_links=analysis.missing,
        )
        report["warnings"].extend(analysis.warnings)
        if beside:
            report["warnings"].append(
                "The page links to local files that an HTML raw file does not "
                f"include: {', '.join(beside)}."
            )
        return _as_it_is(report, page, "html", reason)

    report.update(form="application", form_reason=reason)
    return _write_bundle(report, files, page.name, _resolve_output(output, page))


def _build_from_tree(
    report: dict,
    root: Path,
    source: Path,
    output: Path | str | None,
    entry: str | None,
    form: str,
) -> dict:
    files, excluded = _walk(root)
    report["files_excluded"] = excluded
    top = {name.split("/", 1)[0] for name in files}
    if source.is_file() and len(top) == 1 and all("/" in name for name in files):
        wrapper = top.pop()
        files = {name.split("/", 1)[1]: path for name, path in files.items()}
        report["warnings"].append(
            f"The archive holds one directory, '{wrapper}'. Its content is the "
            "top level of the bundle."
        )
    has_page = any(_kind(name) == "html" for name in files)
    if source.is_file() and form == "auto" and not has_page:
        if MANIFEST_NAME not in files:
            return _as_it_is(
                report,
                source,
                "file",
                "The archive has no HTML file, so it is not a web app.",
            )
    reason = (
        "The embedded application form was requested."
        if form == "application"
        else f"The {report['input_kind']} is a web app with an entry page."
    )
    report.update(form="application", form_reason=reason)
    if entry is not None:
        entry = posixpath.normpath(entry.replace("\\", "/"))
    return _write_bundle(report, files, entry, _resolve_output(output, source))


def build(
    input_path: Path | str,
    *,
    output: Path | str | None = None,
    entry: str | None = None,
    form: str = "auto",
    report: dict | None = None,
) -> dict:
    """Prepare the input for a push, and return the report.

    Raise ``BundleError`` when the input cannot go to Jinkō as it is and the
    command cannot make it valid.
    """
    report = _new_report(input_path) if report is None else report
    source = Path(os.path.abspath(input_path))
    if not source.exists():
        raise BundleError("input_not_found", f"'{input_path}' does not exist.")
    suffix = source.suffix.lower()

    if source.is_dir():
        report["input_kind"] = "directory"
        if form == "html":
            raise BundleError(
                "form_not_possible",
                "A directory cannot go as an HTML raw file. Give one HTML file.",
            )
        return _build_from_tree(report, source, source, output, entry, form)

    if suffix in HTML_SUFFIXES:
        return _build_from_page(report, source, output, form)

    if suffix == ".zip":
        report["input_kind"] = "zip"
        if form == "html":
            raise BundleError(
                "form_not_possible",
                "A zip archive cannot go as an HTML raw file. Give one HTML file.",
            )
        with tempfile.TemporaryDirectory(prefix="jinko-webapp-") as temporary:
            _extract(source, Path(temporary))
            return _build_from_tree(
                report, Path(temporary), source, output, entry, form
            )

    report["input_kind"] = "file"
    if form != "auto":
        raise BundleError(
            "form_not_possible",
            "This file is not a web app. It can only go to Jinkō as it is.",
        )
    return _as_it_is(report, source, "file", "The file is not a web app.")


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a file or a web app for a push to Jinkō as a raw file."
    )
    parser.add_argument(
        "input", help="A file, an HTML file, a directory, or a zip archive."
    )
    parser.add_argument(
        "--output",
        help="Path of the zip bundle to write. Default: a new temporary directory.",
    )
    parser.add_argument(
        "--entry",
        help="Entry page, relative to the top level of the bundle.",
    )
    parser.add_argument(
        "--form",
        choices=("auto", "html", "application"),
        default="auto",
        help="Form in Jinkō. Default: the command chooses, and says why.",
    )
    parser.add_argument("--report", help="Also write the JSON report to this path.")
    args = parser.parse_args(argv)

    report = _new_report(args.input)
    try:
        build(
            args.input,
            output=args.output,
            entry=args.entry,
            form=args.form,
            report=report,
        )
    except BundleError as error:
        report.update(
            ok=False,
            output_path=None,
            error={"code": error.code, "message": error.message, **error.details},
        )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
