from contextlib import asynccontextmanager
from uuid import uuid4
import os
import asyncio
import asyncpg
from fastapi import FastAPI,Request,HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from visual_platform.core.settings import Settings
from visual_platform.db.pool import open_pool
from visual_platform.storage.s3 import S3Storage
from visual_platform.services.readiness import Readiness
from visual_platform.core.lifecycle import clear_api_shutdown_marker,record_api_shutdown
from visual_platform.services.telemetry import RequestTelemetry
from visual_platform.api import auth,products,credits,quotes,tasks,rules,assets,reviews


def create_app(settings: Settings | None=None):
    @asynccontextmanager
    async def lifespan(app):
        clear_api_shutdown_marker()
        started=False
        configured=settings or (Settings.from_env() if os.environ.get("API_DATABASE_URL") else None)
        app.state.settings=configured
        app.state.storage=None
        app.state.api_pool=None
        app.state.auth_pool=None
        app.state.readiness=None
        app.state.decode_capacity=asyncio.Semaphore(2)
        try:
            app.state.storage=S3Storage(configured) if configured and configured.s3_endpoint else None
            if configured:
                app.state.api_pool=await open_pool(configured.api_database_url,"app_api")
                app.state.auth_pool=await open_pool(configured.auth_database_url,"app_auth")
            app.state.readiness=Readiness(app.state.api_pool,app.state.auth_pool,app.state.storage)
            started=True
            yield
        finally:
            try:
                if app.state.readiness: await app.state.readiness.close()
            finally:
                try:
                    if app.state.api_pool: await app.state.api_pool.close()
                finally:
                    try:
                        if app.state.auth_pool: await app.state.auth_pool.close()
                    finally:
                        if app.state.storage: app.state.storage.close()
            if started: record_api_shutdown()

    app=FastAPI(title="跨境电商 AI 视觉生产平台",version="0.1.0",lifespan=lifespan)
    def error(request,status,code):
        return JSONResponse(status_code=status,content={"error":{"code":code,"message":code,"request_id":getattr(request.state,"request_id",str(uuid4())),"retryable":status==503}})

    @app.middleware("http")
    async def boundary(request: Request,call_next):
        request.state.request_id=str(uuid4())
        if request.url.path.startswith("/api/v1/") and "/health/" not in request.url.path:
            if not getattr(app.state,"settings",None): return error(request,503,"service_not_configured")
            if request.method not in ("GET","HEAD","OPTIONS"):
                try:
                    if request.url.path=="/api/v1/auth/login": auth.origin_check(request)
                    else: auth.csrf_check(request)
                except HTTPException as exc: return error(request,exc.status_code,exc.detail)
        try: response=await call_next(request)
        except (asyncpg.PostgresError,TimeoutError,ConnectionError):
            return error(request,503,"dependency_unavailable")
        response.headers["X-Request-ID"]=request.state.request_id
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Cache-Control"]="no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request,exc): return error(request,exc.status_code,str(exc.detail))
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc): return error(request,422,"invalid_request")
    @app.get("/api/v1/health/live")
    def live(): return {"status":"alive"}
    @app.get("/api/v1/health/ready")
    async def ready():
        result=await app.state.readiness.check()
        return JSONResponse(status_code=200 if result["status"]=="ready" else 503,content=result)
    app.include_router(auth.router); app.include_router(products.router); app.include_router(credits.router); app.include_router(quotes.router); app.include_router(tasks.router); app.include_router(rules.router); app.include_router(assets.router); app.include_router(reviews.router)
    app.add_middleware(RequestTelemetry)
    return app

app=create_app()
