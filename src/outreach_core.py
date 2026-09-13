"""Pure helpers for the cold outreach pipeline (stdlib only)."""

import json
import os
import re

BLOCKED_DOMAINS = {
    'sentry.io', 'wix.com', 'shopify.com', 'google.com', 'example.com',
    'domain.com', 'mysite.com', 'yourdomain.com', 'email.com', '2x.png', '3x.png'
}
BLOCKED_KEYWORDS = ['test', 'example', 'placeholder', 'mysite', 'yourdomain', 'template', 'globe@']
BLOCKED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf', '.webp', '.css', '.js')

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
FULL_PLACEHOLDER_SUBJECTS = {"...", "Subject", "None", "null"}


def clean_emails(raw_emails):
    """Filter raw scraped email candidates down to plausible addresses.

    Applies the same blocking rules as the original pipeline: domain/keyword/
    extension denylists, googlemail->gmail normalization, hash-like user check,
    and finally prioritises gmail.com addresses.
    """
    clean = []
    for email in set(raw_emails):
        email_lower = email.lower()
        if any(email_lower.endswith(ext) for ext in BLOCKED_EXTENSIONS):
            continue
        if any(kw in email_lower for kw in BLOCKED_KEYWORDS):
            continue
        if "googlemail.com" in email_lower:
            email_lower = email_lower.replace("googlemail.com", "gmail.com")
        domain = email_lower.split('@')[-1]
        user = email_lower.split('@')[0]
        if domain not in BLOCKED_DOMAINS and len(user) < 30 \
                and not re.search(r'[a-f0-9]{20,}', user) \
                and 'sentry' not in email_lower and 'noreply' not in email_lower:
            clean.append(email_lower)
    return sorted(set(clean), key=lambda x: ("gmail.com" not in x))


def website_root(href):
    """Lowercased scheme://host root of a link, or None when not an http(s) URL."""
    if not href or "google.com" in href:
        return None
    match = re.match(r"(https?://[^/\s]+)", href.lower())
    return match.group(1) if match else None


def is_valid_email_address(email):
    """True when the address matches the send-time validation regex."""
    return bool(re.match(EMAIL_REGEX, email))


def is_valid_subject(subject):
    """True when the subject is a real, usable subject line."""
    subject = subject.strip() if subject else ""
    return bool(subject) and subject not in FULL_PLACEHOLDER_SUBJECTS and len(subject) >= 3


def load_processed_memory(path):
    """Load the set of processed URLs from a JSON file; empty set on any error."""
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def save_processed_memory(path, url):
    """Append a processed URL to the JSON memory file, best-effort."""
    try:
        memory = list(load_processed_memory(path))
        if url not in memory:
            memory.append(url)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as f:
                json.dump(memory, f)
    except Exception:
        pass


def next_output_filename(directory, base_name, extension):
    """First unused `base_name(n)extension` path inside `directory`."""
    os.makedirs(directory, exist_ok=True)
    counter = 1
    while True:
        file_path = os.path.join(directory, f"{base_name}({counter}){extension}")
        if not os.path.exists(file_path):
            return file_path
        counter += 1