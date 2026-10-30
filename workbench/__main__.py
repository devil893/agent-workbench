import argparse
import asyncio
import json
import secrets
import tempfile
from pathlib import Path
from .api import create_app
from .config import Settings


def main():
    parser=argparse.ArgumentParser(description='Agent Workbench')
    parser.add_argument('command',choices=['demo','serve','token'])
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    if args.command=='token':
        print(secrets.token_urlsafe(32))
    elif args.command=='serve':
        import uvicorn
        uvicorn.run(create_app(),host='127.0.0.1',port=args.port,loop='asyncio',http='h11')
    else:
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(Settings(db=str(Path(tmp)/'demo.db')))
            agent=app.state.agent
            async def demo():
                for msg in ['remember prepare the evaluation report','list notes','/tool browser_open {"url":"https://example.com"}']:
                    result=await agent.run('synthetic-user',msg)
                    print(json.dumps({'message':msg,**result},indent=2))
            asyncio.run(demo())


if __name__=='__main__': main()
