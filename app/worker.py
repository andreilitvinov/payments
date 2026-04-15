import asyncio

from app.messaging.broker import broker
from app.messaging.consumer import process_payment  # noqa: F401


async def run() -> None:
    await broker.start()
    try:
        await asyncio.Event().wait()
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(run())
