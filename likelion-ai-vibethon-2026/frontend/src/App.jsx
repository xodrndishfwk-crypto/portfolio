import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import './QuestionOptions.css'
import './FeatureUpdates.css'
import heroEnvelopeEyes from './assets/hero-envelope-eyes.png'
import heroLetter from './assets/hero-letter.gif'
import Header from './components/Header'
import ChildPage from './components/ChildPage'
import ParentPage from './components/ParentPage'
import LibraryPage from './components/LibraryPage'
import FamilyPanel from './components/FamilyPanel'
import { Icon } from './utils/icons'

const getInitialApiUrl = () => {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('seuljjeock-api-url')
    if (saved) return saved
    if (window.Capacitor?.isNativePlatform?.() || window.Capacitor?.getPlatform?.() === 'android') {
      return import.meta.env.VITE_API_URL || 'https://prudishly-outdoors-eliminate.ngrok-free.dev'
    }
  }
  return import.meta.env.VITE_API_URL || ''
}
const API = getInitialApiUrl()
const heroBackgrounds = [heroEnvelopeEyes, heroLetter]
const NICKNAME_MAX_LENGTH = 12
const roleOptions = [
  { value: 'son', label: '아들', description: '마음을 질문으로 보내요' },
  { value: 'daughter', label: '딸', description: '마음을 질문으로 보내요' },
  { value: 'father', label: '아빠', description: '경험을 답장으로 남겨요' },
  { value: 'mother', label: '엄마', description: '경험을 답장으로 남겨요' },
]
const roleLabels = { son: '아들', daughter: '딸', father: '아빠', mother: '엄마', child: '자녀', parent: '부모' }
const toneOptions = [
  { value: 'firm', title: '단호하고 분명하게', description: '기준과 책임을 또렷하게 전해요.' },
  { value: 'warm', title: '따뜻하고 공감하게', description: '이해와 온기를 먼저 전해요.' },
  { value: 'calm', title: '차분하게 설명하기', description: '이유를 순서 있게 말해요.' },
  { value: 'practical', title: '현실적인 해결 중심', description: '실행 가능한 행동에 집중해요.' },
  { value: 'friendly', title: '친근하고 편안하게', description: '평소 대화처럼 전해요.' },
]
const isChildRole = (role) => ['son', 'daughter', 'child'].includes(role)

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric', weekday: 'short' }).format(d)
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('seuljjeock-token') || '')
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('seuljjeock-user')) || null } catch { return null }
  })
  const [family, setFamily] = useState(() => {
    try { return JSON.parse(localStorage.getItem('seuljjeock-family')) || null } catch { return null }
  })
  const [userRole, setUserRole] = useState(() => localStorage.getItem('seuljjeock-role') || 'child')

  const [authMode, setAuthMode] = useState('login')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authName, setAuthName] = useState('')
  const [authRole, setAuthRole] = useState('son')
  const [inviteCodeInput, setInviteCodeInput] = useState('')
  const [familyNameInput, setFamilyNameInput] = useState('')
  const [familyAliasInput, setFamilyAliasInput] = useState('')

  const [apiStatus, setApiStatus] = useState('checking')
  const [aiReady, setAiReady] = useState(false)
  const [screen, setScreen] = useState(() => (isChildRole(userRole) ? 'child' : 'parent'))
  const [emotion, setEmotion] = useState('지침')
  const [worry, setWorry] = useState('')
  const [mode, setMode] = useState('stealth')

  const [currentDelivery, setCurrentDelivery] = useState(null)
  const [pendingDeliveries, setPendingDeliveries] = useState([])
  const [selectedQuestion, setSelectedQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [polished, setPolished] = useState('')
  const [recommendationReason, setRecommendationReason] = useState('')
  const [answerTone, setAnswerTone] = useState('warm')
  const [library, setLibrary] = useState([])
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteData, setInviteData] = useState(null)
  const [inviteLoading, setInviteLoading] = useState(false)
  const [inviteMessage, setInviteMessage] = useState('')

  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [recording, setRecording] = useState(false)
  const [heroIndex, setHeroIndex] = useState(0)
  const recognitionRef = useRef(null)
  const baseAnswerRef = useRef('')

  const membership = family?.members?.find((member) => member.user_id === user?.id)
  const currentRole = membership?.role || userRole
  const childUser = isChildRole(currentRole)
  const notificationCount = pendingDeliveries.filter((delivery) => delivery.should_notify).length

  const authHeaders = useCallback(() => ({
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }), [token])

  const go = (next) => {
    if (next === 'child' && !childUser) return
    if (next === 'parent' && childUser) return
    setScreen(next)
    setNotice('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const openInvitePanel = async () => {
    setInviteOpen(true)
    setInviteLoading(true)
    setInviteMessage('')
    try {
      const [familyRes, inviteRes] = await Promise.all([
        fetch(`${API}/api/families/${family.id}`, { headers: authHeaders() }),
        fetch(`${API}/api/families/${family.id}/invite`, { headers: authHeaders() }),
      ])
      if (!familyRes.ok || !inviteRes.ok) {
        const error = await (!familyRes.ok ? familyRes : inviteRes).json()
        throw new Error(error.detail || '가족 정보를 확인하지 못했습니다.')
      }
      const latestFamily = await familyRes.json()
      setFamily(latestFamily)
      localStorage.setItem('seuljjeock-family', JSON.stringify(latestFamily))
      setInviteData(await inviteRes.json())
    } catch (err) {
      setInviteMessage(err.message)
    } finally {
      setInviteLoading(false)
    }
  }

  const createInvite = async () => {
    setInviteLoading(true)
    setInviteMessage('')
    try {
      const res = await fetch(`${API}/api/families/${family.id}/invites`, { method: 'POST', headers: authHeaders() })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '초대 코드 생성 실패')
      setInviteData(data)
      setInviteMessage('새 가족에게 이 코드를 공유해 주세요.')
    } catch (err) {
      setInviteMessage(err.message)
    } finally {
      setInviteLoading(false)
    }
  }

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(inviteData.invite_code)
      setInviteMessage('초대 코드를 복사했습니다.')
    } catch {
      setInviteMessage('복사하지 못했습니다. 코드를 직접 선택해 주세요.')
    }
  }

  const chooseDelivery = (delivery) => {
    if (recording && recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
      setRecording(false)
    }
    setCurrentDelivery(delivery)
    setSelectedQuestion(delivery.questions?.[0] || delivery.target_question)
    setAnswer('')
    setPolished('')
    setRecommendationReason('')
  }

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try { recognitionRef.current.abort() } catch {}
      }
    }
  }, [])

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API}/api/health`, { method: 'GET', headers: { 'ngrok-skip-browser-warning': 'true' } })
        if (res.ok) {
          const data = await res.json()
          setApiStatus('online')
          setAiReady(Boolean(data.ai))
        } else {
          setApiStatus('offline')
          setAiReady(false)
        }
      } catch {
        setApiStatus('offline')
        setAiReady(false)
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (token) return undefined
    const interval = setInterval(() => {
      setHeroIndex((current) => (current + 1) % heroBackgrounds.length)
    }, 6500)
    return () => clearInterval(interval)
  }, [token])

  // 2. 미답변 질문 및 서재 목록 실시간 동기화
  const refreshData = useCallback(async () => {
    if (!token || !family?.id) return
    try {
      const qRes = await fetch(`${API}/api/questions/deliveries?family_id=${family.id}&status=pending`, { headers: authHeaders() })
      if (qRes.status === 401) {
        handleLogout()
        setNotice('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.')
        return
      }
      if (qRes.ok) {
        const deliveries = await qRes.json()
        setPendingDeliveries(deliveries)
        if (deliveries.length > 0) {
          const active = deliveries.find((delivery) => delivery.id === currentDelivery?.id) || deliveries[0]
          setCurrentDelivery(active)
          setSelectedQuestion((selected) => active.questions?.includes(selected) ? selected : (active.questions?.[0] || active.target_question))
        } else {
          setCurrentDelivery(null)
          setSelectedQuestion('')
        }
      }
      const aRes = await fetch(`${API}/api/answers?family_id=${family.id}`, { headers: authHeaders() })
      if (aRes.status === 401) {
        handleLogout()
        setNotice('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.')
        return
      }
      if (aRes.ok) {
        const answers = await aRes.json()
        setLibrary(answers)
      }
    } catch (err) {
      console.warn('데이터 동기화 지연:', err)
    }
  }, [authHeaders, currentDelivery?.id, family, token])

  useEffect(() => {
    if (token && family?.id) {
      // 서버 상태를 화면 진입 시 동기화해야 하므로 의도적으로 effect에서 갱신합니다.
      // oxlint-disable-next-line react-hooks/set-state-in-effect
      refreshData()
      const interval = setInterval(refreshData, 10000)
      return () => clearInterval(interval)
    }
    return undefined
  }, [family?.id, refreshData, screen, token])

  const handleAuthSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setNotice('')
    try {
      if (authMode === 'login') {
        const res = await fetch(`${API}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
          body: JSON.stringify({ email: authEmail, password: authPassword }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || '로그인에 실패했습니다.')
        setToken(data.access_token)
        setUser(data.user)
        localStorage.setItem('seuljjeock-token', data.access_token)
        localStorage.setItem('seuljjeock-user', JSON.stringify(data.user))
        if (data.family) {
          const savedMembership = data.family.members.find((member) => member.user_id === data.user.id)
          const savedRole = savedMembership?.role || 'child'
          setFamily(data.family)
          setUserRole(savedRole)
          localStorage.setItem('seuljjeock-family', JSON.stringify(data.family))
          localStorage.setItem('seuljjeock-role', savedRole)
          setScreen(isChildRole(savedRole) ? 'child' : 'parent')
          setNotice(`${data.user.name}님, 다시 오신 것을 환영합니다!`)
        } else {
          setFamily(null)
          localStorage.removeItem('seuljjeock-family')
          setNotice(`${data.user.name}님 환영합니다! 가족 그룹을 연결해 주세요.`)
          setAuthMode('family_join')
        }
      } else if (authMode === 'register') {
        const displayName = authName.trim()
        const res = await fetch(`${API}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
          body: JSON.stringify({ email: authEmail, password: authPassword, name: displayName }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || '회원가입에 실패했습니다.')
        setNotice('가입이 완료되었습니다. 방금 만든 정보로 로그인해 주세요.')
        setAuthMode('login')
      } else if (authMode === 'family_create') {
        const res = await fetch(`${API}/api/families`, {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ name: familyNameInput, role: authRole, nickname: familyAliasInput.trim() }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || '가족 생성 실패')
        setFamily(data)
        setUserRole(authRole)
        const renamedUser = { ...user, name: familyAliasInput.trim() }
        setUser(renamedUser)
        localStorage.setItem('seuljjeock-family', JSON.stringify(data))
        localStorage.setItem('seuljjeock-role', authRole)
        localStorage.setItem('seuljjeock-user', JSON.stringify(renamedUser))
        setNotice(`'${data.name}' 가족이 연결되었습니다!`)
        setScreen(isChildRole(authRole) ? 'child' : 'parent')
      } else if (authMode === 'family_join') {
        const res = await fetch(`${API}/api/families/join`, {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ invite_code: inviteCodeInput, role: authRole, nickname: familyAliasInput.trim() }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || '가족 참여 실패')
        setFamily(data)
        setUserRole(authRole)
        const renamedUser = { ...user, name: familyAliasInput.trim() }
        setUser(renamedUser)
        localStorage.setItem('seuljjeock-family', JSON.stringify(data))
        localStorage.setItem('seuljjeock-role', authRole)
        localStorage.setItem('seuljjeock-user', JSON.stringify(renamedUser))
        setNotice(`'${data.name}' 가족에 참여하셨습니다!`)
        setScreen(isChildRole(authRole) ? 'child' : 'parent')
      }
    } catch (err) {
      setNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('seuljjeock-token')
    localStorage.removeItem('seuljjeock-user')
    localStorage.removeItem('seuljjeock-family')
    localStorage.removeItem('seuljjeock-role')
    setToken('')
    setUser(null)
    setFamily(null)
    setUserRole('child')
    setAuthRole('son')
    setInviteOpen(false)
    setInviteData(null)
    setInviteMessage('')
    setPendingDeliveries([])
    setLibrary([])
    setCurrentDelivery(null)
    setFamilyAliasInput('')
    setAuthMode('login')
    setNotice('로그아웃되었습니다.')
  }

  async function transformAndSend() {
    if (!worry.trim()) return setNotice('마음에 걸리는 일을 한 줄만 들려주세요.')
    if (!family?.id) return setNotice('가족 그룹에 먼저 연결되어야 질문을 전송할 수 있습니다.')
    setLoading(true)
    setNotice('')
    try {
      const res = await fetch(`${API}/api/questions/deliveries`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ family_id: family.id, worry, emotion, mode }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '질문 전달 실패')
      setWorry('')
      setNotice(mode === 'direct' ? "단독 질문('살짝')으로 부모님께 조용히 전달했어요." : "익명 질문 묶음('슬쩍')으로 4개의 일상 질문 사이에 섞어 보냈어요.")
      await refreshData()
    } catch (err) {
      setNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  function record() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setNotice('현재 브라우저에서는 음성 인식을 지원하지 않습니다. Chrome 또는 Edge 브라우저를 이용해 주세요.')
      return
    }

    if (recording) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop() } catch {}
      }
      setRecording(false)
      setNotice('음성 입력을 완료했습니다.')
      return
    }

    try {
      const recognition = new SpeechRecognition()
      recognition.lang = 'ko-KR'
      recognition.continuous = true
      recognition.interimResults = true

      baseAnswerRef.current = answer.trim() ? answer.trim() + ' ' : ''

      recognition.onstart = () => {
        setRecording(true)
        setNotice('목소리를 듣고 있어요... 편하게 말씀해 보세요.')
      }

      recognition.onresult = (event) => {
        let transcript = ''
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript
        }
        const fullText = (baseAnswerRef.current + transcript).trim()
        setAnswer(fullText)
        setPolished('')
        setRecommendationReason('')
      }

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error)
        setRecording(false)
        if (event.error === 'not-allowed') {
          setNotice('마이크 사용 권한이 차단되었습니다. 브라우저 설정에서 마이크를 허용해 주세요.')
        } else if (event.error === 'no-speech') {
          setNotice('음성이 감지되지 않았습니다. 다시 말씀해 보세요.')
        } else if (event.error === 'network') {
          setNotice('음성 인식 서버와의 연결 상태를 확인해 주세요.')
        } else if (event.error !== 'aborted') {
          setNotice('음성 인식 중 오류가 발생했습니다.')
        }
      }

      recognition.onend = () => {
        setRecording(false)
      }

      recognitionRef.current = recognition
      recognition.start()
    } catch (err) {
      console.error('Speech recognition start failed:', err)
      setRecording(false)
      setNotice('음성 인식을 시작하지 못했습니다.')
    }
  }

  async function polish() {
    if (recording && recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
      setRecording(false)
    }
    if (!answer.trim()) return setNotice('짧게라도 경험을 들려주세요.')
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/answers/polish`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ answer, question: selectedQuestion, tone: answerTone }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '답변 다듬기 실패')
      setPolished(data.polished)
      setRecommendationReason(data.recommendation_reason || '')
    } catch (err) {
      setNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function saveAnswer(version = 'polished') {
    if (recording && recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
      setRecording(false)
    }
    if (!currentDelivery?.id) return setNotice('답변할 대상 질문이 없습니다.')
    const finalAnswer = version === 'original' ? answer : polished
    if (!finalAnswer.trim()) return setNotice('보낼 답변을 먼저 작성해 주세요.')
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/answers/deliveries/${currentDelivery.id}`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ question: selectedQuestion, answer, final_answer: finalAnswer, tone: answerTone }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '답변 저장 실패')
      setAnswer('')
      setPolished('')
      setRecommendationReason('')
      setNotice('부모님의 소중한 경험이 가족 서재에 기록되었습니다.')
      await refreshData()
      go('library')
    } catch (err) {
      setNotice(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function react(id, type) {
    try {
      const res = await fetch(`${API}/api/answers/${id}/reactions`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ reaction_type: type }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '반응 저장 실패')
      setLibrary(library.map((x) => (x.id === id ? { ...x, [`${type}_count`]: (x[`${type}_count`] || 0) + 1 } : x)))
    } catch (err) {
      setNotice(err.message)
    }
  }

  if (!token) {
    return (
      <div className="auth-landing">
        <div className="hero-backgrounds" aria-hidden="true">
          {heroBackgrounds.map((image, index) => (
            <div
              key={image}
              className={`hero-background ${heroIndex === index ? 'is-active' : ''}`}
              style={{ backgroundImage: `url(${image})` }}
            />
          ))}
        </div>
        <div className="hero-wash" aria-hidden="true" />

        <header className="landing-header">
          <button className="landing-brand" onClick={() => setHeroIndex((heroIndex + 1) % heroBackgrounds.length)}>
            <span>슬쩍</span>
            <small>마음을 잇는 작은 질문</small>
          </button>
          <div className={`landing-status ${apiStatus === 'online' ? (aiReady ? 'ai-on' : 'api-ok') : 'offline'}`}>
            <i /> {apiStatus === 'online' ? (aiReady ? '✦ AI 연결됨' : '로컬 모드') : '연결 확인 중'}
          </div>
        </header>

        <main className="landing-content">
          <section className="landing-copy">
            <p className="landing-kicker">A LETTER BETWEEN US</p>
            <h1>
              말하기 어려운 마음을
              <br />
              질문 한 장에 담아요.
            </h1>
            <p>
              직접 꺼내기 어려웠던 이야기를 슬쩍 건네보세요.
              <br />
              가족의 경험이 다정한 답장이 되어 돌아옵니다.
            </p>
            <div className="hero-pagination" aria-label="배경 이미지 선택">
              {heroBackgrounds.map((_, index) => (
                <button
                  key={index}
                  className={heroIndex === index ? 'is-active' : ''}
                  onClick={() => setHeroIndex(index)}
                  aria-label={`${index + 1}번째 배경 보기`}
                />
              ))}
            </div>
          </section>

          <section className="auth-card">
            <div className="auth-card-heading">
              <span>{authMode === 'login' ? '다시 만나 반가워요' : '우리 가족의 첫 페이지'}</span>
              <h2>{authMode === 'login' ? '로그인' : '회원가입'}</h2>
              <p>{authMode === 'login' ? '가족에게 도착한 마음을 확인해 보세요.' : '가볍게 시작하고, 천천히 마음을 나눠요.'}</p>
            </div>

            <form className="auth-form" onSubmit={handleAuthSubmit}>
              {authMode === 'register' && (
                <label>
                  <span>이름 또는 호칭</span>
                  <input
                    type="text"
                    placeholder="예: 딸, 아빠"
                    value={authName}
                    onChange={(e) => setAuthName(e.target.value)}
                    required
                  />
                </label>
              )}
              <label>
                <span>이메일</span>
                <input
                  type="email"
                  placeholder="family@example.com"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  required
                />
              </label>
              <label>
                <span>비밀번호</span>
                <input
                  type="password"
                  placeholder="4자 이상 입력해 주세요"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  required
                />
              </label>

              {notice && <p className="auth-notice">{notice}</p>}
              <button className="auth-submit" type="submit" disabled={loading}>
                {loading ? '마음을 여는 중…' : authMode === 'login' ? '로그인하기' : '계정 만들기'}
                {!loading && <Icon type="arrow" />}
              </button>
            </form>

            <div className="auth-switch">
              <span>{authMode === 'login' ? '아직 계정이 없나요?' : '이미 계정이 있나요?'}</span>
              <button onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
                {authMode === 'login' ? '회원가입' : '로그인'}
              </button>
            </div>
          </section>
        </main>
      </div>
    )
  }

  if (!family) {
    return (
      <div className="family-onboarding">
        <div className="onboarding-orb orb-one" />
        <div className="onboarding-orb orb-two" />
        <header className="onboarding-header">
          <b>슬쩍</b>
          <div className="onboarding-header-tools">
            <span className="onboarding-user-badge"><b>{user?.name}</b>님</span>
            <button className="onboarding-logout-btn" onClick={handleLogout} title="로그아웃">
              <Icon type="logout" />
              <span>로그아웃</span>
            </button>
          </div>
        </header>
        <main className="onboarding-card">
          <span className="onboarding-step">WELCOME, {user?.name}</span>
          <h1>{authMode === 'family_create' ? '새 가족의 문을 열어요' : '가족의 초대를 받았나요?'}</h1>
          <p>한 가족으로 연결되면 질문과 답장을 안전하게 나눌 수 있어요.</p>

          <form className="auth-form onboarding-form" onSubmit={handleAuthSubmit}>
            {authMode === 'family_create' ? (
              <label>
                <span>가족 이름</span>
                <input
                  type="text"
                  placeholder="예: 김가네 마음 우체국"
                  value={familyNameInput}
                  onChange={(e) => setFamilyNameInput(e.target.value)}
                  required
                />
              </label>
            ) : (
              <label>
                <span>초대 코드</span>
                <input
                  type="text"
                  placeholder="8자리 코드를 입력해 주세요"
                  value={inviteCodeInput}
                  onChange={(e) => setInviteCodeInput(e.target.value.toUpperCase())}
                  required
                />
              </label>
            )}

            <fieldset className="role-picker">
              <legend>가족 안에서 나의 역할</legend>
              {roleOptions.map((role) => (
                <label key={role.value} className={authRole === role.value ? 'selected' : ''}>
                  <input type="radio" name="role" value={role.value} checked={authRole === role.value} onChange={() => setAuthRole(role.value)} />
                  <span>{role.label}</span>
                  <small>{role.description}</small>
                </label>
              ))}
            </fieldset>

            <label>
              <span>가족에게 보일 별칭</span>
              <input
                type="text"
                placeholder="예: 다정한 엄마, 씩씩이"
                value={familyAliasInput}
                onChange={(e) => setFamilyAliasInput(e.target.value)}
                maxLength={NICKNAME_MAX_LENGTH}
                required
              />
              <small className="input-count">{familyAliasInput.length}/{NICKNAME_MAX_LENGTH}자</small>
            </label>

            {notice && <p className="auth-notice">{notice}</p>}
            <button className="auth-submit" type="submit" disabled={loading}>
              {loading ? '연결하는 중…' : authMode === 'family_create' ? '가족 만들기' : '가족과 연결하기'}
              {!loading && <Icon type="arrow" />}
            </button>
          </form>

          <button
            className="onboarding-switch"
            onClick={() => setAuthMode(authMode === 'family_join' ? 'family_create' : 'family_join')}
          >
            {authMode === 'family_join' ? '초대 코드가 없어요 · 새 가족 만들기' : '이미 초대 코드가 있어요 · 참여하기'}
          </button>
        </main>
      </div>
    )
  }

  return (
    <div className="app">
      <Header
        token={token} family={family} user={user} userRole={currentRole} screen={screen}
        go={go} pendingCount={notificationCount} apiStatus={apiStatus} aiReady={aiReady}
        onLogout={handleLogout} onOpenFamily={openInvitePanel}
      />

      {inviteOpen && (
        <FamilyPanel
          family={family}
          user={user}
          roleLabels={roleLabels}
          inviteData={inviteData}
          loading={inviteLoading}
          message={inviteMessage}
          formatDate={formatDate}
          onClose={() => setInviteOpen(false)}
          onCreateInvite={createInvite}
          onCopyInvite={copyInvite}
          onLogout={handleLogout}
        />
      )}

      {notice && <p className="notice">{notice}</p>}

      {token && family && childUser && screen === 'child' && (
        <ChildPage
          emotion={emotion} setEmotion={setEmotion} worry={worry} setWorry={setWorry}
          mode={mode} setMode={setMode} transformAndSend={transformAndSend} loading={loading}
        />
      )}

      {token && family && !childUser && screen === 'parent' && (
        <ParentPage
          pendingDeliveries={pendingDeliveries} currentDelivery={currentDelivery}
          chooseDelivery={chooseDelivery}
          selectedQuestion={selectedQuestion} setSelectedQuestion={setSelectedQuestion}
          recording={recording} record={record} answer={answer} setAnswer={setAnswer}
          polished={polished} setPolished={setPolished} polish={polish} saveAnswer={saveAnswer}
          recommendationReason={recommendationReason} setRecommendationReason={setRecommendationReason}
          answerTone={answerTone} setAnswerTone={setAnswerTone} toneOptions={toneOptions}
          loading={loading}
        />
      )}

      {token && family && screen === 'library' && (
        <LibraryPage library={library} formatDate={formatDate} react={react} childUser={childUser} />
      )}

      <footer>
        <b>슬쩍</b>
        <p>자녀의 조용한 고민과 부모의 지나온 삶을 잇습니다.</p>
        <small>© 2026 SEUL-JJEOCK. All rights reserved.</small>
      </footer>
    </div>
  )
}
