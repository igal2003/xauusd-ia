import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.engine import Engine

ROOT = Path(__file__).parent


def create_app(engine=None, interval=None):
    engine = engine or Engine(os.getenv('XAU_DB_PATH', 'data/simulation.sqlite3'),
                              spread=float(os.getenv('XAU_SPREAD', '.6')),
                              slippage=float(os.getenv('XAU_SLIPPAGE', '.1')))
    interval = interval if interval is not None else float(os.getenv('XAU_INTERVAL', '1'))
    if interval < .1:
        raise ValueError('Intervalle minimum : 0.1 seconde')

    async def worker():
        while True:
            try:
                engine.step()
            except Exception:
                logging.exception('Échec du moteur ; mise en pause')
                engine.control('pause')
            await asyncio.sleep(interval)

    @asynccontextmanager
    async def lifespan(app):
        # Un seul processus possède le moteur pour une base donnée.
        import fcntl
        lock = open(engine.path + '.lock', 'a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            raise RuntimeError('Un autre moteur utilise cette base SQLite')
        task = asyncio.create_task(worker())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            lock.close()

    app = FastAPI(title='XAUUSD IA — simulation', lifespan=lifespan)
    app.state.engine = engine

    @app.middleware('http')
    async def local_access(request: Request, call_next):
        # Aucun contrôle inter-origines pour les commandes depuis un site tiers.
        if request.method not in ('GET', 'HEAD'):
            origin = request.headers.get('origin')
            if origin and origin != str(request.base_url).rstrip('/'):
                return __import__('fastapi').responses.JSONResponse({'detail':'Origine refusée'}, status_code=403)
        return await call_next(request)

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'static/index.html')

    @app.get('/api/state')
    def state():
        return engine.snapshot()

    @app.get('/api/health')
    def health():
        engine.snapshot()
        return {'status':'ok', 'execution':'paper-only'}

    class Command(BaseModel):
        action: str
        profile: str | None = None

    @app.post('/api/control')
    def control(command: Command):
        try:
            engine.control(command.action, command.profile)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return engine.snapshot()

    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    return app


app = create_app()
