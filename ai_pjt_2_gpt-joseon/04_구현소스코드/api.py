"""로컬 Vue 화면용 API. 키와 내부 오류는 응답에 포함하지 않는다."""
import os
import time
import uuid
import threading
import traceback
import json
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Literal
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from history_rag.settings import settings, ROOT
from history_rag.timeline import load_periods
from history_rag.storage import Store
from history_rag.sources import SourceClient
from history_rag.llm import model, embeddings
from history_rag.index import Index
from history_rag.pipeline import build_graph
from history_rag.explore import explore_periods
from history_rag.research import collection_status

app = FastAPI(title='GPT-Joseon 로컬 API')
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'] + [host.strip() for host in os.getenv('HISTORY_PUBLIC_HOSTS', '').split(',') if host.strip()])
pool = ThreadPoolExecutor(max_workers=1)
jobs, lock = {}, threading.Lock()


def local_client(request: Request):
    origin = request.headers.get('origin')
    if request.headers.get('x-history-client') != 'annals-local' or (origin and origin != str(request.base_url).rstrip('/')):
        raise HTTPException(403, '이 화면에서 다시 요청해 보렴.')


class Turn(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=12000)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    period_id: str | None = None
    history: list[Turn] = Field(default_factory=list, max_length=20)
    search_mode: Literal['similarity', 'mmr'] | None = None
    top_k: int | None = Field(default=None, ge=1, le=15)
    refresh: bool = False


@lru_cache(maxsize=2)
def embedding_client(name):
    return embeddings({**settings(), 'embedding_model': name})


def context():
    config = settings()
    if not os.getenv('GMS_KEY'):
        raise RuntimeError('GMS 설정 필요')
    store = Store()
    return config, store, Index(embedding_client(config['embedding_model']), config)


@app.get('/api/health')
def health():
    settings()
    return {'status': 'ok', 'configured': bool(os.getenv('GMS_KEY'))}


@app.get('/api/periods')
def periods():
    return [{k: p.get(k) for k in ['id', 'title', 'king', 'year', 'url']} for p in load_periods()]


@app.get('/api/lab')
def lab():
    config = settings()
    result = {'settings': {k: config[k] for k in ['search_mode', 'top_k', 'chunk_size', 'chunk_overlap', 'fetch_k', 'mmr_lambda']},
              'source_contact_configured': bool(os.getenv('HISTORY_SOURCE_CONTACT')),
              'periods': len(load_periods())}
    if os.getenv('GMS_KEY'):
        try:
            _, store, index = context()
            result.update({'counts': index.counts(), 'documents': store.counts()})
        except Exception:
            result['notice'] = '색인을 열지 못했구나. 데이터 준비 상태를 확인해 보렴.'
    return result


def run_job(job_id, payload, mode):
    def progress(message):
        with lock:
            jobs[job_id]['progress'] = message
    try:
        config, store, index = context()
        if payload.search_mode:
            config['search_mode'] = payload.search_mode
        if payload.top_k:
            config['top_k'] = payload.top_k
        index.config.update(config)
        source = SourceClient(store, config)
        source.refresh = payload.refresh
        if payload.refresh:
            base = source.search
            source.search = lambda *a, **kw: base(*a, **{**kw, 'refresh': True})
        if mode == 'explore':
            progress('조건에 맞는 사건과 연도를 찾는 중이란다…')
            result = {'matches': explore_periods(payload.question, load_periods(), index, source, model(config))}
        else:
            item = next((p for p in load_periods() if p['id'] == payload.period_id), None)
            output = build_graph(store, source, index, model(config), config, progress).invoke({
                'item': item, 'question': payload.question,
                'history': [t.model_dump() for t in payload.history]})
            result = {'answer': output['answer'], 'sources': [
                {'text': d.page_content, 'metadata': d.metadata} for d in output['evidence']],
                'research': output['trace'], 'status_label': collection_status(output['answer'])}
        with lock:
            jobs[job_id].update(status='complete', result=result, elapsed=round(time.monotonic() - jobs[job_id]['started'], 1))
    except Exception as exc:
        # 진단은 로컬 ignored data/에만 저장한다. 키·프롬프트·오류 메시지는 남기지 않는다.
        try:
            (ROOT / 'data').mkdir(exist_ok=True)
            (ROOT / 'data' / 'last_job_error.json').write_text(json.dumps({
                'type': type(exc).__name__, 'frames': [{'file': f.filename, 'line': f.lineno, 'function': f.name}
                    for f in traceback.extract_tb(exc.__traceback__)]}, ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass
        with lock:
            jobs[job_id].update(status='failed', error='설명을 마치지 못했구나. 설정과 연결 상태를 확인한 뒤 다시 시도해 보렴.')


def submit(payload, mode):
    if not payload.question.strip():
        raise HTTPException(422, '궁금한 것을 입력해 보렴.')
    if payload.period_id and payload.period_id not in {p['id'] for p in load_periods()}:
        raise HTTPException(422, '목록에서 시기를 선택해 보렴.')
    settings()
    if not os.getenv('GMS_KEY'):
        raise HTTPException(503, 'GMS 키 설정이 필요하단다. 질문은 그대로 남겨두었어.')
    with lock:
        for old in [k for k, j in jobs.items() if j['status'] != 'running' and time.monotonic() - j['started'] > 3600]:
            del jobs[old]
        if any(j['status'] == 'running' for j in jobs.values()):
            raise HTTPException(429, '다른 기록을 살피는 중이란다. 잠시 뒤 다시 시도해 보렴.')
        job_id = uuid.uuid4().hex
        jobs[job_id] = {'status': 'running', 'progress': '훈장님이 서재에서 기록을 찾는 중이란다…', 'started': time.monotonic()}
    pool.submit(run_job, job_id, payload, mode)
    return {'job_id': job_id}


@app.post('/api/questions', dependencies=[Depends(local_client)])
def ask(payload: Question):
    return submit(payload, 'question')


@app.post('/api/explore', dependencies=[Depends(local_client)])
def explore(payload: Question):
    return submit(payload, 'explore')


@app.get('/api/jobs/{job_id}')
def job(job_id: str):
    with lock:
        if job_id not in jobs:
            raise HTTPException(404, '요청 기록이 만료되었구나.')
        return {k: v for k, v in jobs[job_id].items() if k != 'started'}


@app.get('/')
def home():
    return FileResponse(ROOT / 'frontend' / 'index.html')


app.mount('/assets', StaticFiles(directory=ROOT / 'frontend'), name='assets')


class TranslationRequest(BaseModel):
    article_id: str = Field(min_length=1, max_length=400)
    text: str = Field(min_length=6, max_length=6000)


translation_slots = threading.BoundedSemaphore(2)


@app.post('/api/translations', dependencies=[Depends(local_client)])
def translate(payload: TranslationRequest):
    from history_rag.translation import translate_source
    config = settings()
    if not config['allow_llm_transfer']:
        raise HTTPException(403, '자료 번역 설정을 확인해 보렴.')
    if not translation_slots.acquire(blocking=False):
        raise HTTPException(429, '다른 본문을 번역 중이란다. 잠시 뒤 다시 눌러보렴.')
    store = Store()
    try:
        return translate_source(store, model({**config, 'timeout': 120, 'retries': 0}), payload.article_id, payload.text)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(502, '번역을 마치지 못했구나. 잠시 뒤 다시 시도해 보렴.')
    finally:
        store.db.close()
        translation_slots.release()
