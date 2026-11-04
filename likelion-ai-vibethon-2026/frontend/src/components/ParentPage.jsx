import { Icon } from '../utils/icons'

export default function ParentPage({
  pendingDeliveries, currentDelivery, chooseDelivery, selectedQuestion, setSelectedQuestion,
  recording, record, answer, setAnswer, polished, setPolished, polish, saveAnswer,
  recommendationReason, setRecommendationReason, answerTone, setAnswerTone, toneOptions,
  loading
}) {
  const delayedCount = pendingDeliveries.filter((delivery) => delivery.mode === 'stealth' && delivery.should_notify).length
  const directDeliveries = pendingDeliveries.filter((delivery) => delivery.mode === 'direct')

  return (
    <main className="page parent">
      <div className="hero">
        <div>
          <div className="eyebrow">● 오늘의 인생 문답</div>
          <h1>자녀에게 건네는<br />경험과 조언의 질문지</h1>
          <p className="lead">지나온 삶에서 배운 소중한 경험을 편하게 들려주세요. 자녀에게 든든한 길잡이가 됩니다.</p>
        </div>
        <div className="date">
          <span>DATE</span><b>{new Date().getDate()}</b><small>{new Date().getMonth() + 1}월</small>
        </div>
      </div>

      {pendingDeliveries.length === 0 ? (
        <div className="paper" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <p style={{ color: 'var(--muted)', fontSize: 15 }}>오늘의 질문지를 준비하고 있습니다...</p>
        </div>
      ) : (
        <>
        {delayedCount > 0 && (
          <div className="answer-nudge" role="status">
            <b>답변을 기다리는 질문이 있어요</b>
            <p>하루 넘게 기다린 질문이 {delayedCount}개 있습니다. 여유가 될 때 경험을 들려주세요.</p>
          </div>
        )}

        {directDeliveries.length > 0 && (
          <div className="answer-nudge" style={{ background: '#fdf3ea', borderColor: 'var(--terra)', marginBottom: 20 }} role="status">
            <b style={{ color: 'var(--terra)' }}>자녀에게서 살짝(단독 질문)이 도착했어요</b>
            <p>자녀가 직접 부모님의 생각을 듣고 싶어 '살짝' 보낸 단독 질문입니다. 먼저 확인해 보세요.</p>
          </div>
        )}

        <div className="paper parent-answer-paper">
          <div className="step">
            <span>01</span>
            <div>
              <h2>답변할 질문 선택</h2>
              <p>10개의 질문 중 오늘 자녀에게 들려주고 싶은 질문 하나를 선택해 주세요</p>
            </div>
          </div>

          <div style={{ display: 'grid', gap: 10, marginBottom: 25 }}>
            {pendingDeliveries.map((delivery, idx) => {
              const qText = delivery.questions?.[0] || delivery.target_question
              const isSelected = (currentDelivery?.id === delivery.id) || (selectedQuestion === qText)
              return (
                <button
                  key={delivery.id}
                  onClick={() => chooseDelivery(delivery)}
                  style={{
                    padding: '14px 16px',
                    textAlign: 'left',
                    border: isSelected ? '2px solid var(--terra)' : '1px solid var(--line)',
                    background: isSelected ? '#fdf5ef' : '#fffcf8',
                    borderRadius: 6,
                    fontSize: 14,
                    fontFamily: 'var(--serif)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    transition: 'all 0.15s ease'
                  }}
                >
                  <b style={{ color: isSelected ? 'var(--terra)' : 'var(--muted)', minWidth: 24 }}>
                    {idx + 1}.
                  </b>
                  <div style={{ flex: 1 }}>
                    <span style={{ fontWeight: isSelected ? 600 : 400, color: 'var(--text)' }}>
                      {qText}
                    </span>
                    {delivery.mode === 'direct' ? (
                      <span style={{ marginLeft: 8, fontSize: 11, background: 'var(--terra)', color: '#fff', padding: '2px 6px', borderRadius: 4 }}>
                        살짝 · 단독
                      </span>
                    ) : (
                      delivery.mode === 'stealth' && (
                        <span style={{ marginLeft: 8, fontSize: 11, background: 'var(--sage)', color: '#fff', padding: '2px 6px', borderRadius: 4 }}>
                          슬쩍 · 묶음
                        </span>
                      )
                    )}
                  </div>
                </button>
              )
            })}
          </div>


          <div className="question">
            <div><b>선택된 질문</b><em>{currentDelivery?.emotion}</em></div>
            <blockquote>{selectedQuestion}</blockquote>
          </div>

          <div className="answer">
            <div className="answer-head"><h2>나의 경험 들려주기</h2><span>텍스트 또는 음성</span></div>
            <div className="tone-picker">
              <div><b>전하고 싶은 말투</b><span>원래 의도에 가장 가까운 문체를 골라주세요.</span></div>
              <div>
                {toneOptions.map((tone) => (
                  <button
                    type="button"
                    key={tone.value}
                    className={answerTone === tone.value ? 'selected' : ''}
                    onClick={() => {
                      setAnswerTone(tone.value)
                      setPolished('')
                      setRecommendationReason('')
                    }}
                  >
                    <b>{tone.title}</b><small>{tone.description}</small>
                  </button>
                ))}
              </div>
            </div>
            <div className={`recorder ${recording ? 'live' : ''}`}>
              <button type="button" onClick={record} title={recording ? '음성 입력 완료' : '음성 입력 시작'}>
                <Icon type="mic" />
              </button>
              <div>
                <b>음성으로 들려주기</b>
                <small>{recording ? '말씀하시는 내용이 바로 적힙니다. (마이크를 다시 누르면 완료)' : '마이크 버튼을 눌러 말씀해 보세요'}</small>
              </div>
              {recording && <div className="wave"><i /><i /><i /></div>}
            </div>

            <div className="or">또는 직접 입력</div>
            <div className="field">
              <textarea placeholder="그때를 돌이켜보면 어떤 마음이었는지 편하게 적어주세요." value={answer} onChange={(e) => { setAnswer(e.target.value); setPolished(''); setRecommendationReason('') }} />
            </div>

            <button className="action" disabled={loading || !answer.trim()} onClick={polish} style={{ marginTop: 15 }}>
              {loading ? <i /> : 'AI로 말투 다듬기'}
            </button>

            {polished && (
              <div className="polished">
                <div><span>자녀에게 전달될 다듬어진 문장</span></div>
                <p>{polished}</p>
                {recommendationReason && <small className="recommendation-reason">{recommendationReason}</small>}
                <div className="actions">
                  <button onClick={() => saveAnswer('original')} disabled={loading}>원문으로 남기기</button>
                  <button onClick={() => saveAnswer('polished')} disabled={loading}>추천 문장으로 남기기</button>
                </div>
              </div>
            )}
          </div>
        </div>
        </>
      )}
    </main>
  )
}
