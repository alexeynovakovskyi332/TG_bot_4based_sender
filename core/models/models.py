from dataclasses import dataclass
from typing import Optional

@dataclass
class Account:
    email: str
    password: str
    message_text: str
    proxy_url: Optional[str] = None


@dataclass
class ProxyCheckResult:
    ok: bool
    info: str          # IP если ok, иначе текст ошибки
    email: str
    proxy_url: str


@dataclass
class SendResult:
    email: str
    success_count: int
    errors: list[str]