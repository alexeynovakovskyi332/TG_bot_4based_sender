import urllib.parse
from typing import Optional


class ProxyParser:

    IP_JSON  = "https://api.ipify.org?format=json"
    IP_PLAIN = "https://ifconfig.io/ip"

    def to_url(self, raw: str, default_scheme: str = "http") -> Optional[str]:
        if not raw:
            return None
        s = raw.strip()
        if not s:
            return None
        if "://" in s:
            return s
        parts = s.split(":")
        if len(parts) < 2:
            return None
        host, port = parts[0].strip(), parts[1].strip()
        if not host or not port.isdigit():
            return None
        if len(parts) >= 4:
            username = ":".join(parts[2:-1]).strip()
            password = parts[-1].strip()
            if not username or not password:
                return f"{default_scheme}://{host}:{port}"
            return f"{default_scheme}://{username}:{password}@{host}:{port}"
        return f"{default_scheme}://{host}:{port}"

    def to_playwright_dict(self, proxy_url: str) -> Optional[dict]:
        if not proxy_url:
            return None
        p = urllib.parse.urlparse(proxy_url)
        if not p.hostname or not p.port:
            return None
        d = {"server": f"{p.scheme or 'http'}://{p.hostname}:{p.port}"}
        if p.username:
            d["username"] = urllib.parse.unquote(p.username)
        if p.password:
            d["password"] = urllib.parse.unquote(p.password)
        return d