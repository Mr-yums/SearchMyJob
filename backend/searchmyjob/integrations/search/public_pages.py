"""Bounded public HTTPS reader; connects only to a validated, pinned public IP."""

import http.client
import ipaddress
import socket
import ssl
import time
import zlib
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


def public_target(url):
    u = urlsplit(url)
    if (
        u.scheme != "https"
        or not u.hostname
        or u.username
        or u.password
        or u.port not in (None, 443)
    ):
        raise ValueError("Une URL HTTPS publique sans identifiants est requise.")
    host = u.hostname.encode("idna").decode("ascii")
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Les adresses locales, privées et réservées ne sont pas accessibles.")
    return host, addresses[0][4][0], u.path or "/", u.query


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip):
        super().__init__(host, 443, timeout=15, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        sock = socket.create_connection((self.ip, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class PageText(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.parts = []
        self.links = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if self.hidden:
            return
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith("mailto:"):
                self.parts.append(href[7:].split("?")[0])
            elif href and len(self.links) < 60:
                target = urljoin(self.url, href)
                if target.startswith("https://") and target not in self.links:
                    self.links.append(target)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def read_public_page(url):
    deadline = time.monotonic() + 45
    for _ in range(4):
        host, ip, path, query = public_target(url)
        connection = PinnedHTTPS(host, ip)
        try:
            connection.request(
                "GET",
                path + ("?" + query if query else ""),
                headers={
                    "User-Agent": "SearchMyJob/1.0 (public page reader)",
                    "Accept": "text/html,text/plain",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Redirection sans destination.")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"Page inaccessible (HTTP {response.status}).")
            content_type = response.getheader("Content-Type", "").lower()
            if not any(
                t in content_type for t in ("text/html", "text/plain", "application/xhtml+xml")
            ):
                raise ValueError("Seules les pages HTML et texte sont prises en charge.")
            encoding = response.getheader("Content-Encoding", "identity").lower()
            if encoding not in ("", "identity", "gzip"):
                raise ValueError("Encodage de page non pris en charge.")
            chunks = []
            size = 0
            while size <= 1_000_000:
                if time.monotonic() > deadline:
                    raise ValueError("Délai de lecture dépassé.")
                chunk = response.read1(min(65536, 1_000_001 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            raw = b"".join(chunks)
            if len(raw) > 1_000_000:
                raise ValueError("Page trop volumineuse (1 Mo maximum).")
            if encoding == "gzip":
                raw = decode_gzip(raw)
            text = raw.decode("utf-8", errors="replace")
            parser = PageText(url)
            if "html" in content_type:
                parser.feed(text)
                text = "\n".join(parser.parts)
            if not text.strip():
                raise ValueError("Aucun texte lisible sur cette page.")
            return {
                "url": url,
                "text": text[:60000],
                "links": parser.links,
                "truncated": len(text) > 60000,
            }
        finally:
            connection.close()
    raise ValueError("Trop de redirections ; lecture arrêtée.")


def decode_gzip(raw):
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        text = decoder.decompress(raw, 1_000_001)
    except zlib.error:
        raise ValueError("Page compressée illisible.") from None
    if len(text) > 1_000_000 or decoder.unconsumed_tail:
        raise ValueError("Page décompressée trop volumineuse (1 Mo maximum).")
    if not decoder.eof or decoder.unused_data:
        raise ValueError("Flux compressé incomplet ou multiple.")
    return text
