from pathlib import Path
import json
R=Path(__file__).resolve().parent;D=R/'data';D.mkdir(exist_ok=True)
rows=[
('CC_DAILY','춘천 일상돌봄서비스','춘천시',19,64,'care_need|caregiver_absent','재가 돌봄·가사·병원동행·심리지원','주민등록상 주소지 읍면동 행정복지센터','돌봄 필요성과 돌봄자 부재 확인; 소득별 본인부담; 제공여력 확인','https://www.chuncheon.go.kr/new-welfare/life/youth-old/care-service/','2025-05-07','outreach|mobility|care'),
('CC_ELDER','춘천 노인맞춤돌봄서비스','춘천시',65,120,'care_need|benefit_status|duplicate_check','안부확인·사회참여·일상생활지원','주소지 읍면동 행정복지센터','65세 이상 수급자·차상위·기초연금수급자 중 돌봄 필요; 유사서비스 중복 제외','https://www.chuncheon.go.kr/new-welfare/life/senior/care-service/comprehensive-care-service/','2025-05-26','outreach|social|care'),
('CC_INTEGRATED','춘천 의료·요양 통합돌봄','춘천시',0,120,'age65_or_severe_disability|complex_care_need','방문진료·건강관리·일상생활 지원 등의 통합 연계','주소지 읍면동 행정복지센터에 접수 경로 확인','65세 이상 또는 65세 미만 심한 지체·뇌병변장애 등; 복합 지원 필요성 확인','https://www.chuncheon.go.kr/new-welfare/life/senior/care-delivery-system/','2026-current','outreach|medical|care'),
('GN_ISOLATED','서울 고립가구 전담기구 연계','강남구',0,120,'isolation_need_assessment','상담·고립 유형 확인·맞춤 자원 및 커뮤니티 연결','거주지 구청·동주민센터·종합사회복지관','서울시 사업 안내 확인; 강남 담당기관·참여 여력은 신청 시 재확인','https://news.seoul.go.kr/welfare/archives/569275','2026-current','social|outreach'),
('GN_YOUTH','서울 고립·은둔청년 지원','강남구',19,39,'isolation_duration|personal_consent','심리상담 및 맞춤형 회복 프로그램','청년몽땅정보통 공식 지원 안내의 신청 경로 확인','서울 거주19~39세; 관계 단절 등 실제 요건과 지속기간 확인; 집계 활동저조만으로 선정 불가','https://youth.seoul.go.kr/youthConts.do?key=2310100062&sc_bbsCtgrySn=2310200007&sc_bbsStngSn=2212200001&sc_faqCtgryCd=013&sc_pbancSeCd=008','2026-current','social'),
('GN_MEDICAL','강남 의료돌봄센터 방문의료','강남구',0,120,'registered_or_discharge_or_integrated|medical_team_need','다학제 방문 건강평가·회복 및 건강관리','강남구보건소 방문돌봄팀 또는 관할 동 방문간호사','통합돌봄대상·퇴원환자·방문건강관리 등록자 중 필요성 평가; 공개 안내는 무료·연중','https://health.gangnam.go.kr/web/business/visit/sub03.do','2026-05-11','outreach|medical'),
('GN_INTEGRATED','강남구 통합돌봄','강남구',0,120,'age65_or_severe_disability|care_need','보건의료·건강관리·요양·일상생활·주거 연계','주소지 동주민센터·국민건강보험공단 지사 등','65세 이상 또는 65세 미만 심한 지체·뇌병변장애인; 필요도 조사 후 지원계획','https://bokji.gangnam.go.kr/contents/tongtoll1/1/view.do?mid=ID08_01','2026-current','outreach|care')]
records=[]
for sid,name,region,lo,hi,conditions,content,entry,caution,url,version,tags in rows:
 records.append(dict(service_id=sid,name=name,region=region,age_min=lo,age_max=hi,required_checks=conditions.split('|'),service_summary=content,application_entry=entry,eligibility_note=caution,source_url=url,source_version=version,verified_on='2026-10-26',availability='official_description_verified_capacity_unknown',tags=tags.split('|')))
(D/'official_services.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('7 official service descriptions saved')
