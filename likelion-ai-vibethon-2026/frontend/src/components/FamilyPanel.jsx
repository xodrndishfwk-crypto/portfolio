export default function FamilyPanel({
  family, user, roleLabels, inviteData, loading, message, formatDate,
  onClose, onCreateInvite, onCopyInvite, onLogout,
}) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="family-panel" role="dialog" aria-modal="true" aria-labelledby="family-panel-title" onClick={(event) => event.stopPropagation()}>
        <button className="modal-close" type="button" aria-label="닫기" onClick={onClose}>×</button>
        <div className="eyebrow">● 가족 연결</div>
        <h2 id="family-panel-title">{family.name}</h2>
        <p>함께 연결된 가족을 확인하고 새 구성원을 초대할 수 있어요.</p>

        <div className="family-members">
          <h3>우리 가족 <span>{family.members?.length || 0}명</span></h3>
          <div>
            {family.members?.map((member) => (
              <article key={member.user_id} className={member.user_id === user.id ? 'me' : ''}>
                <b>{roleLabels[member.role] || '가족'}</b>
                <span>{member.name}</span>
                {member.user_id === user.id && <em>나</em>}
              </article>
            ))}
          </div>
        </div>

        <div className="invite-divider"><span>가족 초대 코드</span></div>
        {loading ? (
          <div className="invite-empty">초대 코드를 확인하고 있어요…</div>
        ) : inviteData ? (
          <div className="invite-ready">
            <div className="invite-code">{inviteData.invite_code}</div>
            <small>{formatDate(inviteData.expires_at)}까지 사용할 수 있어요.</small>
            <button type="button" onClick={onCopyInvite}>코드 복사하기</button>
          </div>
        ) : (
          <button className="invite-create" type="button" onClick={onCreateInvite}>초대 코드 만들기</button>
        )}
        {message && <p className="invite-message" role="status">{message}</p>}
        {onLogout && (
          <div className="panel-footer-actions">
            <button
              type="button"
              className="panel-logout-btn"
              onClick={() => {
                onClose()
                onLogout()
              }}
            >
              로그아웃하기
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
