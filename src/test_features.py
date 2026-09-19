from features import extract_features

test_urls = [
    "http://google.com",
    "https://www.paypal.com/signin",
    "http://192.168.1.1/login/verify",
    "https://secure-paypal-login.verify-account.tk/update",
    "http://a.b.c.d.example.com/path/to/page?query=1",
]

for url in test_urls:
    print(url)
    print(extract_features(url))
    print()
