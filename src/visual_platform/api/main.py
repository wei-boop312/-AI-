from fastapi import FastAPI
from fastapi.responses import JSONResponse
app=FastAPI(title="跨境电商 AI 视觉生产平台",version="0.1.0")
@app.get("/api/v1/health/live")
def live(): return {"status":"alive"}
@app.get("/api/v1/health/ready")
def ready():
    return JSONResponse(status_code=503,content={"status":"not_ready","reason":"native services and authenticated routes pending"})
