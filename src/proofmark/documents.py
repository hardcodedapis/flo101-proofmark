from __future__ import annotations

import base64
import binascii
import re
import urllib.parse
import zlib
from pathlib import PurePath
from typing import Any


MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".text", ".notes"}
LATEX_EXTENSIONS = {".tex", ".latex"}
PDF_EXTENSIONS = {".pdf"}


def has_document_payload(item: dict[str, Any]) -> bool:
    return any(item.get(key) for key in ("data_url", "file_data", "content_base64", "base64"))


def parse_document_source(item: dict[str, Any]) -> dict[str, Any]:
    filename = _filename(item)
    mime_type = str(item.get("mime_type") or item.get("content_type") or "").lower()
    extension = PurePath(filename).suffix.lower()
    try:
        raw = _decode_payload(item)
    except ValueError as exc:
        return _failed(filename, mime_type, extension, f"Document payload could not be decoded: {exc}")

    if len(raw) > MAX_DOCUMENT_BYTES:
        return _failed(filename, mime_type, extension, "Document is larger than the 8 MB parser limit.")

    try:
        if extension in PDF_EXTENSIONS or "pdf" in mime_type:
            text = extract_pdf_text(raw)
            parser = "pdf_text_stream_best_effort"
        elif extension in LATEX_EXTENSIONS or "latex" in mime_type or "x-tex" in mime_type:
            text = normalize_latex_source(_decode_text(raw))
            parser = "latex_source"
        elif extension in TEXT_EXTENSIONS or "text" in mime_type or "markdown" in mime_type or not extension:
            decoded = _decode_text(raw)
            parser = "markdown_text" if extension in {".md", ".markdown"} or "markdown" in mime_type else "plain_text"
            text = normalize_markdown_text(decoded) if parser == "markdown_text" else decoded
        else:
            return _failed(filename, mime_type, extension, f"Unsupported document type '{extension or mime_type}'.")
    except ValueError as exc:
        return _failed(filename, mime_type, extension, str(exc))

    text = _clean_text(text)
    if not text:
        return _failed(filename, mime_type, extension, "No readable text was extracted.")

    return {
        "filename": filename,
        "mime_type": mime_type,
        "extension": extension,
        "parser": parser,
        "text": text,
        "math_detected": has_math(text),
    }


def normalize_markdown_text(value: str) -> str:
    text = re.sub(r"\A---\s*\n.*?\n---\s*", "", value, flags=re.DOTALL)
    text = re.sub(r"```.*?```", _code_block_text, text, flags=re.DOTALL)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^\s{0,3}[-*+]\s+", "", text)
    text = re.sub(r"(?m)^\s{0,3}\d+[.)]\s+", "", text)
    text = re.sub(r"(?m)^\s{0,3}>\s?", "", text)
    text = re.sub(r"(?m)^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", " ", text)
    text = text.replace("|", " ")
    text = re.sub(r"(?<!\\)(\*\*|__)(.+?)(?<!\\)\1", r"\2", text)
    text = re.sub(r"(?<!\\)(`)(.+?)(?<!\\)`", r"\2", text)
    return text


def normalize_latex_source(value: str) -> str:
    lines = []
    for line in value.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*$", "", line))
    text = "\n".join(lines)
    text = re.sub(r"\\(section|subsection|subsubsection|paragraph)\*?\{([^{}]*)\}", r"\2\n", text)
    text = re.sub(r"\\(textbf|textit|emph|underline)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\(begin|end)\{[^{}]+\}", " ", text)
    text = re.sub(r"\\item\s+", "- ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", _latex_command_text, text)
    return text


def extract_pdf_text(raw: bytes) -> str:
    payloads = _pdf_text_payloads(raw)
    texts: list[str] = []
    for payload in payloads:
        block_text = payload.decode("latin-1", errors="ignore")
        for block in re.findall(r"BT\b(.*?)\bET", block_text, flags=re.DOTALL):
            texts.extend(_extract_pdf_strings(block))
    if not texts:
        fallback = raw.decode("latin-1", errors="ignore")
        texts.extend(_extract_pdf_strings(fallback))
    cleaned = _clean_pdf_fragments(texts)
    if not cleaned:
        raise ValueError("No readable PDF text was extracted. Scanned/image-only PDFs need OCR before upload.")
    return cleaned


def has_math(text: str) -> bool:
    patterns = [
        r"\$\$[^$]+\$\$",
        r"(?<!\\)\$[^$\n]{1,240}(?<!\\)\$",
        r"\\\([^)]+\\\)",
        r"\\\[[\s\S]+?\\\]",
        r"\\frac\{",
        r"\\sum\b",
        r"\\int\b",
        r"\\sqrt\{",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _filename(item: dict[str, Any]) -> str:
    value = str(item.get("filename") or item.get("name") or item.get("title") or "uploaded-document").strip()
    return PurePath(value).name or "uploaded-document"


def _decode_payload(item: dict[str, Any]) -> bytes:
    encoded = str(
        item.get("data_url")
        or item.get("file_data")
        or item.get("content_base64")
        or item.get("base64")
        or ""
    )
    if not encoded:
        raise ValueError("missing file data")
    if encoded.startswith("data:"):
        _meta, data = encoded.split(",", 1)
        if ";base64" in _meta:
            return base64.b64decode(data, validate=True)
        return urllib.parse.unquote_to_bytes(data)
    try:
        return base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("expected base64 or data URL") from exc


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Document text could not be decoded.")


def _pdf_text_payloads(raw: bytes) -> list[bytes]:
    payloads = []
    stream_pattern = re.compile(rb"(<<.*?>>)\s*stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
    for header, body in stream_pattern.findall(raw):
        body = body.strip(b"\r\n")
        if b"FlateDecode" in header:
            try:
                payloads.append(zlib.decompress(body))
            except zlib.error:
                continue
        else:
            payloads.append(body)
    if not payloads:
        payloads.append(raw)
    return payloads


def _extract_pdf_strings(block: str) -> list[str]:
    strings = [_decode_pdf_literal(match) for match in re.findall(r"\((?:\\.|[^\\)])*\)", block)]
    strings.extend(_decode_pdf_hex(match) for match in re.findall(r"<([0-9A-Fa-f\s]{6,})>", block))
    return [item for item in strings if item]


def _decode_pdf_literal(value: str) -> str:
    inner = value[1:-1]
    out: list[str] = []
    index = 0
    while index < len(inner):
        char = inner[index]
        if char != "\\":
            out.append(char)
            index += 1
            continue
        index += 1
        if index >= len(inner):
            break
        escaped = inner[index]
        mapping = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "(": "(", ")": ")", "\\": "\\"}
        if escaped in mapping:
            out.append(mapping[escaped])
            index += 1
        elif escaped in "\r\n":
            while index < len(inner) and inner[index] in "\r\n":
                index += 1
        elif escaped.isdigit():
            octal = escaped
            index += 1
            for _ in range(2):
                if index < len(inner) and inner[index].isdigit():
                    octal += inner[index]
                    index += 1
            out.append(chr(int(octal[:3], 8)))
        else:
            out.append(escaped)
            index += 1
    return "".join(out)


def _decode_pdf_hex(value: str) -> str:
    compact = re.sub(r"\s+", "", value)
    if len(compact) % 2:
        compact += "0"
    try:
        raw = bytes.fromhex(compact)
    except ValueError:
        return ""
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="ignore")
    return raw.decode("latin-1", errors="ignore")


def _clean_pdf_fragments(fragments: list[str]) -> str:
    cleaned = []
    for fragment in fragments:
        fragment = re.sub(r"\s+", " ", fragment).strip()
        if len(fragment) < 2:
            continue
        if sum(ch.isprintable() for ch in fragment) / max(1, len(fragment)) < 0.85:
            continue
        cleaned.append(fragment)
    return _clean_text(" ".join(cleaned))


def _clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()[:180_000]


def _code_block_text(match: re.Match[str]) -> str:
    block = match.group(0)
    lines = block.splitlines()
    if len(lines) <= 2:
        return " "
    return "\n".join(lines[1:-1])


def _latex_command_text(match: re.Match[str]) -> str:
    argument = match.group(1)
    return argument if argument else " "


def _failed(filename: str, mime_type: str, extension: str, message: str) -> dict[str, Any]:
    return {
        "filename": filename,
        "mime_type": mime_type,
        "extension": extension,
        "parser": "unsupported_or_failed",
        "text": "",
        "math_detected": False,
        "parse_warning": message,
    }
