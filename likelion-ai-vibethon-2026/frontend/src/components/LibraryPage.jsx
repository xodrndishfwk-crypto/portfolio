import { Icon } from '../utils/icons'

export default function LibraryPage({ library, formatDate, react, childUser }) {
  return (
    <main className="page library">
      <div className="hero">
        <div>
          <div className="eyebrow">● 나의 지혜 서재</div>
          <h1>{childUser ? '내 질문에 도착한 지혜' : '내가 남긴 지혜'}</h1>
          <p className="lead">{childUser ? '내가 보낸 질문에 도착한 답변만 간직하는 개인 공간입니다.' : '내가 직접 남긴 답변만 모아 다시 읽을 수 있습니다.'}</p>
        </div>
        <div className="count">
          <Icon type="book" /><b>{library.length}</b><span>개의 이야기</span>
        </div>
      </div>

      <div className="wisdom-list" style={{ marginTop: 35 }}>
        {library.length === 0 ? (
          <p style={{ textAlign: 'center', color: 'var(--muted)', padding: 40 }}>아직 등록된 지혜 답변이 없습니다.</p>
        ) : (
          library.map((item) => (
            <article key={item.id} className="wisdom">
              <div className="wisdom-top">
                <span>{item.emotion || '따뜻함'}</span>
                <time>{formatDate(item.created_at)}</time>
              </div>
              <div className="question-history">
                <b>{childUser ? '당시 내가 보낸 질문' : '내가 답한 질문'}</b>
                <p>{item.original_question || item.question}</p>
                {item.original_question && item.question !== item.original_question && <small>답변한 질문: {item.question}</small>}
              </div>
              <blockquote>{item.polished_answer}</blockquote>
              <div className="author">
                <b>{item.author_name ? item.author_name[0] : '가'}</b>
                <div><strong>{item.author_name || '부모님'}</strong><span>가족의 지혜</span></div>
              </div>
              <div className="wisdom-foot">
                <div>
                  <button onClick={() => react(item.id, 'thanks')}>고마워요 {item.thanks_count > 0 && `(${item.thanks_count})`}</button>
                  <button onClick={() => react(item.id, 'moved')}>감동이에요 {item.moved_count > 0 && `(${item.moved_count})`}</button>
                </div>
              </div>

              {childUser && item.reference_answers?.length > 0 && (
                <aside className="reference-wisdom">
                  <div><b>같은 질문에 대한 또 다른 지혜</b><span>다른 가족의 익명 답변</span></div>
                  {item.reference_answers.map((reference, index) => (
                    <article key={`${item.id}-reference-${index}`}>
                      <p>{reference.polished_answer}</p>
                      <time>{formatDate(reference.created_at)}</time>
                    </article>
                  ))}
                </aside>
              )}
            </article>
          ))
        )}
      </div>
    </main>
  )
}
