from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.api.payments import router as payments_router
from app.core.config import settings
from app.messaging.broker import broker
from app.services.metrics import metrics_store
from app.services.outbox_relay import OutboxRelay

outbox_relay = OutboxRelay()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await broker.start()
    outbox_relay.start()
    try:
        yield
    finally:
        await outbox_relay.stop()
        await broker.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(payments_router, prefix=settings.api_prefix)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    return metrics_store.to_prometheus()
