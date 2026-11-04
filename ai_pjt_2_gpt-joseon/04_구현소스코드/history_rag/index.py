import json
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .settings import ROOT
from .storage import digest


def metadata_text(a):
    keys = ('title', 'collection', 'king', 'year', 'reign_label', 'date_original', 'era_original', 'category', 'snippet', 'id')
    return '\n'.join(f'{k}: {a.get(k, "")}' for k in keys)


def common_metadata(a, kind):
    return {'article_id': a['id'], 'title': a['title'], 'url': a['url'],
            'collection': a.get('collection', ''), 'date': a.get('date_original', ''),
            'source_kind': kind, 'service': a.get('service', ''),
            'rights_status': a.get('rights_status', 'unverified'), 'item_kind': a.get('item_kind', 'article'),
            'license': a.get('license', ''), 'license_name': a.get('license_name', 'CC BY-SA 4.0' if a.get('license') else ''),
            'attribution': a.get('attribution', a.get('service', '') + ' 문서 기여자'), 'revision_url': a.get('revision_url', ''),
            'is_primary': bool(a.get('is_primary', a.get('source_kind') not in ('웹 해설', '합성 테스트')))}


class Index:
    def __init__(self, embedding, config, path=None):
        self.config = config
        path = path or ROOT / 'data' / 'chroma'
        path.mkdir(parents=True, exist_ok=True)
        signature = digest(config['embedding_model'])[:10]
        self.meta = Chroma(collection_name='royal_year_meta_v2_' + signature, embedding_function=embedding, persist_directory=str(path))
        self.body = Chroma(collection_name='external_docs_' + signature, embedding_function=embedding, persist_directory=str(path))
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=config['chunk_size'], chunk_overlap=config['chunk_overlap'], separators=['\n\n', '\n', '。', '. ', ' ', ''])

    def counts(self):
        return {'metadata_chunks': self.meta._collection.count(), 'body_chunks': self.body._collection.count()}

    def index_metadata(self, articles):
        if not self.config['allow_llm_transfer']:
            raise RuntimeError('자료 외부 전송 이용 조건을 확인하세요.')
        pending = []
        for a in articles:
            if a.get('rights_status') != 'permitted' or not a.get('rights_basis'):
                continue
            text = metadata_text(a)
            old = self.meta.get(ids=[a['id']], include=['metadatas'])
            h = digest(text)
            if old['ids'] and old['metadatas'][0].get('content_hash') == h:
                continue
            pending.append(Document(page_content=text, metadata={**common_metadata(a, '항목 메타데이터'), 'content_hash': h}, id=a['id']))
        for start in range(0, len(pending), 32):
            batch = pending[start:start + 32]
            self.meta.add_documents(batch, ids=[d.id for d in batch])
        return len(pending)

    def index_body(self, item_id, article):
        if not article.get('text') or article.get('validation') != 'valid':
            return 0
        if not self.config['allow_llm_transfer']:
            raise RuntimeError('자료 외부 전송 이용 조건을 확인하세요.')
        if article.get('rights_status') != 'permitted' or not article.get('rights_basis'):
            raise RuntimeError('이 문서의 외부 모델 전송 이용 근거가 없습니다.')
        relation = digest(item_id + ':' + article['id'])
        signature = digest(json.dumps([article['body_hash'], self.config['chunk_size'], self.config['chunk_overlap']]))
        old = self.body.get(where={'relation': relation}, include=['metadatas'])
        if old['ids'] and all(m.get('index_signature') == signature for m in old['metadatas']):
            return 0
        chunks = self.splitter.split_text(article['text'])
        docs = [Document(page_content=t, metadata={**common_metadata(article, article.get('source_kind', '기존 번역')),
                'item_id': item_id, 'relation': relation, 'index_signature': signature, 'chunk': i,
                'chunk_hash': digest(t)}) for i, t in enumerate(chunks)]
        ids = [f'{relation}:{signature[:12]}:{i}' for i in range(len(docs))]
        if docs:
            self.body.add_documents(docs, ids=ids)
            stale = [i for i in old['ids'] if i not in ids]
            if stale:
                self.body.delete(ids=stale)
        return len(docs)

    def retrieve(self, item, question, scoped=True):
        result = [Document(page_content=metadata_text(item), metadata=common_metadata(item, '항목 메타데이터'))] if item else []
        if self.meta._collection.count():
            result += self.meta.similarity_search(question, k=min(3, self.meta._collection.count()))
        if self.body._collection.count():
            # 이미 확보한 해당 시기의 사료도 별도로 검색한다. 누적된 한국어 웹
            # 해설만 상위에 몰려 한문 사료가 근거에서 사라지는 일을 막는다.
            primary_filter = {'is_primary': True}
            if item and item.get('item_kind') == 'royal_year':
                primary_filter = {'$and': [{'is_primary': True}, {'item_id': item['id']}]}
            result += self.body.similarity_search(question, k=min(3, self.config['top_k']), filter=primary_filter)
            kwargs = {'k': self.config['top_k']}
            if item and scoped:
                kwargs['filter'] = {'item_id': item['id']}
            if self.config['search_mode'] == 'mmr':
                result += self.body.max_marginal_relevance_search(question, fetch_k=self.config['fetch_k'], lambda_mult=self.config['mmr_lambda'], **kwargs)
            else:
                result += self.body.similarity_search(question, **kwargs)
            # 선택 기사의 전문은 검색 순위와 관계없이 최소 한 청크 포함한다.
            own = self.body.get(where={'$and': [{'item_id': item['id']}, {'article_id': item['id']}]}, include=['documents', 'metadatas']) if item and item.get('item_kind') != 'royal_year' else {'ids': []}
            if own['ids']:
                result.insert(1, Document(page_content=own['documents'][0], metadata=own['metadatas'][0]))
        seen, unique = set(), []
        for doc in result:
            key = (doc.metadata['article_id'], doc.metadata['source_kind'], digest(doc.page_content))
            if key not in seen:
                unique.append(doc)
                seen.add(key)
        return unique
