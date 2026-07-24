import os
import pytest
from src.data.loader import (
    get_live_recorder_status, stop_live_recorder, load_live_session, CACHE_DIR
)

def test_get_live_recorder_status_non_existent():
    """Test status function when the target live stream file does not exist."""
    status = get_live_recorder_status("non_existent_stream_file_9999.txt")
    assert status["active"] is False
    assert status["exists"] is False
    assert status["size_bytes"] == 0
    assert status["line_count"] == 0

def test_get_live_recorder_status_mock_file(tmp_path):
    """Test status function with a valid temporary stream text file."""
    test_file = tmp_path / "mock_live_timing.txt"
    content = "Header\nPacket1\nPacket2\nPacket3\n"
    test_file.write_text(content, encoding="utf-8")
    
    status = get_live_recorder_status(str(test_file))
    assert status["exists"] is True
    assert status["line_count"] == 4
    assert status["size_bytes"] == len(content.encode("utf-8"))

def test_stop_live_recorder_inactive():
    """Test stopping an inactive live recorder instance."""
    res = stop_live_recorder("non_existent_recorder_123.txt")
    assert res["success"] is False
    assert "No active live recorder" in res["message"]

def test_load_live_session_missing_file():
    """Test load_live_session gracefully returns error for missing stream file."""
    sess, err = load_live_session(2024, "China", "R", "missing_live_stream_file.txt")
    assert sess is None
    assert err is not None
    assert "empty or does not exist" in err
