import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.github_service import decode_repository_file


def _encoded_file(content):
    return {
        "type": "file",
        "name": "main.py",
        "path": "main.py",
        "encoding": "base64",
        "content": base64.b64encode(content).decode("ascii"),
    }


def test_decode_repository_file_marks_valid_utf8():
    result = decode_repository_file(_encoded_file(b"print('hello')"))

    assert result["valid_utf8"] is True
    assert result["decoded_content"] == "print('hello')"


def test_decode_repository_file_marks_invalid_utf8():
    result = decode_repository_file(_encoded_file(b"print('bad')\xff"))

    assert result["valid_utf8"] is False
    assert "\ufffd" in result["decoded_content"]
