from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown: close pools etc. if needed


app = FastAPI(
    title="Payment Service API",
    description="Orders and payments with cash/acquiring and bank sync.",
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok"}
