import asyncio
import logging
import threading

from playwright.async_api import async_playwright

from core.models.models import Account, SendResult

log = logging.getLogger("4based_bot")


class SpamOrchestrator:

    def __init__(self, worker_factory_fn):
        self._make_worker = worker_factory_fn

    async def run(
        self,
        accounts,
        profiles,
        notifier,
        stop_async,
        stop_thread
    ):

        tasks = []

        async with async_playwright() as playwright:

            for account in accounts:

                worker = self._make_worker()

                t = asyncio.create_task(
                    worker.run(
                        playwright,
                        account,
                        profiles,
                        stop_thread
                    )
                )

                tasks.append(t)

            total_success = 0
            all_errors = []

            for done in asyncio.as_completed(tasks):

                result = await done

                total_success += result.success_count

                all_errors.extend(result.errors)

                await notifier.worker_done(result)

        await notifier.final(
            stop_async.is_set(),
            total_success,
            len(all_errors)
        )