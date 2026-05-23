from __future__ import annotations

import html
import ipaddress
import json
import math
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class RagError(RuntimeError):
    pass


def extract_url_text(url: str, timeout: float = 8.0) -> dict[str, Any]:
    if _should_skip_url_fetch(url):
        return {
            "text": "",
            "content_type": "",
            "warning": "url_type_not_text_fetched",
        }
    _validate_fetchable_url(url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ProofLoop-RAG/0.1 (+local demo)",
            "Accept": "text/html,text/plain,application/xhtml+xml",
        },
        method="GET",
    )
    try:
        opener = urllib.request.build_opener(_PublicRedirectHandler())
        with opener.open(req, timeout=timeout) as response:
            final_url = response.geturl()
            if final_url:
                _validate_fetchable_url(final_url)
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(600_000)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RagError(f"Could not fetch URL: {exc}") from exc

    if _looks_binary_url(url, content_type, raw):
        return {
            "text": "",
            "content_type": content_type,
            "warning": "binary_or_pdf_url_not_text_extracted",
        }

    text = raw.decode("utf-8", errors="replace")
    if "html" in content_type or "<html" in text[:1000].lower():
        text = _html_to_text(text)
    return {
        "text": _clean_extracted_text(text),
        "content_type": content_type,
    }


def _looks_binary_url(url: str, content_type: str, raw: bytes) -> bool:
    lowered_type = content_type.lower()
    lowered_url = url.lower()
    if "application/pdf" in lowered_type or lowered_url.endswith(".pdf") or raw.startswith(b"%PDF"):
        return True
    if "text/" in lowered_type or "html" in lowered_type or "json" in lowered_type or "xml" in lowered_type:
        return False
    sample = raw[:2000]
    if not sample:
        return False
    replacement_ratio = sample.count(b"\x00") / max(1, len(sample))
    return replacement_ratio > 0.02


def _should_skip_url_fetch(url: str) -> bool:
    lowered = url.lower()
    return (
        "youtube.com/" in lowered
        or "youtu.be/" in lowered
        or lowered.endswith((".pdf", ".mp4", ".mov", ".webm", ".mpeg", ".mpg"))
    )


def _validate_fetchable_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RagError("URL fetch only supports http and https URLs.")
    host = parsed.hostname
    if not host:
        raise RagError("URL fetch requires a valid host.")
    lowered_host = host.lower().rstrip(".")
    if lowered_host in {"localhost", "localhost.localdomain"} or lowered_host.endswith(".localhost"):
        raise RagError("URL fetch blocked local host.")

    addresses = _resolve_host_addresses(lowered_host)
    for address in addresses:
        if not address.is_global:
            raise RagError(f"URL fetch blocked non-public host address: {address}")


def _validated_redirect_url(current_url: str, redirect_url: str) -> str:
    resolved = urllib.parse.urljoin(current_url, redirect_url)
    _validate_fetchable_url(resolved)
    return resolved


class _PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        safe_url = _validated_redirect_url(req.full_url, newurl)
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


def _resolve_host_addresses(host: str) -> list[ipaddress._BaseAddress]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RagError(f"Could not resolve URL host: {host}") from exc
    addresses: list[ipaddress._BaseAddress] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise RagError(f"Could not resolve URL host: {host}")
    return addresses


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", value)
    value = re.sub(r"(?is)<br\s*/?>", "\n", value)
    value = re.sub(r"(?is)</(p|div|section|article|li|h[1-6])>", "\n", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    return html.unescape(value)


def _clean_extracted_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    lines = [line for line in lines if len(line) >= 20 and not _looks_like_pdf_noise(line)]
    return "\n".join(lines)[:120_000]


def _looks_like_pdf_noise(line: str) -> bool:
    lower = line.lower()
    if any(token in lower for token in ["/filter", "/flatedecode", "endstream", " obj", "xref", "startxref"]):
        return True
    weird = sum(1 for char in line if char in "{}<>/\\\x00\ufffd")
    return weird / max(1, len(line)) > 0.18


def embed_texts(
    texts: list[str],
    api_key: str = "",
    model: str = "text-embedding-3-small",
    dimensions: int | None = None,
) -> list[list[float]]:
    api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise RagError("OPENAI_API_KEY is required for embedding RAG.")
    if not texts:
        return []

    body: dict[str, Any] = {
        "model": model,
        "input": texts,
    }
    if dimensions:
        body["dimensions"] = dimensions
    req = urllib.request.Request(
        f"{os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')}/embeddings",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(os.getenv("PROOFMARK_EMBEDDING_TIMEOUT", os.getenv("PROOFMARK_PROVIDER_TIMEOUT", "75")))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw)
        ordered = sorted(payload["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in ordered]
    except TimeoutError as exc:
        raise RagError(f"Embedding request timed out after {timeout:.0f}s.") from exc
    except (urllib.error.URLError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RagError(f"Embedding request failed: {exc}") from exc


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(left[index] * left[index] for index in range(size)))
    right_norm = math.sqrt(sum(right[index] * right[index] for index in range(size)))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def pinecone_upsert_and_query(
    *,
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
    query_vector: list[float],
    api_key: str,
    index_host: str,
    namespace: str,
    top_k: int,
) -> dict[str, Any]:
    if not api_key or not index_host:
        raise RagError("Pinecone API key and index host are required.")
    if len(chunks) != len(vectors):
        raise RagError("Chunk/vector count mismatch.")

    vector_records = []
    chunk_by_id = {}
    for chunk, vector in zip(chunks, vectors):
        chunk_id = str(chunk["id"])
        chunk_by_id[chunk_id] = chunk
        vector_records.append(
            {
                "id": chunk_id,
                "values": vector,
                "metadata": {
                    "id": chunk_id,
                    "source_id": chunk.get("source_id", ""),
                    "source_title": chunk.get("source_title", ""),
                    "source_type": chunk.get("source_type", ""),
                    "source_state": chunk.get("source_state", "usable_text"),
                    "content_is_grounded": bool(chunk.get("content_is_grounded", True)),
                    "url": chunk.get("url", ""),
                    "start": chunk.get("start", ""),
                    "end": chunk.get("end", ""),
                    "text": chunk.get("text", "")[:32_000],
                    "concepts": ", ".join(chunk.get("concepts", [])[:8]),
                },
            }
        )

    base = _normalize_index_host(index_host)
    headers = {
        "Api-Key": api_key,
        "Content-Type": "application/json",
        "X-Pinecone-Api-Version": "2026-04",
    }
    _post_json(
        f"{base}/vectors/upsert",
        headers,
        {
            "namespace": namespace,
            "vectors": vector_records,
        },
    )
    query_payload = _post_json(
        f"{base}/query",
        headers,
        {
            "namespace": namespace,
            "vector": query_vector,
            "topK": max(1, min(50, top_k)),
            "includeMetadata": True,
            "includeValues": False,
        },
    )

    matches = []
    for match in query_payload.get("matches", []):
        metadata = match.get("metadata") or {}
        chunk_id = str(metadata.get("id") or match.get("id") or "")
        chunk = chunk_by_id.get(chunk_id, {})
        concepts = chunk.get("concepts", [])
        if not concepts and metadata.get("concepts"):
            concepts = [
                concept.strip()
                for concept in str(metadata.get("concepts", "")).split(",")
                if concept.strip()
            ]
        matches.append(
            {
                "id": chunk_id,
                "score": float(match.get("score", 0.0)),
                "metadata": metadata,
                "chunk": {
                    **chunk,
                    "id": chunk.get("id") or chunk_id,
                    "source_id": metadata.get("source_id") or chunk.get("source_id", ""),
                    "text": metadata.get("text") or chunk.get("text", ""),
                    "source_title": metadata.get("source_title") or chunk.get("source_title", ""),
                    "source_type": metadata.get("source_type") or chunk.get("source_type", ""),
                    "source_state": metadata.get("source_state") or chunk.get("source_state", "usable_text"),
                    "content_is_grounded": metadata.get("content_is_grounded", chunk.get("content_is_grounded", True)),
                    "url": metadata.get("url") or chunk.get("url", ""),
                    "start": metadata.get("start") or chunk.get("start", ""),
                    "end": metadata.get("end") or chunk.get("end", ""),
                    "concepts": concepts,
                },
            }
        )
    return {"matches": matches, "namespace": namespace}


def _normalize_index_host(index_host: str) -> str:
    host = index_host.strip().rstrip("/")
    if not host:
        raise RagError("Pinecone index host is required.")
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    return host


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    timeout = float(os.getenv("PROOFMARK_PINECONE_TIMEOUT", os.getenv("PROOFMARK_PROVIDER_TIMEOUT", "75")))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RagError(f"Pinecone HTTP {exc.code}: {detail[:300]}") from exc
    except TimeoutError as exc:
        raise RagError(f"Pinecone request timed out after {timeout:.0f}s.") from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RagError(f"Pinecone request failed: {exc}") from exc
