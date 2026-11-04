from pathlib import Path
import json
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor,white
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
R=Path(__file__).resolve().parent;cases=json.loads((R.parent/'step6_parts345/results/illustrative_agent_cases.json').read_text(encoding='utf-8'));services={s['service_id']:s for s in json.loads((R.parent/'step6_parts345/data/official_services.json').read_text(encoding='utf-8'))}
pdfmetrics.registerFont(TTFont('K',r'C:\Windows\Fonts\malgun.ttf'));pdfmetrics.registerFont(TTFont('KB',r'C:\Windows\Fonts\malgunbd.ttf'))
W,H=595.276,841.89;ink=HexColor('#183042');muted=HexColor('#526572');accent=HexColor('#166B72');light=HexColor('#EDF5F5');line=HexColor('#DAE3E7')
c=canvas.Canvas(str(R/'preventive_intervention_cards.pdf'),pagesize=(W,H));c.setTitle('AI 에이전트 예방 개입 카드 실제 격자 기반 설계 예시');c.setAuthor('빅콘테스트 AI')
def text(s,x,top,w=523,size=10.2,bold=False,color=ink,maxh=None):
 p=Paragraph(s,ParagraphStyle('p',fontName='KB' if bold else 'K',fontSize=size,leading=size*1.48,textColor=color,wordWrap='CJK',spaceAfter=0));_,h=p.wrap(w,900)
 if maxh is not None and h>maxh:raise ValueError((s[:50],h,maxh))
 p.drawOn(c,x,H-top-h);return h
def rule(top):c.setStrokeColor(line);c.line(36,H-top,559,H-top)
def section(title,top):text(title,36,top,size=10.8,bold=True,color=accent)
def box(x,top,w,h,fill=light):c.setFillColor(fill);c.roundRect(x,H-top-h,w,h,7,fill=1,stroke=0)
for num,case in enumerate(cases,1):
 r=case['observed_grid_context'];out=r['route_code']=='VISIT_OR_MOBILITY_FIRST';age={'20G':'20대','60GU':'60대 이상'}.get(r['AGE'],r['AGE']);route='연결 공백 확인 후 방문·이동 지원 검토' if out else '기존 자원 이용 장벽 확인 후 연결 검토'
 text('AI 에이전트 예방 개입 카드',36,27,size=19,bold=True)
 text(f"{r['REGION']} {r['DONG']}  ·  {age}  ·  {case['case_id']}",36,59,size=12,bold=True)
 text('[확실] 실제 격자 기반 설계 시연 예시  |  LLM 실행 및 개인 상담 기록 없음',36,82,size=8.6,color=muted)
 box(36,106,523,34);text('[추정] '+route,49,113,w=496,size=11,bold=True,color=accent,maxh=23)
 for x,label,v in [(36,'향후 1개월<br/>활동 저조 진입 확률',r['event_probability_next_1m']),(304,'향후 2개월<br/>활동 저조 진입 확률',r['event_probability_next_2m'])]:
  box(x,151,255,62,HexColor('#F3F6F8'));text('[확실] 모델 계산값',x+12,158,w=231,size=8.2,color=muted);text(f'{v*100:.2f}%',x+12,173,w=105,size=22,bold=True);text(label,x+112,176,w=130,size=9.2)
 section('판단 근거',228)
 low=case['low_categories'].replace('|',', ')
 basis=f'[확실] 같은 지역·연령의 전체 모델 격자와 비교해 {low} 중력이 하위 25%에 해당한다.' if out else '[확실] 공통 5종 인프라 중 하위 25%에 해당하는 항목은 없다. 시설이 충분하거나 실제 이용 가능함을 확정한 판정은 아니다.'
 text(basis,36,249,size=10,maxh=44)
 section('연결할 생활 접점 후보',295)
 text('[확실] 시설별 중력 기여로 추린 후보  |  직선거리  |  복지사업 제공기관 확인은 별도',36,315,size=8.2,color=muted)
 y=334
 for node in case['nearby_contact_candidates'][:2]:
  text(escape(node['facility_name'])+f"  /  {node['distance_m']:.0f}m",36,y,w=235,size=10,bold=True,maxh=30);text(escape(str(node['address'])),284,y,w=275,size=8.7,maxh=32);y+=34
 rule(404)
 section('담당자가 먼저 확인할 질문',415)
 if out and r['AGE']=='60GU':question='[추정] 정확한 나이가 65세 이상인가? 외출·돌봄 지원이 필요한가? 방문건강관리 등록·퇴원 이력이 있는가? 본인이 연락·방문을 원하는가?'
 elif out:question='[추정] 실제 이동·외출 제약이 있는가? 일상 돌봄이 필요하고 돌봐줄 사람이 없는가? 어떤 지원을 원하는가? 지역 지표만으로 개인 상태를 판단하지 않는다.'
 else:question='[추정] 주변 거점을 알고 있거나 이용해 본 적이 있는가? 시간·신청 절차·참여 부담 중 장벽은 무엇인가? 원하는 참여 방식과 상담 의향은 무엇인가?'
 text(question,36,437,size=10,maxh=48)
 section('조건 확인 후 연결할 서비스',495)
 ids=(['CC_DAILY'] if r['REGION']=='춘천시' else (['GN_MEDICAL','GN_INTEGRATED'] if r['AGE']=='60GU' else ['GN_YOUTH','GN_ISOLATED']))
 y=517
 for sn,sid in enumerate(ids,1):
  s=services[sid];note={'CC_DAILY':'만19~64세. 돌봄 필요·돌봄자 부재 확인 후 주소지 행정복지센터 상담.','GN_MEDICAL':'등록·퇴원·통합돌봄 등 해당 요건과 방문의료 필요 확인 후 보건소 방문돌봄팀 상담.','GN_INTEGRATED':'65세 이상 또는 별도 장애 요건과 돌봄 필요도 확인 후 동주민센터 상담.','GN_YOUTH':'서울 거주19~39세. 실제 고립·은둔 요건과 지속기간 확인 후 공식 지원 경로 안내.','GN_ISOLATED':'고립 관련 필요 확인 후 동주민센터·종합사회복지관의 상담·연계 경로 확인.'}[sid]
  text('[확실] '+s['name'],36,y,w=450,size=10,bold=True,maxh=20);text(f'<link href="{escape(s["source_url"])}" color="#166B72">공식 안내 {sn}</link>',486,y,w=73,size=8.2);text('[추정] '+note,36,y+19,size=9.1,maxh=30);y+=57
 if len(ids)==1:
  text('[추정] 돌봄 필요가 없다면 이 서비스로 연결하지 않는다. 사회참여를 원할 때는 지역 프로그램을 추가 조회하고, 해당 도서관의 성인 이용·프로그램 조건도 확인한다.',36,577,size=9.2,maxh=43)
 text('[모름] 개인 자격·모집 여력·거점의 사업 참여 여부는 아직 확인되지 않음',36,633,size=8.4,color=muted)
 section('담당자의 다음 행동',655)
 text('[추정] 1. 생활권·의향 확인  →  2. 서비스 조건 대조  →  3. 담당 기관 상담<br/>4. 본인 동의 후 신청 지원  →  5. 실제 이용 여부와 미이용 사유 점검',36,677,size=9.7,maxh=40)
 text('[확실] 현재 상태  미확인  /  연락·신청·이용 완료를 의미하지 않음',36,724,size=9.1,bold=True)
 rule(752)
 text('[확실] 분석 기준 2025년 12월. 이후 위험확률은 관측기간 밖 모델 추정. 서비스 안내 확인 2026년 10월 26일.',36,763,size=7.7,color=muted)
 text('GRID_ID  '+r['GRID_ID'],36,786,w=477,size=7,color=muted);text(f'{num} / 4',523,786,w=36,size=8,color=muted)
 c.showPage()
c.save();print(R/'preventive_intervention_cards.pdf')

