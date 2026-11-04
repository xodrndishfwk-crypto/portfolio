"""Step6 parts 1-2: risk x category gravity routing and facility decomposition.
No LLM/service recommendation is claimed in these two stages.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
P=argparse.ArgumentParser();P.add_argument('--main',type=Path,default=Path(r'./private_inputs/main_work'));P.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'results');a=P.parse_args();B=a.main;O=a.output;O.mkdir(exist_ok=True,parents=True)
bundled=Path(__file__).resolve().parent/'inputs'
S=(bundled/'step5') if (bundled/'step5').exists() else B/'step5_alpha_results/results';A=(bundled/'alpha') if (bundled/'alpha').exists() else B/'initial_pipeline_alpha_results/results';metadata_path=(bundled/'facility_metadata.csv') if (bundled/'facility_metadata.csv').exists() else B/'monthly_grid_results/surrounding_consumption_mass_v4_all_ages/infrastructure_gravity_mass.csv'
CAT={'도서관':'X_도서관','병원':'X_의료','버스정류장':'X_버스정류장','지하철역':'X_지하철역','주민센터':'X_주민센터','공원':'X_공원','사교상권':'X_사교'}
COMMON=['X_도서관','X_의료','X_버스정류장','X_공원','X_사교'];AGE={'20G':'M_20','30G':'M_30','40G':'M_40','50G':'M_50','60GU':'M_60'}
def save(d,n):d.to_csv(O/n,index=False,encoding='utf-8-sig')
def log(x):print(x,flush=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
prioritypath=S/'high_risk_intervention_prescriptions.csv';targets=pd.read_csv(prioritypath,dtype={'GRID_ID':str});assert not targets.duplicated(['GRID_ID','AGE']).any();assert targets.high_risk_target.all()
masspath=A/'mass_all_ages_alpha.csv';mass=pd.read_csv(masspath,dtype={'facility_id':str});mass=mass[mass.READY_FOR_HUFF.astype(str).str.lower().isin(['true','1'])].copy();md=pd.read_csv(metadata_path,dtype={'facility_id':str});assert not mass.facility_id.duplicated().any();assert not md.facility_id.duplicated().any()
extra=[c for c in ['facility_id','address','subcategory','longitude','latitude','source_file','coord_source_status','temporal_status','mass_status'] if c in md];mass=mass.merge(md[extra],on='facility_id',how='left',validate='one_to_one');save(mass,'facility_inventory_alpha.csv')
profiles=[];thresholds=[];refstats=[];allmat={}
log('Classifying per-category exposure against all modelled grids in the same region and age')
for age in AGE:
 matrixpath=A/f'grid_huff_dosage_matrix_{age}.csv';mat=pd.read_csv(matrixpath,dtype={'GRID_ID':str});allmat[age]=mat;tr=targets[targets.AGE.eq(age)];joined=tr.merge(mat[['GRID_ID']+list(CAT.values())],on='GRID_ID',validate='one_to_one');assert len(joined)==len(tr)
 for region,rs in mat.groupby('REGION'):
  q=joined[joined.REGION.eq(region)]
  for cat,col in CAT.items():
   ref=rs[col].dropna();vary=len(ref)>0 and ref.max()-ref.min()>1e-12;cut=float(ref.quantile(.25)) if len(ref) else np.nan
   thresholds.append(dict(REGION=region,AGE=age,category=cat,feature=col,reference_grids=len(rs),nonmissing_grids=len(ref),q25=cut,q50=float(ref.median()) if len(ref) else np.nan,variable=bool(vary),used_for_route=col in COMMON))
   sortedref=np.sort(ref.to_numpy(float))
   for r in q.to_dict('records'):
    v=r[col];valid=pd.notna(v) and vary
    pct=(np.searchsorted(sortedref,v,'left')+np.searchsorted(sortedref,v,'right'))/(2*len(ref)) if valid else np.nan
    state=('low' if v<=cut else 'not_low') if valid else ('missing_exposure' if pd.isna(v) else 'no_variation')
    profiles.append(dict(GRID_ID=r['GRID_ID'],REGION=region,DONG=r['DONG'],AGE=age,category=cat,feature=col,X=v,reference_percentile=pct,q25=cut,gravity_status=state,used_for_route=col in COMMON,event_probability_next_1m=r['event_probability_next_1m']))
prof=pd.DataFrame(profiles);save(prof,'priority_category_gravity_profile.csv');save(pd.DataFrame(thresholds),'gravity_reference_thresholds.csv')
routes=[]
for (grid,age),g in prof.groupby(['GRID_ID','AGE'],sort=False):
 core=g[g.used_for_route];low=core[core.gravity_status.eq('low')];unknown=core[~core.gravity_status.isin(['low','not_low'])];route='VISIT_OR_MOBILITY_FIRST' if len(low) else ('EXISTING_RESOURCE_LINK_FIRST' if not len(unknown) else 'EXPOSURE_REVIEW_REQUIRED')
 routes.append(dict(GRID_ID=grid,AGE=age,route_code=route,response_type='',low_categories='|'.join(low.category),n_low_categories=len(low),unknown_categories='|'.join(unknown.category),route_basis='any of five common infrastructure X <= regional-age q25',transport_low=bool(low.feature.eq('X_버스정류장').any()),medical_low=bool(low.feature.eq('X_의료').any()),social_low=bool(low.feature.eq('X_사교').any())))
route=pd.DataFrame(routes);route['response_type']=route.route_code.map({'VISIT_OR_MOBILITY_FIRST':'연결 공백 확인·방문/이동 지원 우선 검토','EXISTING_RESOURCE_LINK_FIRST':'기존 자원 이용 장벽 확인·연결 우선 검토','EXPOSURE_REVIEW_REQUIRED':'접근성 자료 확인 필요'});cards=targets.merge(route,on=['GRID_ID','AGE'],validate='one_to_one');save(cards,'priority_response_classification.csv');save(cards.groupby(['REGION','AGE','route_code','response_type']).size().rename('n_grid_age').reset_index(),'response_type_summary.csv')
log('Decomposing exact original category gravity, retaining top3 per category plus nearest facility')
candidates=[];decomp=[];nearestrows=[]
for age,mc in AGE.items():
 tr=targets[targets.AGE.eq(age)].reset_index(drop=True);raw=pd.read_csv(A/f'grid_huff_dosage_raw_{age}.csv',dtype={'GRID_ID':str}).set_index('GRID_ID')
 for region,g in tr.groupby('REGION'):
  for cat,col in CAT.items():
   f=mass[mass.region.eq(region)&mass['카테고리'].eq(cat)].reset_index(drop=True)
   if not len(f):
    for r in g.to_dict('records'):decomp.append(dict(GRID_ID=r['GRID_ID'],AGE=age,REGION=region,category=cat,feature=col,n_facilities=0,total_raw_gravity=np.nan,top3_share=np.nan,nearest_distance_m=np.nan,status='no_covered_facilities'))
    continue
   dist=cdist(g[['X_COORD','Y_COORD']],f[['X_COORD','Y_COORD']]);contrib=np.maximum(dist,1.)**-2*f[mc].to_numpy()[None,:];tot=contrib.sum(1);expected=raw.loc[g.GRID_ID,col].to_numpy(float);assert np.allclose(tot,expected,rtol=2e-7,atol=1e-11)
   k=min(3,len(f));top=np.argsort(-contrib,axis=1,kind='stable')[:,:k];near=np.argmin(dist,axis=1)
   for j,r in enumerate(g.to_dict('records')):
    shares=contrib[j,top[j]]/tot[j];decomp.append(dict(GRID_ID=r['GRID_ID'],AGE=age,REGION=region,category=cat,feature=col,n_facilities=len(f),total_raw_gravity=float(tot[j]),top3_share=float(shares.sum()),nearest_distance_m=float(dist[j,near[j]]),nearest_facility_id=f.iloc[near[j]].facility_id,status='covered',reproduction_abs_error=float(abs(tot[j]-expected[j]))))
    chosen=list(top[j]);
    if near[j] not in chosen:chosen.append(near[j])
    for fi in chosen:
     z=f.iloc[fi];name=str(z['명칭']);addr=str(z.get('address',''));rank=int(np.where(top[j]==fi)[0][0]+1) if fi in top[j] else None
     candidates.append(dict(GRID_ID=r['GRID_ID'],AGE=age,REGION=region,DONG=r['DONG'],category=cat,feature=col,facility_id=z.facility_id,facility_name=name,address=addr,subcategory=z.get('subcategory',''),facility_x=z.X_COORD,facility_y=z.Y_COORD,longitude=z.get('longitude',np.nan),latitude=z.get('latitude',np.nan),gravity_rank=rank,is_nearest=bool(fi==near[j]),distance_m=float(dist[j,fi]),distance_basis='Euclidean EPSG:5179, not walking route',beyond_1km=bool(dist[j,fi]>1000),M_alpha=float(z[mc]),raw_gravity_contribution=float(contrib[j,fi]),category_contribution_share=float(contrib[j,fi]/tot[j]),resource_role='private_life_contact' if cat=='사교상권' else ('transport_access_node' if cat in ['버스정류장','지하철역'] else 'potential_public_or_medical_contact'),service_verified=False,service_matching_status='DEFERRED_TO_PART3',generic_name_flag=bool(name in ['공원','도서관','병원','nan','']),source_file=z.get('source_file',''),temporal_status=z.get('temporal_status','')))
 log(age+' complete')
cand=pd.DataFrame(candidates).merge(prof[['GRID_ID','AGE','category','gravity_status']],on=['GRID_ID','AGE','category'],validate='many_to_one').merge(route[['GRID_ID','AGE','route_code']],on=['GRID_ID','AGE'],validate='many_to_one');assert not cand.duplicated(['GRID_ID','AGE','category','facility_id']).any();save(cand,'facility_connection_candidates.csv');dec=pd.DataFrame(decomp).merge(prof[['GRID_ID','AGE','category','gravity_status']],on=['GRID_ID','AGE','category'],validate='one_to_one');save(dec,'gravity_decomposition_audit.csv')
# Longlist is joined before ranking facilities, enabling later service eligibility search.
hubs=cand.groupby(['REGION','category','facility_id','facility_name','address'],dropna=False).agg(n_target_grid_age=('GRID_ID','size'),n_unique_target_grids=('GRID_ID','nunique'),mean_distance_m=('distance_m','mean'),median_category_share=('category_contribution_share','median'),n_low_exposure_targets=('gravity_status',lambda s:int(s.eq('low').sum()))).reset_index().sort_values(['REGION','n_target_grid_age'],ascending=[True,False]);save(hubs,'facility_target_coverage_summary.csv')
coverage=dec[dec.status.eq('covered')];report={'priority_grid_age_rows':len(targets),'unique_grids':int(targets.GRID_ID.nunique()),'category_profile_rows':len(prof),'candidate_rows':len(cand),'unique_candidate_facilities':int(cand.facility_id.nunique()),'decomposition_reproduced_rows':len(coverage),'max_gravity_reproduction_abs_error':float(coverage.reproduction_abs_error.max()),'route_counts':cards.route_code.value_counts().to_dict(),'threshold':'regional age category 25th percentile, all modeled grids, not just priority subset; any low of five common types => visit/mobility review','category_absence':'missing not zero; no variation not classified as low','scope':'Step6 parts1-2 only; no LLM execution, no service eligibility verification, no installation simulation','alpha_interpretation':'negative activation calibrated mass is a model-derived accessibility score, not facility quality or verified service capacity','risk_baseline':'December 2025; inherited model extrapolation, not October 2026 current risk','no_source_modification':True,'input_sha256':{'priority':sha(prioritypath),'alpha_mass':sha(masspath),'facility_metadata':sha(metadata_path)}}
(O/'run_metadata.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');log(json.dumps(report,ensure_ascii=True));log('COMPLETE')
