from core.worker.account_worker import AccountWorker

from core.services.proxy.proxy_parser import ProxyParser
from core.services.browser.browser_factory import PlaywrightBrowserFactory
from core.services.cloudflare.cloudflare_waiter import CloudflareWaiter
from core.services.session.session_manager import SessionManager
from core.services.messaging.messagе_sender import MessageSender


def build_worker() -> AccountWorker:

    proxy_parser = ProxyParser()

    cf_waiter = CloudflareWaiter()

    browser_factory = PlaywrightBrowserFactory(proxy_parser)

    session_manager = SessionManager(cf_waiter)

    message_sender = MessageSender()

    return AccountWorker(
        browser_factory,
        session_manager,
        message_sender,
        cf_waiter
    )