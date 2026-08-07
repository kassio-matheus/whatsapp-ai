"""Document reading hook: the place where the file-reading AI plugs in.

Uploaded knowledge documents are stored, then passed through
:func:`extract_document_text`; the returned text is kept next to the file and
injected into the AI assistant's system prompt, so the model answers from the
company's own files without tool calls.

This is intentionally a single, isolated function so the reading AI of your
choice (vision model, PDF parser, OCR service, ...) can be swapped in without
touching the rest of the pipeline. Implement it wherever you like and call it
from here.
"""

from __future__ import annotations


def extract_document_text(*, filename: str, mime_type: str, data: bytes) -> str:
    """Return the textual content of an uploaded document.

    An empty string means "no text extracted yet": the document stays queued
    with ``pending`` status, ready for the reading AI to process it later.

    TODO(ai-reader): implement the document-reading AI here. The current
    placeholder only reads plain-text files natively; every other format
    remains ``pending``.
    """
    if mime_type in {"text/plain"} or filename.lower().endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    return ""
