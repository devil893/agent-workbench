"""Authenticated JSON API plus an optional signed inbound WhatsApp channel."""
import asyncio
import base64
from contextlib import asynccontextmanager, suppress
import hashlib
import hmac
import json
import uuid
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .agent import Agent
from .config import Settings
from .execution import Executor
from .storage import Store
from .tools import Catalog


class Chat(BaseModel):
    message: str = Field(min_length=1,max_length=20000)


class Decision(BaseModel):
    approve: bool


def create_app(settings=None, model=None):
    settings=settings or Settings.from_env()
    store=Store(settings.db)
    catalog=Catalog(store)
    executor=Executor(store,catalog)
    agent=Agent(settings,store,catalog,executor,model)

    async def scheduler():
        while True:
            await asyncio.to_thread(store.deliver_due)
            await asyncio.sleep(5)

    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(scheduler())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError): await task

    app=FastAPI(title='Agent Workbench',version='0.1.0',lifespan=lifespan)
    app.state.store,app.state.executor,app.state.agent=store,executor,agent

    @app.middleware('http')
    async def limit_body(request,call_next):
        # Bound bodies even when Content-Length is missing or dishonest.
        chunks=[]; size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>65536: return Response('Request too large',status_code=413)
            chunks.append(chunk)
        request._body=b''.join(chunks)
        return await call_next(request)

    def identity(authorization: str=Header(default='')):
        scheme,_,token=authorization.partition(' ')
        if scheme.lower()=='bearer':
            for expected,tenant in settings.tokens.items():
                if hmac.compare_digest(expected,token): return tenant
        raise HTTPException(401,'A configured bearer token is required')

    @app.get('/health')
    def health():
        return {'status':'ok','backend':settings.backend,'external_effects':'simulated'}

    @app.get('/tools')
    def manifest(tenant=Depends(identity)):
        return catalog.manifest()

    @app.post('/chat')
    @app.post('/webhook/test')
    async def chat(body:Chat,tenant=Depends(identity)):
        return await agent.run(tenant,body.message)

    @app.get('/approvals')
    def pending(tenant=Depends(identity)):
        return store.pending(tenant)

    @app.post('/approvals/{key}')
    async def decide(key:str,body:Decision,tenant=Depends(identity)):
        run_id=uuid.uuid4().hex
        # Serialize with agent turns for this tenant; users cannot approve a
        # draft while that tenant's model is mutating it in another turn.
        async with agent.locks.setdefault(tenant,asyncio.Lock()):
            result=executor.decide(tenant,key,body.approve,run_id)
        return {'run_id':run_id,**result}

    @app.get('/runs/{run_id}')
    def trace(run_id:str,tenant=Depends(identity)):
        events=store.events(tenant,run_id)
        if not events: raise HTTPException(404,'Run not found')
        return events

    @app.get('/inbox')
    def inbox(tenant=Depends(identity)):
        return store.list(tenant,'inbox')

    @app.post('/whatsapp')
    async def whatsapp(request:Request):
        if not settings.twilio_token or not settings.twilio_url:
            raise HTTPException(503,'WhatsApp is not configured')
        form=await request.form()
        # Reject duplicate keys so signature and parsed values are identical.
        if len(form.multi_items())!=len(form): raise HTTPException(400,'Duplicate fields')
        payload=settings.twilio_url+''.join(k+str(form[k]) for k in sorted(form))
        expected=base64.b64encode(hmac.new(settings.twilio_token.encode(),payload.encode(),hashlib.sha1).digest()).decode()
        if not hmac.compare_digest(expected,request.headers.get('x-twilio-signature','')):
            raise HTTPException(403,'Invalid signature')
        sender=str(form.get('From','')).removeprefix('whatsapp:')
        if sender not in settings.twilio_phones: raise HTTPException(403,'Sender is not enabled')
        tenant='whatsapp:'+sender
        sid=str(form.get('MessageSid',''))
        if not sid: raise HTTPException(400,'MessageSid is required')
        if not store.claim_delivery(tenant,sid):
            reply=store.delivery_reply(tenant,sid) or 'This message is already being processed.'
        elif str(form.get('NumMedia','0'))!='0':
            reply='This version supports text messages only. Voice and image input are not implemented.'
            store.complete_delivery(tenant,sid,reply)
        else:
            message=str(form.get('Body',''))[:20000]
            words=message.strip().split()
            # Approval is parsed from the actual signed human message, never
            # from model prose or retrieved documents.
            if len(words)==2 and words[0].lower() in {'approve','reject'}:
                async with agent.locks.setdefault(tenant,asyncio.Lock()):
                    reply=json.dumps(executor.decide(tenant,words[1],words[0].lower()=='approve',uuid.uuid4().hex))
            else:
                reply=(await agent.run(tenant,message))['reply']
            store.complete_delivery(tenant,sid,reply)
        parts=[reply[i:i+1400] for i in range(0,min(len(reply),8400),1400)] or ['']
        xml='<Response>'+''.join('<Message>'+escape(p)+'</Message>' for p in parts)+'</Response>'
        return Response(xml,media_type='application/xml')

    return app
