import json
import os
import re
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from .settings import BASE_URL


def model(config):
    key = os.getenv('GMS_KEY')
    if not key:
        raise RuntimeError('GMS_KEY가 없습니다. .env 설정을 확인하세요.')
    return ChatOpenAI(model=config['model'], api_key=key, base_url=BASE_URL,
                      timeout=config['timeout'], max_retries=config['retries'])


def embeddings(config):
    if not os.getenv('GMS_KEY'):
        raise RuntimeError('GMS_KEY가 없습니다.')
    return OpenAIEmbeddings(model=config['embedding_model'], api_key=os.environ['GMS_KEY'],
                            base_url=BASE_URL, check_embedding_ctx_length=False,
                            request_timeout=config['timeout'], max_retries=config['retries'])


def ask_json(llm, system, payload):
    response = llm.invoke([{'role': 'system', 'content': system},
                           {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}])
    content = response.content
    if not isinstance(content, str):
        content = ''.join(p.get('text', '') for p in content if isinstance(p, dict))
    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip())
    return json.loads(content)
