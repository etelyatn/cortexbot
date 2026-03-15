"""Tests for message chunking and media utilities."""

import pytest

from cortexbot.bot.media import chunk_message


class TestChunkMessage:
    """Test splitting long text for Telegram's 4096-char limit."""

    def test_short_message_unchanged(self) -> None:
        """Messages under limit are returned as single chunk."""
        result = chunk_message("Hello, world!")
        assert result == ["Hello, world!"]

    def test_empty_message(self) -> None:
        """Empty message returns empty list."""
        result = chunk_message("")
        assert result == []

    def test_split_on_paragraph_boundary(self) -> None:
        """Long messages split at paragraph boundaries (double newline)."""
        para1 = "A" * 2000
        para2 = "B" * 2000
        para3 = "C" * 2000
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = chunk_message(text, max_len=4096)
        assert len(chunks) >= 2
        # Reassembly should produce original content (minus any trailing whitespace)
        reassembled = "\n\n".join(chunks)
        assert para1 in reassembled
        assert para2 in reassembled
        assert para3 in reassembled

    def test_no_chunk_exceeds_limit(self) -> None:
        """No single chunk exceeds max_len."""
        text = "word " * 2000  # ~10000 chars
        chunks = chunk_message(text, max_len=4096)
        for chunk in chunks:
            assert len(chunk) <= 4096

    def test_single_long_line_force_split(self) -> None:
        """A single line longer than limit is hard-split."""
        text = "X" * 8000
        chunks = chunk_message(text, max_len=4096)
        assert len(chunks) == 2
        assert chunks[0] == "X" * 4096
        assert chunks[1] == "X" * 3904
