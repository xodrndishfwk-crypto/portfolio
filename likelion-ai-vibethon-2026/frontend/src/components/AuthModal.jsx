export default function AuthModal({
  token, authMode, setAuthMode, authRole, handleRoleChange, authSubRole, handleSubRoleChange,
  authName, setAuthName, authEmail, setAuthEmail, authPassword, setAuthPassword,
  familyNameInput, setFamilyNameInput, inviteCodeInput, setInviteCodeInput,
  handleAuthSubmit, loading
}) {
  return (
    <div style={{ maxWidth: 460, margin: '50px auto 80px', padding: '0 20px', animation: 'rise 0.4s ease' }}>
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <span style={{ color: 'var(--terra)', fontSize: 13, fontWeight: 700, letterSpacing: '0.1em' }}>SEUL-JJEOCK</span>
        <h1 style={{ fontFamily: 'var(--serif)', fontSize: 32, margin: '10px 0 8px', color: 'var(--ink)' }}>마음을 잇는 작은 질문</h1>
        <p style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.6 }}>
          말하지 못한 자녀의 고민과 부모의 지나온 삶의 지혜를 슬쩍 이어드립니다.
        </p>
      </div>

      <div className="paper" style={{ padding: '36px 32px' }}>
        <h2 style={{ fontFamily: 'var(--serif)', fontSize: 20, marginBottom: 18, color: 'var(--ink)' }}>
          {!token ? (authMode === 'login' ? '로그인' : '가족 회원가입') : (authMode === 'family_create' ? '새 가족 만들기' : '가족 초대 코드 입력')}
        </h2>

        <form onSubmit={handleAuthSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {!token && authMode === 'register' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 6 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>1. 역할을 선택해주세요</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <button type="button" onClick={() => handleRoleChange('child')} style={{ padding: 11, border: authRole === 'child' ? '2px solid var(--terra)' : '1px solid var(--line)', background: authRole === 'child' ? '#fdf5ef' : '#fff', color: authRole === 'child' ? 'var(--terra)' : 'var(--ink)', fontWeight: 'bold', borderRadius: 4 }}>자녀로 참여</button>
                  <button type="button" onClick={() => handleRoleChange('parent')} style={{ padding: 11, border: authRole === 'parent' ? '2px solid var(--terra)' : '1px solid var(--line)', background: authRole === 'parent' ? '#fdf5ef' : '#fff', color: authRole === 'parent' ? 'var(--terra)' : 'var(--ink)', fontWeight: 'bold', borderRadius: 4 }}>부모로 참여</button>
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>2. 가족 내 호칭을 골라주세요</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {(authRole === 'child' ? ['아들', '딸'] : ['아빠', '엄마']).map((sub) => (
                    <button key={sub} type="button" onClick={() => handleSubRoleChange(sub)} style={{ padding: 9, border: authSubRole === sub ? '2px solid var(--terra)' : '1px solid var(--line)', background: authSubRole === sub ? '#fdf5ef' : '#fff', color: authSubRole === sub ? 'var(--terra)' : 'var(--muted)', borderRadius: 4 }}>{sub}</button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>표시될 이름 / 닉네임</label>
                <input type="text" placeholder="예: 큰딸, 막내아들, 아빠" value={authName} onChange={(e) => setAuthName(e.target.value)} required style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--line)', borderRadius: 4 }} />
              </div>
            </div>
          )}

          {!token && (
            <>
              <input type="email" placeholder="이메일 주소" value={authEmail} onChange={(e) => setAuthEmail(e.target.value)} required style={{ padding: '11px 12px', border: '1px solid var(--line)', borderRadius: 4 }} />
              <input type="password" placeholder="비밀번호" value={authPassword} onChange={(e) => setAuthPassword(e.target.value)} required style={{ padding: '11px 12px', border: '1px solid var(--line)', borderRadius: 4 }} />
            </>
          )}

          {token && authMode === 'family_create' && (
            <input type="text" placeholder="가족 그룹명 (예: 행복한 우리집, 김가네)" value={familyNameInput} onChange={(e) => setFamilyNameInput(e.target.value)} required style={{ padding: '11px 12px', border: '1px solid var(--line)', borderRadius: 4 }} />
          )}

          {token && authMode === 'family_join' && (
            <input type="text" placeholder="8자리 가족 초대 코드 (예: A1B2C3D4)" value={inviteCodeInput} onChange={(e) => setInviteCodeInput(e.target.value)} required style={{ padding: '11px 12px', border: '1px solid var(--line)', borderRadius: 4 }} />
          )}

          <button type="submit" disabled={loading} style={{ padding: 13, marginTop: 6, background: 'var(--terra)', color: '#fff', border: 0, borderRadius: 4, fontWeight: 'bold', fontSize: 14, cursor: 'pointer' }}>
            {loading ? '처리 중...' : authMode === 'login' ? '로그인하기' : '완료하고 시작하기'}
          </button>
        </form>

        <div style={{ marginTop: 18, display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          {!token ? (
            <button type="button" onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')} style={{ border: 0, background: 'none', color: 'var(--muted)', textDecoration: 'underline', cursor: 'pointer' }}>
              {authMode === 'login' ? '처음이신가요? 회원가입하기' : '이미 계정이 있으신가요? 로그인'}
            </button>
          ) : (
            <button type="button" onClick={() => setAuthMode(authMode === 'family_join' ? 'family_create' : 'family_join')} style={{ border: 0, background: 'none', color: 'var(--muted)', textDecoration: 'underline', cursor: 'pointer' }}>
              {authMode === 'family_join' ? '+ 새 가족 만들기' : '기존 가족 초대 코드로 참여하기'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
