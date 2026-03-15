"""Message chunking and media utilities for Telegram."""

from __future__ import annotations

TELEGRAM_MAX_MESSAGE_LEN = 4096


def chunk_message(text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LEN) -> list[str]:
    """Split text into chunks that fit Telegram's message limit.

    Splits on paragraph boundaries (double newline) when possible,
    falls back to hard split on max_len.

    Args:
        text: Message text to split
        max_len: Maximum characters per chunk (default 4096)

    Returns:
        List of text chunks, each <= max_len
    """
    if not text:
        return []

    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para

        if len(candidate) <= max_len:
            current = candidate
        else:
            # Flush current if non-empty
            if current:
                chunks.append(current)
                current = ""

            # If this paragraph alone exceeds limit, hard-split it
            if len(para) > max_len:
                while para:
                    chunks.append(para[:max_len])
                    para = para[max_len:]
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks
