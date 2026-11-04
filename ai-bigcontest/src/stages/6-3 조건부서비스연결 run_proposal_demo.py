"""Proposal demonstration: deterministic evidence retrieval/case rendering and site scenarios.
No LLM or OpenAI API calls. LLM tool design is supplied separately.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
P=argparse.ArgumentParser();P.add_argument('--main',type=Path,default=Path(r'./private_inputs/main_work'));P.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'results');args=P.parse_args();R=Path(__file__).resolve().parent;O=args.output;O.mkdir(parents=True,exist_ok=True);bundle=R/'inputs';B=args.main
S=bundle/'step6' if (bundle/'step6').exists() else R.parent/'step6_parts12/results';A=bundle/'alpha' if (bundle/'alpha').exists() else B/'initial_pipeline_alpha_results/results';parampath=bundle/'normalization_parameters.csv' if bundle.exists() else B/'monthly_grid_results/step4_aft_and_3d_gravity/inputs/normalization_parameters.csv'
def save(d,n):d.to_csv(O/n,index=False,encoding='utf-8-sig')
def log(x):print(x,flush=True)
services=json.loads((R/'data/official_services.json').read_text(encoding='utf-8'));save(pd.DataFrame(services).assign(required_checks=lambda d:d.required_checks.str.join('|'),tags=lambda d:d.tags.str.join('|')),'verified_service_catalog.csv')
targets=pd.read_csv(S/'priority_response_classification.csv',dtype={'GRID_ID':str});prof=pd.read_csv(S/'priority_category_gravity_profile.csv',dtype={'GRID_ID':str});cand=pd.read_csv(S/'facility_connection_candidates.csv',dtype={'GRID_ID':str,'facility_id':str});inventory=pd.read_csv(S/'facility_inventory_alpha.csv',dtype={'facility_id':str});coverage=pd.read_csv(S/'facility_target_coverage_summary.csv',dtype={'facility_id':str});assert len(targets)==2125
AGE={'20G':(20,29,'M_20'),'30G':(30,39,'M_30'),'40G':(40,49,'M_40'),'50G':(50,59,'M_50'),'60GU':(60,120,'M_60')}
links=[];plans=[]
for r in targets.to_dict('records'):
 lo,hi,_=AGE[r['AGE']];outreach=r['route_code']=='VISIT_OR_MOBILITY_FIRST';low='' if pd.isna(r['low_categories']) else r['low_categories'];questions=[]
 questions=['실제 생활권·연락 가능 여부와 본인 의향 확인','정확한 나이·돌봄 필요·기존 이용서비스 확인']
 questions+=['외출·이동이 어려운지, 방문형 지원을 원하는지 확인'] if outreach else ['주변 시설 이용 경험·이용하지 않는 이유·원하는 참여 방식 확인']
 matched=[]
 for sv in services:
  if sv['region']!=r['REGION'] or hi<sv['age_min'] or lo>sv['age_max']:continue
  agecheck='AGE_WITHIN_RANGE_NOT_PERSON_VERIFIED' if lo>=sv['age_min'] and hi<=sv['age_max'] else 'EXACT_AGE_REQUIRED'
  score=(2 if outreach and 'outreach' in sv['tags'] else 0)+(2 if not outreach and 'social' in sv['tags'] else 0)+(1 if r.get('medical_low',False) and 'medical' in sv['tags'] else 0)
  matched.append((score,sv['service_id']))
  links.append(dict(GRID_ID=r['GRID_ID'],AGE=r['AGE'],REGION=r['REGION'],route_code=r['route_code'],service_id=sv['service_id'],service_name=sv['name'],proposal_priority_score=score,eligibility_status='CONDITIONAL_CANDIDATE_NOT_APPROVED',age_check=agecheck,unverified_conditions='|'.join(sv['required_checks']),source_url=sv['source_url'],verified_on=sv['verified_on'],application_entry=sv['application_entry'],source_version=sv['source_version'],capacity_confirmed=False))
 matched.sort(key=lambda x:(-x[0],x[1]));plans.append(dict(GRID_ID=r['GRID_ID'],AGE=r['AGE'],REGION=r['REGION'],DONG=r['DONG'],route_code=r['route_code'],low_categories=low,event_probability_next_1m=r['event_probability_next_1m'],first_questions=' | '.join(questions),service_candidate_ids='|'.join(s for _,s in matched),first_action='담당자 현장확인·방문/이동 지원 필요 조사' if outreach else '담당자 이용 장벽 확인·기존 서비스 연결 상담',followup='동의 기반 연락·신청·이용 여부 기록 후 담당자가 다음 행동 결정',output_type='RULE_BASED_PROPOSAL_NOT_LLM_EXECUTION'))
links=pd.DataFrame(links);save(links,'conditional_service_links.csv');plans=pd.DataFrame(plans);save(plans,'response_proposal_cards.csv')
# Four real grid contexts. Person facts below remain hypothetical and are not fed into actual eligibility decisions.
selected=targets.sort_values('event_probability_next_1m',ascending=False).groupby(['REGION','route_code'],sort=True).head(1);examples=[]
for n,r in enumerate(selected.to_dict('records'),1):
 cs=cand[(cand.GRID_ID==r['GRID_ID'])&(cand.AGE==r['AGE'])].sort_values(['category','gravity_rank']).groupby('category').head(1)
 ls=links[(links.GRID_ID==r['GRID_ID'])&(links.AGE==r['AGE'])].sort_values('proposal_priority_score',ascending=False)
 hypothetical='정확한 나이·돌봄 필요·동의 여부를 담당자가 확인한다는 가상 상담 분기. 실제 개인자료 없음.'
 examples.append(dict(case_id=f'CASE_{n}',observed_grid_context={k:r[k] for k in ['GRID_ID','AGE','REGION','DONG','route_code','event_probability_next_1m','event_probability_next_2m']},low_categories='' if pd.isna(r['low_categories']) else r['low_categories'],nearby_contact_candidates=cs[['facility_id','facility_name','category','distance_m','address']].to_dict('records'),conditional_services=ls[['service_id','service_name','age_check','unverified_conditions','source_url']].to_dict('records'),field_input_status=hypothetical,illustrative_agent_output='위험 지역 지표로 개인을 확진하지 않고 담당자가 실제 상황을 확인한 뒤 조건을 충족하는 자원으로 연결합니다.',execution_status='DESIGNED_EXAMPLE_NOT_ACTUAL_LLM_RESPONSE'))
(O/'illustrative_agent_cases.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf-8')
log('Conditional service mapping complete; calculating physical site scenarios')
# Up to 12 real public contact locations per region: high-demand coverage and sites near remote high-risk target grids.
sites=[]
for region in targets.REGION.unique():
 pool=coverage[(coverage.REGION==region)&coverage.category.isin(['도서관','공원','주민센터'])].sort_values('n_target_grid_age',ascending=False)
 chosen=list(pool.facility_id.head(6))
 rr=targets[(targets.REGION==region)&targets.medical_low].sort_values('event_probability_next_1m',ascending=False)
 for r in rr.to_dict('records'):
  cc=cand[(cand.GRID_ID==r['GRID_ID'])&(cand.AGE==r['AGE'])&cand.category.isin(['도서관','공원','주민센터'])].sort_values('distance_m')
  if len(cc) and cc.iloc[0].facility_id not in chosen:chosen.append(cc.iloc[0].facility_id)
  if len(chosen)>=12:break
 for fid in chosen:
  f=inventory[inventory.facility_id.eq(fid)].iloc[0];sites.append(dict(site_id=f'PILOT_{fid}',host_facility_id=fid,site_name=f['명칭'],host_category=f['카테고리'],REGION=region,site_x=f.X_COORD,site_y=f.Y_COORD,address=f.get('address',''),proposal='가상 찾아가는 건강·복지 접점 추가',permission_status='NOT_CONFIRMED',provider_status='NOT_ASSIGNED'))
sites=pd.DataFrame(sites);save(sites,'hypothetical_site_candidates.csv');params=pd.read_csv(parampath).set_index('column');q=params.loc['X_의료'];coefs=pd.read_csv(B/'initial_pipeline_alpha_results/results/selected_full_refit_coefficients.csv') if not (A/'selected_full_refit_coefficients.csv').exists() else pd.read_csv(A/'selected_full_refit_coefficients.csv')
def prob(eta,rho,t,h):return -np.expm1(-np.exp(np.clip(np.log((t+h)**rho-t**rho)-rho*eta,-745,700)))
scenario_rows=[]
for age,(lo,hi,mc) in AGE.items():
 raw=pd.read_csv(A/f'grid_huff_dosage_raw_{age}.csv',dtype={'GRID_ID':str}).set_index('GRID_ID');matrix=pd.read_csv(A/f'grid_huff_dosage_matrix_{age}.csv',dtype={'GRID_ID':str}).set_index('GRID_ID');beta=float(coefs[(coefs.AGE==age)&coefs.term.eq('X_의료')].beta.iloc[0])
 for region,g in targets[targets.AGE.eq(age)].groupby('REGION'):
  ss=sites[sites.REGION.eq(region)];m=float(inventory[(inventory.region==region)&inventory['카테고리'].eq('병원')][mc].median());assert m>0
  dist=cdist(g[['X_COORD','Y_COORD']],ss[['site_x','site_y']]);delta=np.maximum(dist,1.)**-2*m;raw0=raw.loc[g.GRID_ID,'X_의료'].to_numpy();x0=matrix.loc[g.GRID_ID,'X_의료'].to_numpy();xref=matrix[matrix.REGION.eq(region)].X_의료;cut=float(xref.quantile(.25));basep=prob(g.eta.to_numpy(),g['shape'].to_numpy(),5.,1.)
  assert np.allclose(basep,g.event_probability_next_1m,atol=1e-10)
  for si,s in enumerate(ss.to_dict('records')):
   xnew=(np.log1p((raw0+delta[:,si])/q.positive_raw_median)-q.log_min)/(q.log_max-q.log_min);dx=xnew-x0;newp=prob(g.eta.to_numpy()+beta*dx,g['shape'].to_numpy(),5.,1.);relative=delta[:,si]/raw0
   for j,r in enumerate(g.to_dict('records')):scenario_rows.append(dict(site_id=s['site_id'],GRID_ID=r['GRID_ID'],AGE=age,REGION=region,DONG=r['DONG'],distance_to_site_m=float(dist[j,si]),assumed_new_M=m,mass_basis='one regional age medical median calibrated M, not measured mobile capacity',medical_low_before=bool(x0[j]<=cut),raw_medical_before=float(raw0[j]),delta_raw_medical=float(delta[j,si]),relative_raw_medical_gain=float(relative[j]),X_medical_before=float(x0[j]),X_medical_after=float(xnew[j]),delta_X_medical=float(dx[j]),crosses_q25=bool(x0[j]<=cut and xnew[j]>cut),material_access_gain=bool(relative[j]>=.1),prob_1m_before=float(basep[j]),prob_1m_after=float(newp[j]),delta_prob_1m=float(newp[j]-basep[j]),exceeds_reference_X_max=bool(xnew[j]>xref.max()),model_scenario_only=True))
sc=pd.DataFrame(scenario_rows);assert sc.delta_raw_medical.gt(0).all();assert sc.prob_1m_after.between(0,1).all();save(sc,'site_grid_accessibility_scenarios.csv')
summ=[]
for sid,g in sc.groupby('site_id'):
 low=g[g.medical_low_before];hit=low[low.material_access_gain];summ.append(dict(site_id=sid,n_target_grid_age=len(g),n_medical_low_grid_age=len(low),n_medical_low_gain10pct=len(hit),unique_low_grids_gain10pct=hit.GRID_ID.nunique(),n_medical_low_cross_q25=int(low.crosses_q25.sum()),median_relative_medical_gain=float(g.relative_raw_medical_gain.median()),median_risk_delta_percentage_points=float(g.delta_prob_1m.median()*100),n_exceeds_X_max=int(g.exceeds_reference_X_max.sum()),ranking_basis='medical-low grid-age count with raw accessibility >=10% gain; not expected persons helped'))
summ=pd.DataFrame(summ).merge(sites,on='site_id',validate='one_to_one').sort_values(['REGION','n_medical_low_gain10pct','n_medical_low_cross_q25'],ascending=[True,False,False]);summ['region_rank']=summ.groupby('REGION').cumcount()+1;save(summ,'site_scenario_comparison.csv');report={'priority_grid_age':len(targets),'official_service_descriptions':len(services),'conditional_links':len(links),'illustrative_real_grid_cases':len(examples),'candidate_sites':len(sites),'site_grid_age_scenario_rows':len(sc),'LLM_executed':False,'API_used':False,'all_person_eligibility_pending':bool(links.eligibility_status.eq('CONDITIONAL_CANDIDATE_NOT_APPROVED').all()),'service_check_date':'2026-10-26','risk_base_date':'2025-12; applying 2026 service catalog is proposal demonstration, not historical service availability validation','scenario':'co-locate a hypothetical temporary medical-contact node at actual facility coordinates; regional age medical median calibrated mass; fixed original normalization and AFT coefficients','no_real_new_service_claim':True,'ranking':'among 24 preselected sites only, no global optimum or budget equality claim'}
(O/'run_metadata.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');log(json.dumps(report));log(summ[['REGION','site_name','address','n_medical_low_gain10pct','unique_low_grids_gain10pct','n_medical_low_cross_q25','region_rank']].head(4).to_json(orient='records',force_ascii=True));log('COMPLETE')
