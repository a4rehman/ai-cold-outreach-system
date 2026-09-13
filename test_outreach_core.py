"""Tests for the outreach core helpers (stdlib only, no API/clients)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from outreach_core import (
    clean_emails,
    website_root,
    is_valid_email_address,
    is_valid_subject,
    load_processed_memory,
    save_processed_memory,
    next_output_filename,
)


def test_clean_emails_drops_extensions():
    assert clean_emails(["info@salon.com", "logo@salon.png", "icon@site.svg", "banner@hero.jpeg"]) == ["info@salon.com"]


def test_clean_emails_drops_blocked_domains():
    assert clean_emails(["me@wix.com", "me@shopify.com", "hi@example.com", "ok@realsalon.com"]) == ["ok@realsalon.com"]


def test_clean_emails_drops_keywords():
    assert clean_emails(["test@salon.com", "noreply@salon.com", "real@salon.com"]) == ["real@salon.com"]


def test_clean_emails_normalises_googlemail():
    assert clean_emails(["owner@googlemail.com"]) == ["owner@gmail.com"]


def test_clean_emails_gmail_prioritised():
    result = clean_emails(["b@yahoo.com", "a@gmail.com"])
    assert result[0] == "a@gmail.com"


def test_clean_emails_accepts_general_good_address():
    assert "jane.43+filter@mydomain.co.uk" in clean_emails(["jane.43+filter@mydomain.co.uk"])


def test_website_root():
    assert website_root("HTTPS://SalonExample.com/contact") == "https://salonexample.com"
    assert website_root("http://foo.com") == "http://foo.com"
    assert website_root(None) is None
    assert website_root("google.com/search") is None
    assert website_root("ftp://x.com") is None


def test_is_valid_email_address():
    assert is_valid_email_address("owner@salon.com")
    assert is_valid_email_address("a.b@sub.co.uk")
    assert not is_valid_email_address("not-an-email")
    assert not is_valid_email_address("owner@")
    assert not is_valid_email_address("")


def test_is_valid_subject():
    assert is_valid_subject("Quick question about your salon")
    assert not is_valid_subject("")
    assert not is_valid_subject("..")
    assert not is_valid_subject("Subject")
    assert not is_valid_subject("null")


def test_processed_memory_roundtrip(tmp_path=None):
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "processed.json")
        assert load_processed_memory(path) == set()
        save_processed_memory(path, "https://a.com")
        save_processed_memory(path, "https://b.com")
        save_processed_memory(path, "https://a.com")  # dedupe
        assert load_processed_memory(path) == {"https://a.com", "https://b.com"}


def test_processed_memory_bad_file_is_empty():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "broken.json")
        with open(path, "w") as f:
            f.write("not json")
        assert load_processed_memory(path) == set()


def test_next_output_filename_increments():
    with tempfile.TemporaryDirectory() as td:
        first = next_output_filename(td, "results", ".json")
        assert os.path.basename(first) == "results(1).json"
        open(first, "w").close()
        second = next_output_filename(td, "results", ".json")
        assert os.path.basename(second) == "results(2).json"


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL OUTREACH CORE TESTS PASSED")