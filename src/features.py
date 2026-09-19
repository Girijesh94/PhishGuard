import re
import math
from urllib.parse import urlparse
import tldextract

def url_length(url):
    return len(url)

def count_special_chars(url):
    scheme_stripped = re.sub(r'^https?://', '', url)
    at_count = url.count('@')
    hyphen_count = url.count('-')
    double_slash_count = scheme_stripped.count('//')
    return at_count + hyphen_count + double_slash_count

def has_ip_address(url):
    domain = urlparse(url).netloc
    domain = domain.split(':')[0]
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    return 1 if re.match(pattern, domain) else 0

def subdomain_count(url):
    ext = tldextract.extract(url)
    if not ext.subdomain:
        return 0
    return len(ext.subdomain.split('.'))

def has_https(url):
    return 1 if urlparse(url).scheme == 'https' else 0

def shannon_entropy(url):
    if not url:
        return 0
    prob = [float(url.count(c)) / len(url) for c in set(url)]
    return -sum(p * math.log2(p) for p in prob)

def digit_ratio(url):
    if not url:
        return 0
    digits = sum(c.isdigit() for c in url)
    return digits / len(url)

def path_depth(url):
    path = urlparse(url).path
    segments = [s for s in path.split('/') if s]
    return len(segments)

def extract_features(url):
    return {
        'url_length': url_length(url),
        'special_chars': count_special_chars(url),
        'has_ip': has_ip_address(url),
        'subdomain_count': subdomain_count(url),
        'has_https': has_https(url),
        'entropy': shannon_entropy(url),
        'digit_ratio': digit_ratio(url),
        'path_depth': path_depth(url),
    }
