"""step7 골격의 채팅·진행 상태·인용 구조를 자유 질문 서비스로 확장."""
import os
import time
from pathlib import Path
import streamlit as st
from history_rag.settings import settings
from history_rag.storage import Store
from history_rag.sources import SourceClient
from history_rag.llm import model, embeddings
from history_rag.index import Index
from history_rag.pipeline import build_graph
from history_rag.timeline import load_periods, match_periods
from history_rag.research import collection_status
from history_rag.explore import explore_periods, exact_period_condition

st.set_page_config(page_title="GPT-Joseon", page_icon="📜", layout="wide")
st.html("<style>" + (Path(__file__).parent / "resources" / "annals.css").read_text(encoding="utf-8") + "</style>")
st.title("📜 GPT-Joseon")
st.caption("궁금한 조선의 역사를 물어보렴. 기록을 살펴 알기 쉽게 가르쳐주마.")
config = settings()
store = Store()
periods = load_periods()
by_id = {p["id"]: p for p in periods}
counts = store.counts()


@st.cache_resource
def get_embedding(embedding_model):
    current = settings()
    current["embedding_model"] = embedding_model
    return embeddings(current)


def choose_period(period_id):
    st.session_state.period = period_id
    st.session_state.king_filter = by_id[period_id]["king"]


def render_cites(entries):
    for e in entries:
        st.caption(f'“{e["quote"]}” [근거 {e["number"]}]')


def cite_numbers(entries):
    return " ".join(f"[근거 {n}]" for n in sorted({e["number"] for e in entries}))


def queue_question(question):
    st.session_state.pending_question = question


def render_answer(answer, sources, research, message_key="latest", show_suggestions=True):
    st.caption("훈장님의 이야기 · " + answer.get("evidence_scope", "확보한 근거 기준"))
    fields = [answer.get(k, {}) for k in ["response", "interpretation", "aside", "ai_translation"]]
    response, interpretation, aside, translation = fields
    if response.get("text"):
        st.markdown(response["text"] + " " + cite_numbers(response.get("evidence", [])))
    else:
        st.write("지금 확보한 기록만으로는 답을 확정하기 어렵소. 확인한 범위는 아래에 남겨두었소.")
    if interpretation.get("text"):
        st.markdown(interpretation["text"] + " " + cite_numbers(interpretation.get("evidence", [])))
    if aside.get("text"):
        st.markdown("**잠깐, 이 대목을 보거라**")
        st.markdown(aside["text"] + " " + cite_numbers(aside.get("evidence", [])))
    used = {e["number"] for field in fields for e in field.get("evidence", [])}
    used.update(e["number"] for c in answer.get("claims", []) for e in c.get("evidence", []))
    # 그날의 기록은 답변에 실제 인용한 사료만 보여준다. 검색 후보는 포함하지 않는다.
    displayed = {e['number'] for field in fields for e in field.get('evidence', [])}
    primary = [(n, sources[n-1]) for n in sorted(displayed) if 1 <= n <= len(sources)
               and sources[n-1]["metadata"].get("is_primary", False)]
    if primary:
        n, record = primary[0]
        m = record["metadata"]
        st.markdown("**그날의 기록**")
        st.caption(f'{m.get("date", "날짜 미상")} · {m.get("collection") or m["title"]} · 사료 표기 기준, 양력 환산 안 함')
        quotes = [e["quote"] for field in [translation, response] for e in field.get("evidence", []) if e["number"] == n]
        if quotes:
            st.markdown("> " + quotes[0])
        if translation.get("text") and any(e["number"] == n for e in translation.get("evidence", [])):
            st.write(translation["text"])
            st.caption("AI 발췌 번역이란다. 기존 국역과 구분하며 공식 판본 대조는 아직 마치지 않았어.")
        st.markdown(f'[기록 원출처]({m["url"]}) · [근거 {n}]')
    with st.expander(f"기록 살펴보기 · 인용 {len(used)}개"):
        citations, originals, checks = st.tabs(["인용과 출처", "원문과 번역", "확인 범위"])
        with citations:
            if not used:
                st.info("아직 인용할 자료를 찾지 못했구나.")
            for n in sorted(used):
                if not 1 <= n <= len(sources):
                    continue
                src = sources[n-1]
                m = src["metadata"]
                st.markdown(f'**[근거 {n}] {m["title"]}**')
                st.caption(f'{m.get("date", "")} · {m["source_kind"]}')
                quotes = {e["quote"] for field in fields for e in field.get("evidence", []) if e["number"] == n}
                for quote in quotes:
                    st.markdown("> " + quote)
                st.markdown(f'[원출처 열기]({m["url"]})')
                if m.get("license"):
                    st.markdown(f'[{m.get("license_name") or "CC BY-SA 4.0"}]({m["license"]}) · {m.get("attribution") or m.get("service", "자료")} · 번역/요약 등 변경 포함')
                    if m.get("revision_url"):
                        st.markdown(f'[사용 판본과 기여 이력]({m["revision_url"]})')
        with originals:
            # 저장된 대화를 다시 열어도 인용한 본문을 확인할 수 있다.
            for n in sorted(used):
                if 1 <= n <= len(sources):
                    src = sources[n-1]
                    st.markdown("**" + src["metadata"]["title"] + "**")
                    st.write(src["text"])
            for doc in research.get("bodies", []):
                if doc.get("text_original") or doc.get("text_translation"):
                    st.markdown("**" + doc["title"] + "**")
                    st.write(doc.get("text_original") or "한문 원문 미확보")
                    st.write(doc.get("text_translation") or "기존 국역 미확보")
        with checks:
            for claim in answer.get("claims", []):
                st.caption("검토할 주장 · 확정 답변과 구분")
                st.markdown("**“" + claim.get("claim", "") + "”**")
                st.write(claim.get("verdict", "현재 근거 부족") + " · " + claim.get("explanation", ""))
                render_cites(claim.get("evidence", []))
            for text in answer.get("unknowns", []):
                st.write("• " + text)
            if research.get("records"):
                st.caption("아래는 검색 후보로, 답변에 인용한 근거와는 다르단다.")
                for record in research["records"]:
                    st.markdown(f'[{record["title"]}]({record["url"]})')
    if show_suggestions and answer.get("follow_up_questions"):
        st.caption("이 기록에서 이야기를 이어가겠소?")
        cols = st.columns(min(2, len(answer["follow_up_questions"])))
        for i, suggested in enumerate(answer["follow_up_questions"][:2]):
            cols[i].button(suggested, key=f"follow_{message_key}_{i}", on_click=queue_question, args=(suggested,), type="tertiary")


index = None
if os.getenv("GMS_KEY"):
    try:
        index = Index(get_embedding(config["embedding_model"]), config)
    except Exception:
        st.warning("저장된 검색 색인을 열지 못했습니다. 설치 상태와 데이터 폴더를 확인하세요.")

with st.sidebar:
    st.header("왕·연도로 둘러보기")
    st.caption("선택은 자유입니다. 고르지 않아도 바로 질문할 수 있습니다.")
    kings = list(dict.fromkeys(p["king"] for p in periods))
    king = st.selectbox("왕", kings, index=None, placeholder="전체 왕대", key="king_filter")
    options = [p["id"] for p in periods if not king or p["king"] == king]
    if st.session_state.get("period") not in options:
        st.session_state.period = None
    period_id = st.selectbox("재위 연도", options, index=None, key="period", placeholder="전체 시기에서 질문", format_func=lambda i: f'{by_id[i]["title"]} ({by_id[i]["year"]})')
    search_condition = st.text_input("사건이나 시기로 찾기", placeholder="임진왜란이 시작된 시기 또는 선조 25년")
    if st.button("연도 탐색"):
        try:
            if exact_period_condition(search_condition, periods):
                found = [{"period": p, "reason": "입력한 왕·연도와 일치", "url": p["url"]} for p in exact_period_condition(search_condition, periods)[:20]]
            elif index and search_condition.strip():
                with st.spinner("조건에 맞는 기록을 살피는 중이란다…"):
                    found = explore_periods(search_condition, periods, index, SourceClient(store, config), model(config))
            else:
                found = []
            st.session_state.period_results = [r["period"]["id"] for r in found]
            st.session_state.period_reasons = {r["period"]["id"]: r for r in found}
        except Exception:
            st.warning("조건 탐색을 마치지 못했구나. 입력은 남겨두었으니 다시 시도해 보렴.")
    if "period_results" in st.session_state:
        found = st.session_state.period_results
        if not found:
            st.caption("해당 왕·연도 항목을 찾지 못했습니다.")
        for pid in found:
            st.button(f'{by_id[pid]["title"]} ({by_id[pid]["year"]})', key="found_" + pid, on_click=choose_period, args=(pid,))
            reason = st.session_state.get("period_reasons", {}).get(pid, {})
            st.caption(reason.get("reason", ""))
            if reason.get("quote"):
                st.caption(reason["quote"])
                st.markdown(f'[탐색 근거]({reason["url"]})')
    st.divider()
    refresh = False
    laboratory = st.toggle("실험실 열기", value=False)
    if not os.getenv("GMS_KEY"):
        st.warning("GMS_KEY가 없습니다. .env 또는 GMS_ENV_FILE을 확인하세요.")
    if index and not index.counts()["metadata_chunks"]:
        st.info("연도 색인이 없습니다. python -m scripts.index_timeline 으로 준비할 수 있습니다.")
    if laboratory:
        st.subheader("검색 실험실")
        st.caption("검색 설정과 저장 현황 · 이 세션에만 적용된단다.")
        st.caption(f'연도 항목 {len(periods)}개 · 확보 본문 {counts["bodies"]}건')
        if index:
            st.json(index.counts())
        config["search_mode"] = st.selectbox("검색 방식", ["similarity", "mmr"], index=["similarity", "mmr"].index(config["search_mode"]))
        config["top_k"] = st.slider("본문 Top-k", 1, 15, config["top_k"])
        config["enable_web_context"] = st.checkbox("웹 해설도 참고", value=config.get("enable_web_context", True))
        refresh = st.checkbox("실패·빈 검색 결과 다시 조회", value=False)
        if not os.getenv("HISTORY_SOURCE_CONTACT"):
            st.caption("출처 식별용 연락처 HISTORY_SOURCE_CONTACT 설정이 아직 필요하단다.")

item = by_id.get(period_id)
context_key = period_id or "free_questions"
chats = st.session_state.setdefault("chats", {})
messages = chats.setdefault(context_key, [])
if item:
    st.caption(f'참고할 시기: {item["title"]} ({item["year"]}) · 질문에 다른 시기를 명시하면 그 시기를 우선해 찾습니다.')
    st.link_button("이 시기의 출처·목차", item["url"])
with st.sidebar:
    if st.button("이 대화 지우기", width="stretch"):
        chats[context_key] = []
        messages = chats[context_key]
if not messages:
    st.markdown("### 어떤 역사가 궁금하세요?")
    st.write("사건이나 인물을 편하게 물어보렴. 날짜와 기록, 흥미로운 대목까지 함께 살펴보자꾸나.")
    examples = ["임진왜란 때 선조는 언제 의주로 피란 갔어?", "태종이 낙마한 일을 사관에게 알리지 말라고 했어?"]
    for i, example in enumerate(examples):
        if st.button(example, key=f"example_{i}"):
            st.session_state.pending_question = example
for message_number, message in enumerate(messages):
    with st.chat_message(message["role"], avatar="📜" if message["role"] == "assistant" else None):
        if message["role"] == "assistant":
            render_answer(message["answer"], message.get("sources", []), message.get("research", {}), message_key=f"{context_key}:{message_number}", show_suggestions=message_number == len(messages) - 1)
        else:
            st.markdown(message["content"])
question = st.chat_input("궁금한 역사 질문을 입력하세요. 기사나 연도를 먼저 고를 필요 없어요.")
question = question or st.session_state.pop("pending_question", None)
if question:
    if not os.getenv("GMS_KEY") or index is None:
        st.warning("답변 생성에는 GMS 키와 정상적인 검색 저장소가 필요합니다. 연도 목록은 키 없이 살펴볼 수 있습니다.")
    else:
        history = [{"role": m["role"], "content": m.get("content", str(m.get("answer", {})))} for m in messages]
        messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant", avatar="📜"):
            started = time.monotonic()
            try:
                with st.status("훈장님이 관련 기록을 살피는 중이란다…", expanded=True) as status:
                    source = SourceClient(store, config)
                    source.refresh = refresh
                    if refresh:
                        base_search = source.search
                        source.search = lambda *a, **kw: base_search(*a, **{**kw, "refresh": True})
                    index.config.update({k: config[k] for k in ["top_k", "search_mode", "fetch_k", "mmr_lambda"]})
                    graph = build_graph(store, source, index, model(config), config, st.write)
                    output = graph.invoke({"item": item, "question": question, "history": history})
                    status.update(label=collection_status(output["answer"]), state="complete", expanded=False)
                sources = [{"text": d.page_content, "metadata": d.metadata} for d in output["evidence"]]
                research = output["trace"]
                render_answer(output["answer"], sources, research, message_key=f"{context_key}:{len(messages)}")
                if research["failed_ids"]:
                    st.caption("일부 사료는 본문 접근 또는 이용 조건 확인이 남아 있어 답변 근거로 사용하지 않았습니다.")
                if research.get("errors"):
                    st.caption(" · ".join(research["errors"]))
                st.caption(f"처리 시간 {time.monotonic() - started:.1f}초")
                messages.append({"role": "assistant", "answer": output["answer"], "sources": sources, "research": research})
            except Exception:
                st.error("설명을 마치지 못했구나. 질문은 남겨두었으니 다시 시도해 보렴.")
                st.button("같은 질문 다시 보내기", key="retry_failed", on_click=queue_question, args=(question,))
