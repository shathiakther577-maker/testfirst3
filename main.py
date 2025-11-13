from fastapi import FastAPI

from settings import FastApiSettings
from root_router import root_router

prefix = FastApiSettings.ROOT_PREFIX
app = FastAPI(
    title=FastApiSettings.TITLE,
    description=FastApiSettings.DESCRIPTION,
    version=FastApiSettings.VERSION,

    openapi_url=f"{prefix}/openapi.json",
    docs_url=f"{prefix}/docs",
    redoc_url=f"{prefix}/redoc"
)

app.include_router(root_router)
