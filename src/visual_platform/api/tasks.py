import json
from uuid import UUID,uuid4
import asyncpg
from fastapi import APIRouter,Depends,Request,Response,Header,HTTPException,Query
from visual_platform.api.auth import current_user
from visual_platform.api.products import cursor_decode,cursor_encode
from visual_platform.db.transactions import tenant_transaction
from visual_platform.domain.schemas import QuoteRequest,TaskRequest,canonical_hash
from visual_platform.services.quotes import db_conflict,hash_data
router=APIRouter(prefix="/api/v1/tasks",tags=["tasks"])

COLUMNS="id,status,phase,revision,credits_status,reserved_credits,created_at,updated_at,completed_at,error_code"
def serialize(row,replay=False):
    data=dict(row)
    data['credits']={"status":data.pop('credits_status'),"amount":data.pop('reserved_credits')}
    data['result']=None; data['compliance']=None; data['idempotent_replay']=replay
    return data

@router.post("",status_code=201)
async def submit(body: TaskRequest,request: Request,response: Response,idempotency_key: str=Header(min_length=1,max_length=200),user=Depends(current_user)):
    business=QuoteRequest.model_validate(body.model_dump(exclude={"quote_id"}))
    input_hash=canonical_hash(business)
    request_hash=hash_data({"operation":"generate","quote_id":str(body.quote_id),"input":business.model_dump(mode="json",exclude_none=True)})
    proposed=uuid4()
    async with tenant_transaction(request.app.state.api_pool,user["id"]) as c:
        try:
            identity=await c.fetchval("SELECT app.submit_quoted_task($1,$2,$3,$4,$5)",proposed,body.quote_id,idempotency_key,request_hash,input_hash)
        except asyncpg.RaiseError as exc: db_conflict(exc)
        row=await c.fetchrow("SELECT "+COLUMNS+" FROM app.generation_tasks WHERE id=$1",identity)
    replay=identity!=proposed
    if replay: response.status_code=200
    return {**serialize(row,replay),"request_id":request.state.request_id}

@router.get("")
async def listing(request: Request,limit: int=Query(20,ge=1,le=100),cursor: str | None=None,user=Depends(current_user)):
    pos=cursor_decode(cursor) if cursor else None
    async with tenant_transaction(request.app.state.api_pool,user["id"]) as c:
        rows=await c.fetch("SELECT "+COLUMNS+" FROM app.generation_tasks WHERE ($1::timestamptz IS NULL OR (created_at,id)<($1,$2::uuid)) ORDER BY created_at DESC,id DESC LIMIT $3",pos[0] if pos else None,pos[1] if pos else None,limit+1)
    return {"items":[serialize(x) for x in rows[:limit]],"next_cursor":cursor_encode(rows[limit-1]) if len(rows)>limit else None}

@router.get("/{task_id}")
async def detail(task_id: UUID,request: Request,user=Depends(current_user)):
    async with tenant_transaction(request.app.state.api_pool,user["id"]) as c:
        row=await c.fetchrow("SELECT "+COLUMNS+" FROM app.generation_tasks WHERE id=$1",task_id)
    if not row: raise HTTPException(404,"not_found")
    return serialize(row)

@router.post("/{task_id}/cancel")
async def cancel(task_id: UUID,request: Request,user=Depends(current_user)):
    async with tenant_transaction(request.app.state.api_pool,user["id"]) as c:
        try: await c.execute("SELECT app.cancel_task($1)",task_id)
        except asyncpg.RaiseError as exc: db_conflict(exc)
        row=await c.fetchrow("SELECT "+COLUMNS+" FROM app.generation_tasks WHERE id=$1",task_id)
    return serialize(row)
