import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/"


def settings():
    load_dotenv(ROOT / '.env', override=False)
    external = os.getenv('GMS_ENV_FILE')
    if external:
        load_dotenv(external, override=False)
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    config['model'] = os.getenv('GMS_MODEL', config['model'])
    config['embedding_model'] = os.getenv('GMS_EMBEDDING_MODEL', config['embedding_model'])
    if not 0 <= config['chunk_overlap'] < config['chunk_size']:
        raise ValueError('청크 중복 길이는 청크 크기보다 작아야 합니다.')
    return config
