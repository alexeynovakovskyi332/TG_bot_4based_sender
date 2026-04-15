from core.models.models import Account
from core.services.proxy.proxy_parser import ProxyParser


class AccountFileParser:

    def __init__(self, proxy_parser: ProxyParser):
        self._pp = proxy_parser

    def parse(self, path: str):

        accounts = []

        with open(path, encoding="utf-8") as f:

            for raw in f:

                line = raw.strip()

                if not line:
                    continue

                parts = line.split(":", 3)

                if len(parts) < 3:
                    continue

                proxy_raw = parts[3].strip() if len(parts) == 4 else ""

                accounts.append(
                    Account(
                        email=parts[0].strip(),
                        password=parts[1].strip(),
                        message_text=parts[2].strip(),
                        proxy_url=self._pp.to_url(proxy_raw)
                        if proxy_raw else None,
                    )
                )

        return accounts