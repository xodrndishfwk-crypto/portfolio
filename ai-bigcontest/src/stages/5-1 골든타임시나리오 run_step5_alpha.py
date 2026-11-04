"""Step5: original-pipeline alpha AFT -> conditional time/risk/priority/scenarios.
No original files are modified. No youth-center feature is used.
"""
from pathlib import Path
import argparse,json,hashlib,shutil
import numpy as np
import pandas as pd
P=argparse.ArgumentParser();P.add_argument('--base',type=Path,default=Path(r'./private_inputs/main_work\monthly_grid_results'));P.add_argument('--alpha',type=Path,default=Path(__file__).resolve().parent/'inputs');P.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'results');args=P.parse_args();B=args.base;A=args.alpha;O=args.output;O.mkdir(parents=True,exist_ok=True)
def save(d,n):d.to_csv(O/n,index=False,encoding='utf-8-sig')
def log(x):print(x,flush=True)
def filehash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
meta=json.loads((A/'run_metadata.json').read_text(encoding='utf-8'));models=json.loads((A/'full_refit_models.json').read_text(encoding='utf-8'));features=meta['features']
assert not any('청년' in x for x in features)
# Numerically stable conditional quantile and conditional probability.
def remaining(eta,rho,t):
 t=np.asarray(t,float);logtr=np.where(t>0,rho*np.log(np.maximum(t,1e-300)),-np.inf);logtotal=np.logaddexp(logtr,rho*eta+np.log(np.log(2.)));logq=logtotal/rho
 return np.where(t>0,t*np.expm1(np.maximum(logq-np.log(np.maximum(t,1e-300)),0)),np.exp(logq))
def probability(eta,rho,t,h):
 t=np.asarray(t,float);t1=t+h;diff=np.where(t>0,t1**rho*(-np.expm1(rho*np.log(np.maximum(t,1e-300)/t1))),t1**rho);loghaz=np.log(np.maximum(diff,1e-300))-rho*eta
 return -np.expm1(-np.exp(np.clip(loghaz,-745,700)))
# Formula checks: probabilities increase with horizon, conditional median yields 50%.
et=np.array([0.,2.,4.,8.]);rh=np.array([.7,1.,1.3,2.]);tt=np.array([0.,1.,3.,5.]);q=remaining(et,rh,tt);assert np.allclose(probability(et,rh,tt,q),.5,rtol=1e-9,atol=1e-10);assert np.all(probability(et,rh,tt,2)>=probability(et,rh,tt,1))
log('Loading original scores/audit and frozen alpha AFT models')
scorepath=next(B.rglob('04_all_scores.csv'));auditpath=B/'step3_survival_results/results/patient_survival_audit.csv';audit=pd.read_csv(auditpath,dtype={'GRID_ID':str})
cols=['GRID_ID','STD_YM','AGE','REGION','DONG','X_COORD','Y_COORD','FLOW','ACTIVITY_RESIDUAL','SELECTED'];scores=pd.read_csv(scorepath,usecols=cols,dtype={'GRID_ID':str});assert not scores.duplicated(['GRID_ID','AGE','STD_YM']).any();assert not audit.duplicated(['GRID_ID','AGE']).any()
fields=[];coeff=[];matrices={}
for age,m in models.items():
 d=pd.read_csv(A/f'grid_huff_dosage_matrix_{age}.csv',dtype={'GRID_ID':str});matrices[age]=d;xx=np.c_[d[features[:-1]].to_numpy(),d.REGION.eq('춘천시').to_numpy(float)];theta=np.array(m['theta']);sd=np.array(m['sd']);mu=np.array(m['mu']);beta=theta[1:-1]/sd;eta=np.c_[np.ones(len(xx)),(xx-mu)/sd]@theta[:-1];z=d[['GRID_ID','AGE','REGION','DONG']].copy();z['eta']=eta;z['shape']=np.exp(theta[-1]);fields.append(z)
 for f,b in zip(features,beta):coeff.append(dict(AGE=age,term=f,beta=b))
fields=pd.concat(fields,ignore_index=True);scores=scores.merge(fields,on=['GRID_ID','AGE','REGION','DONG'],how='left',validate='many_to_one');assert scores.eta.notna().all()
scores=scores.merge(audit[['GRID_ID','AGE','status','duration_T','last_followup_month','event_month']],on=['GRID_ID','AGE'],how='left',validate='many_to_one');assert scores.status.notna().all();scores['elapsed_months']=scores.STD_YM.map({202500+i:i-7 for i in range(7,13)});assert scores.elapsed_months.notna().all();t=scores.elapsed_months
scores['prediction_status']='excluded_'+scores.status
end=scores.status.eq('censored_end');before_event=scores.status.eq('event')&(t<scores.duration_T);before_missing=scores.status.eq('censored_missing')&(t<=scores.duration_T)
scores.loc[end|before_event|before_missing,'prediction_status']='eligible_event_free';scores.loc[scores.status.eq('event')&(t>=scores.duration_T),'prediction_status']='event_already_observed';scores.loc[scores.status.eq('censored_missing')&(t>scores.duration_T),'prediction_status']='followup_unavailable'
eligible=scores.prediction_status.eq('eligible_event_free');ix=scores.index[eligible];eta=scores.loc[ix,'eta'].to_numpy();rho=scores.loc[ix,'shape'].to_numpy();elapsed=scores.loc[ix,'elapsed_months'].to_numpy(float)
for c in ['remaining_median_months','event_probability_next_1m','event_probability_next_2m']:scores[c]=np.nan
scores.loc[ix,'remaining_median_months']=remaining(eta,rho,elapsed);scores.loc[ix,'event_probability_next_1m']=probability(eta,rho,elapsed,1);scores.loc[ix,'event_probability_next_2m']=probability(eta,rho,elapsed,2)
scores['available_observed_horizon_months']=5-scores.elapsed_months;scores['next_1m_extrapolated']=eligible&(scores.elapsed_months+1>5);scores['next_2m_extrapolated']=eligible&(scores.elapsed_months+2>5);scores['median_beyond_observed_horizon']=eligible&(scores.remaining_median_months>scores.available_observed_horizon_months)
scores['high_risk_target']=False;latest=scores.STD_YM.max();thresholds=[]
for (r,a),g in scores[(scores.STD_YM==latest)&eligible].groupby(['REGION','AGE']):
 threshold=g.remaining_median_months.quantile(.05);target=g.remaining_median_months.le(threshold);scores.loc[g.index[target],'high_risk_target']=True;thresholds.append(dict(REGION=r,AGE=a,eligible=len(g),median_time_5pct_threshold=threshold,selected=int(target.sum()),selected_fraction=float(target.mean())))
save(pd.DataFrame(thresholds),'priority_thresholds.csv');save(pd.DataFrame(coeff),'aft_feature_coefficients_used.csv')
# Exact original bus scenario, plus comparable +0.1 scenarios for fitted common infrastructure.
# Subway/resident center have X but are absent from fitted primary AFT; never assign zero coefficients.
scenarios=[('bus_plus_0_2','X_버스정류장',.2)]+[(f'{f}_plus_0_1',f,.1) for f in features if f.startswith('X_')]
current=scores[scores.STD_YM.eq(latest)].copy();targets=current[current.high_risk_target].copy();scenario_frames=[];bc=pd.DataFrame(coeff).set_index(['AGE','term']).beta
for name,f,delta in scenarios:
 ss=targets[['GRID_ID','AGE','REGION','DONG','eta','shape','elapsed_months','remaining_median_months','event_probability_next_1m','event_probability_next_2m']].copy();ss['scenario']=name;ss['feature']=f;ss['delta_X']=delta;ss['beta']=ss.AGE.map({a:bc.loc[(a,f)] for a in models});neweta=ss.eta+ss.beta*delta
 ss['scenario_remaining_median_months']=remaining(neweta.to_numpy(),ss['shape'].to_numpy(),ss.elapsed_months.to_numpy());ss['delta_remaining_months']=ss.scenario_remaining_median_months-ss.remaining_median_months;ss['scenario_probability_next_1m']=probability(neweta.to_numpy(),ss['shape'].to_numpy(),ss.elapsed_months.to_numpy(),1);ss['scenario_probability_next_2m']=probability(neweta.to_numpy(),ss['shape'].to_numpy(),ss.elapsed_months.to_numpy(),2);ss['delta_probability_next_1m']=ss.scenario_probability_next_1m-ss.event_probability_next_1m
 vals=[];upper=[]
 for age in models:
  d=matrices[age];q=d[['GRID_ID','REGION',f]].copy();q['AGE']=age;vals.append(q);bound=d.merge(audit.loc[audit.AGE.eq(age)&audit.status.isin(['event','censored_end','censored_missing']),['GRID_ID']],on='GRID_ID').groupby('REGION')[f].max().to_dict();upper.extend([(age,r,v) for r,v in bound.items()])
 ss=ss.merge(pd.concat(vals),on=['GRID_ID','AGE','REGION'],validate='one_to_one');bounds={(a,r):v for a,r,v in upper};ss['scenario_X']=ss[f]+delta;ss['exceeds_observed_X_max']=ss.scenario_X>np.array([bounds[(a,r)] for a,r in zip(ss.AGE,ss.REGION)]);ss['is_causal_effect']=False;ss['beyond_time_observation']=True;scenario_frames.append(ss)
sc=pd.concat(scenario_frames,ignore_index=True);save(sc,'high_risk_infrastructure_scenarios.csv');bus=sc[sc.scenario.eq('bus_plus_0_2')][['GRID_ID','AGE','delta_remaining_months','scenario_probability_next_1m','exceeds_observed_X_max']].rename(columns={'delta_remaining_months':'scenario_bus_delta_T','scenario_probability_next_1m':'scenario_bus_probability_next_1m','exceeds_observed_X_max':'scenario_bus_exceeds_observed_X_max'});targets=targets.merge(bus,on=['GRID_ID','AGE'],validate='one_to_one');targets=targets.sort_values(['REGION','AGE','remaining_median_months']);save(targets,'high_risk_intervention_prescriptions.csv')
save(scores,'04_aft_golden_time_scores.csv');save(current,'current_202512_golden_time_scores.csv');save(fields,'grid_age_model_prognosis.csv')
def summary(keys):
 d=scores.copy();d['eligible_flag']=d.prediction_status.eq('eligible_event_free');return d.groupby(keys).agg(total_grids=('GRID_ID','size'),eligible_grids=('eligible_flag','sum'),high_risk_grids=('high_risk_target','sum'),median_remaining_months=('remaining_median_months','median'),mean_prob_1m=('event_probability_next_1m','mean'),mean_prob_2m=('event_probability_next_2m','mean')).reset_index()
save(summary(['REGION','DONG','AGE','STD_YM']),'dong_age_month_summary.csv');save(summary(['REGION','AGE','STD_YM']),'region_age_month_summary.csv');save(sc.groupby(['REGION','AGE','scenario','feature','delta_X']).agg(n=('GRID_ID','size'),median_delta_months=('delta_remaining_months','median'),median_delta_probability_1m=('delta_probability_next_1m','median'),exceeds_X_max=('exceeds_observed_X_max','sum')).reset_index(),'scenario_summary.csv')
assert np.isfinite(scores.loc[eligible,['remaining_median_months','event_probability_next_1m','event_probability_next_2m']]).all().all();assert scores.loc[~eligible,'remaining_median_months'].isna().all();assert (scores.loc[eligible,'event_probability_next_2m']>=scores.loc[eligible,'event_probability_next_1m']).all();assert scores.loc[eligible,'event_probability_next_2m'].between(0,1).all();assert len(current)==current[['GRID_ID','AGE']].drop_duplicates().shape[0];assert not any('youth' in c or '청년' in c for c in scores.columns)
report={'rows':len(scores),'latest_month':int(latest),'latest_eligible':int(current.prediction_status.eq('eligible_event_free').sum()),'high_risk_rows':len(targets),'unique_high_risk_grids':int(targets.GRID_ID.nunique()),'scenario_rows':len(sc),'no_youth_center':True,'formula_median_probability_0_5_check':True,'probability_range_monotonicity_and_status_checks':True,'source':str(B),'alpha_source':str(A),'AFT_specification':'five pooled age models, common five infrastructure X plus region indicator; no A/B/C comparison added','selection_rule':'latest month eligible, within region-age lowest remaining median 5%; ties retained','calendar':'July=0, December=5; next1/2m at December = Jan/Feb 2026, model extrapolation','interpretation':'low-activity-label onset not diagnosed individual isolation; scenario delta model sensitivity not causal impact','inputs_sha256':{'scores':filehash(scorepath),'audit':filehash(auditpath),'models':filehash(A/'full_refit_models.json'),'alpha_meta':filehash(A/'run_metadata.json')}}
(O/'run_metadata.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(O/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');log(json.dumps(report,ensure_ascii=True));log(pd.DataFrame(thresholds).to_string(index=False));log('COMPLETE')
