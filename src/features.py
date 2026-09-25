"""Deterministic, offline lexical features shared by training and serving."""
from collections import Counter
from functools import lru_cache
import ipaddress
import math
import re
from urllib.parse import urlsplit
import tldextract

# Bundled PSL, no downloads or cache-dependent results. Private suffixes are
# excluded so whole hosting platforms stay together during evaluation.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def normalize_url(url):
    """Feature representation, not a claim HTTP/HTTPS/www serve the same page.

    Ignore scheme and leading www consistently; preserve userinfo, port,
    path/query case and fragment. Treat an empty root path like '/'.
    Conflicting labels collapsed by this representation are quarantined.
    """
    url = (url or '').strip()
    rest = re.sub(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', '', url)
    if rest.startswith('//'):
        rest = rest[2:]
    cut = min([rest.find(ch) for ch in '/?#' if ch in rest] or [len(rest)])
    authority, tail = rest[:cut], rest[cut:]
    userinfo, sep, hostport = authority.rpartition('@')
    hostport = hostport.lower()
    while hostport.startswith('www.'):
        hostport = hostport[4:]
    if tail == '/' or tail.startswith('/?') or tail.startswith('/#'):
        tail = tail[1:]
    return userinfo + sep + hostport + tail


def parse_host(url):
    return urlsplit('//' + normalize_url(url)).hostname or ''


@lru_cache(maxsize=200000)
def registered_domain(host):
    ext = _EXTRACT(host)
    return ext.top_domain_under_public_suffix or host


def domain_group(url):
    return registered_domain(parse_host(url))


def url_length(url):
    return len(url)


def count_special_chars(url):
    return url.count('@') + url.count('-') + url.count('//')


def has_ip_address(url):
    try:
        ipaddress.ip_address(parse_host(url))
        return 1
    except ValueError:
        return 0


def subdomain_count(url):
    if has_ip_address(url):
        return 0
    subdomain = _EXTRACT(parse_host(url)).subdomain
    return len(subdomain.split('.')) if subdomain else 0


def has_https(url):
    return 0  # Legacy cached column; excluded from model schema.


def shannon_entropy(url):
    if not url:
        return 0.0
    # Stable across Python hash seeds, unlike iterating over set(url).
    probabilities = [n / len(url) for n in sorted(Counter(url).values())]
    return -math.fsum(p * math.log2(p) for p in probabilities)


def digit_ratio(url):
    return sum(c.isdigit() for c in url) / len(url) if url else 0.0


def path_depth(url):
    return len([s for s in urlsplit('//' + normalize_url(url)).path.split('/') if s])


def extract_features(url):
    url = normalize_url(url)
    return {
        'url_length': url_length(url), 'special_chars': count_special_chars(url),
        'has_ip': has_ip_address(url), 'subdomain_count': subdomain_count(url),
        'has_https': 0, 'entropy': shannon_entropy(url),
        'digit_ratio': digit_ratio(url), 'path_depth': path_depth(url),
    }
