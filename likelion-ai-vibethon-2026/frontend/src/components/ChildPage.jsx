import { Icon } from '../utils/icons'

const emotions = [
  ['지침', '😮‍💨'], ['불안', '😟'], ['기쁨', '😊'], ['외로움', '🥺'], ['설렘', '🥰'], ['슬픔', '😢']
]

export default function ChildPage({
  emotion, setEmotion, worry, setWorry, mode, setMode, transformAndSend, loading
}) {
  return (
    <main className="page child">
      <div className="eyebrow">● 마음 전달</div>
      <h1>마음에 걸리는 일을<br />슬쩍 꺼내보세요</h1>
      <p className="lead">
        자녀의 고민 내용은 부모님께 그대로 노출되지 않습니다.<br />
        AI가 부모님의 과거 회고 질문으로 바꾸어 일상 질문 4개와 함께 전달합니다.
      </p>

      <div className="paper">
        <div className="step">
          <span>01</span>
          <div><h2>지금 마음의 날씨</h2><p>가장 가까운 감정을 골라주세요</p></div>
        </div>
        <div className="emotions">
          {emotions.map(([label, icon]) => (
            <button key={label} className={emotion === label ? 'selected' : ''} onClick={() => setEmotion(label)}>
              <i>{icon}</i><span>{label}</span>
            </button>
          ))}
        </div>

        <hr />

        <div className="step">
          <span>02</span>
          <div><h2>속마음 적어보기</h2><p>부모님께 직접 말하기 힘든 고민을 솔직하게 적어주세요</p></div>
        </div>
        <label className="field">
          <textarea placeholder="예: 취업 준비가 길어져서 자꾸 포기하고 싶어져요. 노력해도 안 되는 것 같아 막막해요." value={worry} onChange={(e) => setWorry(e.target.value)} />
          <small>{worry.length}자</small>
        </label>

        <hr />

        <div className="step">
          <span>03</span>
          <div><h2>전달 방식</h2><p>자녀의 원래 고민은 저장되지 않고 정제된 질문 피드로만 변환됩니다</p></div>
        </div>
        <div className="modes">
          <button className={mode === 'stealth' ? 'selected' : ''} onClick={() => setMode('stealth')}>
            <i /><div><b>슬쩍 <em>추천</em></b><p>익명 질문 묶음: 4개의 일상 질문 속에 자녀의 핵심 질문 1개를 슬쩍 숨겨서 전달합니다.</p></div>
          </button>
          <button className={mode === 'direct' ? 'selected' : ''} onClick={() => setMode('direct')}>
            <i /><div><b>살짝</b><p>단독 질문: 정제된 회고 질문 1개만 부모님께 살짝 직접 전달합니다.</p></div>
          </button>
        </div>

        <button className="action" disabled={loading} onClick={transformAndSend}>
          {loading ? <i /> : '질문 배달하기'}
          {!loading && <Icon type="arrow" />}
        </button>
        <p className="privacy">자녀의 원문 고민은 AI 변환 즉시 파기되며 DB에 저장되지 않습니다.</p>
      </div>
    </main>
  )
}
