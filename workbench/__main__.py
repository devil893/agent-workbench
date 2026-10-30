import argparse
import asyncio
import json
import secrets
import os
import tempfile
from pathlib import Path
from .api import create_app
from .config import Settings


def main():
    parser=argparse.ArgumentParser(description='Agent Workbench')
    parser.add_argument('command',choices=['demo','serve','token','init'])
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    if args.command=='init':
        path=Path(os.getenv('WORKBENCH_CONFIG','data/local-config.json'))
        if path.exists():
            parser.exit(message=f'Configuration already exists at {path}. It was not overwritten.\n')
        path.parent.mkdir(parents=True,exist_ok=True)
        token=secrets.token_urlsafe(32)
        with path.open('x',encoding='utf-8') as stream:
            json.dump({'tokens':{token:'local-user'}},stream)
        print(f'Local account created. Keep this access token private:\n{token}\nRun python -m workbench serve, then open http://127.0.0.1:8000 and enter the token.')
    elif args.command=='token':
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
