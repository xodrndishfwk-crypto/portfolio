import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import json,hashlib,importlib.util,math
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist
from scipy.optimize import minimize
from scipy.stats import rankdata
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,default=Path(r'./private_inputs/main_work\monthly_grid_results'));parser.add_argument('--sources',type=Path,default=Path(__file__).resolve().parent.parent/'sources');args=parser.parse_args();BASE=args.base
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
SRC=args.sources;INP=BASE/'step4_aft_and_3d_gravity/inputs'
spec=importlib.util.spec_from_file_location('original',BASE/'step4_aft_and_3d_gravity/run_step4_aft.py');aft=importlib.util.module_from_spec(spec);spec.loader.exec_module(aft)
AGES=aft.AGES;STRENGTHS=[-2.,-1.,-.5,0.,.5,1.,2.];RADII=[300.,800.]
def save(d,n):d.to_csv(OUT/n,index=False,encoding='utf-8-sig')
def log(x):print(x,flush=True)
def auc(y,p):
 y=np.asarray(y,bool);n=y.sum();m=len(y)-n
 return float((rankdata(p)[y].sum()-n*(n+1)/2)/(n*m)) if n*m else float('nan')
def fit(A,L,U):
 mu=A.mean(0);sd=A.std(0);sd[sd<1e-12]=1;X=np.c_[np.ones(len(A)),(A-mu)/sd]
 f=minimize(aft.objgrad,np.r_[math.log(10),np.zeros(A.shape[1]),0.],args=(X,L,U),jac=True,method='BFGS',options={'maxiter':800,'gtol':1e-5})
 grad=float(np.max(np.abs(f.jac)))
 if not np.isfinite(f.fun) or grad>.05:raise RuntimeError(str(f.message)+' gradient='+str(grad))
 return {'theta':f.x,'mu':mu,'sd':sd,'gradient':grad}
def evaluate(m,A,L,U):
 X=np.c_[np.ones(len(A)),(A-m['mu'])/m['sd']];eta=X@m['theta'][:-1];rho=np.exp(m['theta'][-1]);p=-np.expm1(-np.exp(np.clip(rho*(np.log(5)-eta),-50,50)))
 known=np.isfinite(U)|(L>=5);y=np.isfinite(U[known]).astype(int)
 return {'interval_nll':float(aft.objgrad(m['theta'],X,L,U)[0]/len(A)),'auc_5m':auc(y,p[known]),'brier_5m':float(np.mean((p[known]-y)**2)),'n':len(A),'known_5m':int(known.sum())},p
G=pd.read_csv(INP/'grid_locations.csv',dtype={'GRID_ID':str});M=pd.read_csv(INP/'mass_all_ages.csv',dtype={'facility_id':str});M=M[M.READY_FOR_HUFF.astype(str).str.lower().isin(['true','1'])].reset_index(drop=True)
lab=pd.read_csv(INP/'patient_survival_interval_labels.csv',dtype={'GRID_ID':str});P=pd.read_csv(INP/'normalization_parameters.csv').set_index('column')
assert not lab.duplicated(['GRID_ID','AGE']).any()
G['spatial_cell']=G.apply(lambda r:f'{r.REGION}|{int(np.floor(r.X_COORD/500))}|{int(np.floor(r.Y_COORD/500))}',axis=1)
def split(k):
 u=int(hashlib.sha256(('alpha-v1|'+k).encode()).hexdigest()[:8],16)%100
 return 'train' if u<60 else ('validation' if u<80 else 'test')
G['split']=G.spatial_cell.map(split);save(G[['GRID_ID','REGION','spatial_cell','split']],'spatial_split.csv')
log('Reading July card data1 only')
cardpath=next(SRC.glob('*1.txt'));cards=[]
for d in pd.read_csv(cardpath,sep='\t',encoding='cp949',dtype={'TA_YMD':str},chunksize=200000):
 d=d[d.TA_YMD.str.startswith('202507')].copy();d['age']=pd.to_numeric(d.AGE_CCD.str.extract(r'(\d+)')[0],errors='coerce');d=d[d.age.between(20,90)&d.SEX_CCD.ne('법인')];d['REGION']=d.MCT_SGG_CD.map({'서울 강남구':'강남구','강원 춘천시':'춘천시'});d['weekend']=pd.to_datetime(d.TA_YMD).dt.dayofweek.ge(5);cards.append(d)
card=pd.concat(cards,ignore_index=True)
mapping={'도서관':['서점','독서실'],'병원':['보건소','일반병원','종합병원','치과병원','한의원'],'사교상권':['커피전문점','유흥업소','한식','양식','일식','중식','기타요식'],'공원':['스포츠시설','헬스장','종합레저타운/놀이동산']}
contact=['커피전문점','한식','양식','일식','중식','기타요식','제과점','편의점','서점','스포츠시설','헬스장','영화/공연'];times=['00_05','06_11','12_17','18_23'];profiles={};rows=[]
for region in sorted(G.REGION.unique()):
 for ai,age in enumerate(AGES):
  an=20+ai*10;d=card[(card.REGION==region)&((card.age==an) if ai<4 else (card.age>=60))]
  for cat in aft.CAT:
   inds=mapping.get(cat,contact);c=d[d.MCT_RY_CD.isin(inds)];fallback=False
   if c.USE_CNT.sum()<=0:c=d;fallback=True
   counts=c.groupby('TIME_GB').USE_CNT.sum().reindex(times,fill_value=0).to_numpy(float);weights=counts/counts.sum();wk=c.loc[c.weekend,'USE_CNT'].sum()/8;wd=c.loc[~c.weekend,'USE_CNT'].sum()/23;ws=float(wk/(wk+wd));profiles[(region,age,cat)]=(weights,ws)
   rows.append(dict(REGION=region,AGE=age,category=cat,industries='|'.join(inds),fallback=fallback,weekend_weight=ws,**dict(zip(times,weights))))
save(pd.DataFrame(rows),'card_july_profiles.csv')
log('Reading July local flow')
t=pd.read_csv(SRC/'flow_time_pop_202507.csv',sep='|',dtype={'BLOCK_CD':str});a=pd.read_csv(SRC/'flow_age_pop_202507.csv',sep='|',dtype={'BLOCK_CD':str});w=pd.read_csv(SRC/'flow_wkdy_pop_202507.csv',sep='|',dtype={'BLOCK_CD':str})
for d in [t,a,w]:
 assert not d.duplicated(['BLOCK_CD','X_COORD','Y_COORD']).any();d['REGION']=d.BLOCK_CD.str[:5].map({'11230':'강남구','32010':'춘천시'})
for h in range(4):t[f't{h}']=t[[f'TMST_{k:02d}' for k in range(h*6,h*6+6)]].mean(axis=1)
for age in AGES:a[age]=a[f'MAN_FLOW_POP_CNT_{age}']+a[f'WMAN_FLOW_POP_CNT_{age}']
w['weekday']=w[['FLOW_POP_CNT_MON','FLOW_POP_CNT_TUS','FLOW_POP_CNT_WED','FLOW_POP_CNT_THU','FLOW_POP_CNT_FRI']].mean(axis=1);w['weekend']=w[['FLOW_POP_CNT_SAT','FLOW_POP_CNT_SUN']].mean(axis=1)
flow=t[['BLOCK_CD','REGION','X_COORD','Y_COORD','t0','t1','t2','t3']].merge(a[['BLOCK_CD','X_COORD','Y_COORD']+AGES],on=['BLOCK_CD','X_COORD','Y_COORD'],validate='one_to_one').merge(w[['BLOCK_CD','X_COORD','Y_COORD','weekday','weekend']],on=['BLOCK_CD','X_COORD','Y_COORD'],validate='one_to_one');flow=flow[flow.REGION.notna()].copy();cols=['t0','t1','t2','t3']+AGES+['weekday','weekend'];assert np.isfinite(flow[cols]).all().all();save(flow.groupby('REGION').size().rename('n_flow_blocks').reset_index(),'july_flow_coverage.csv')
mat={};alphas=[];fallbacks=[]
for radius in RADII:
 log(f'Gravity radius={radius}');z=np.zeros((len(M),5))
 for region,fac in M.groupby('region'):
  f=flow[flow.REGION==region];tree=cKDTree(f[['X_COORD','Y_COORD']].to_numpy());hood=tree.query_ball_point(fac[['X_COORD','Y_COORD']].to_numpy(),radius);vals=f[cols].to_numpy(float);fallbacks.append(dict(radius=radius,REGION=region,n_empty=sum(not len(x) for x in hood),n_facilities=len(fac)))
  local=np.array([vals[ix].mean(0) if len(ix) else vals[int(tree.query(fac.iloc[k][['X_COORD','Y_COORD']].to_numpy(float))[1])] for k,ix in enumerate(hood)])
  for cat,sub in fac.groupby('카테고리'):
   ix=fac.index.get_indexer(sub.index)
   for ai,age in enumerate(AGES):
    weight,ws=profiles[(region,age,cat)];v=np.column_stack([np.log1p(local[ix,4+ai]),np.log1p(local[ix,:4]@weight),np.log1p(local[ix,9]*(1-ws)+local[ix,10]*ws)]);sd=v.std(0);sd[sd<1e-9]=1;z[sub.index,ai]=np.clip(((v-v.mean(0))/sd).mean(1),-3,3)
 for b in STRENGTHS:
  if b:mat[f'r{int(radius)}_b{b:g}']={age:np.full((len(G),len(aft.CAT)),np.nan) for age in AGES}
 for region,g in G.groupby('REGION'):
  for ci,(cat,col) in enumerate(aft.CAT.items()):
   f=M[(M.region==region)&M['카테고리'].eq(cat)]
   if not len(f):continue
   blocks=[];keys=[]
   for b in STRENGTHS:
    if not b:continue
    key=f'r{int(radius)}_b{b:g}';keys.append(key);al=np.exp(b*z[f.index]);al/=al.mean(0);blocks.append(f[aft.MASS].to_numpy()*al)
    for ai,age in enumerate(AGES):
     for j,fi in enumerate(f.index):alphas.append((key,M.loc[fi,'facility_id'],region,cat,age,float(z[fi,ai]),float(al[j,ai])))
   masses=np.concatenate(blocks,axis=1)
   for start in range(0,len(g),256):
    gg=g.iloc[start:start+256];kernel=np.maximum(cdist(gg[['X_COORD','Y_COORD']],f[['X_COORD','Y_COORD']]),1.)**-2;raw=kernel@masses;q=P.loc[col];norm=(np.log1p(raw/q.positive_raw_median)-q.log_min)/(q.log_max-q.log_min)
    for ki,key in enumerate(keys):
     for ai,age in enumerate(AGES):mat[key][age][gg.index,ci]=norm[:,ki*5+ai]
mat['baseline']={}
for age in AGES:
 d=pd.read_csv(BASE/f'step4_aft_and_3d_gravity/results/grid_huff_dosage_matrix_{age}.csv',dtype={'GRID_ID':str}).set_index('GRID_ID').loc[G.GRID_ID];mat['baseline'][age]=d[list(aft.CAT.values())].to_numpy()
alphas=pd.DataFrame(alphas,columns=['candidate','facility_id','REGION','category','AGE','activation_z','alpha']);save(pd.DataFrame(fallbacks),'neighborhood_fallback_audit.csv')
log('Fitting 13 candidates x 5 ages; original pooled primary specification')
ci=[list(aft.CAT.values()).index(c) for c in aft.COMMON];samples={};metrics=[]
for age in AGES:
 d=lab[lab.AGE.eq(age)].merge(G[['GRID_ID','split','spatial_cell']],on='GRID_ID',validate='one_to_one');idx=pd.Index(G.GRID_ID).get_indexer(d.GRID_ID);assert (idx>=0).all();samples[age]=(d,idx);L=d.interval_lower.to_numpy(float);U=d.interval_upper.to_numpy(float);tr=d.split.eq('train').to_numpy();va=d.split.eq('validation').to_numpy()
 for key,mats in mat.items():
  A=np.c_[mats[age][idx][:,ci],d.REGION.eq('춘천시').to_numpy(float)];model=fit(A[tr],L[tr],U[tr]);met,_=evaluate(model,A[va],L[va],U[va]);metrics.append(dict(candidate=key,AGE=age,split='validation',**met))
 log(f'Age {age} complete')
validation=pd.DataFrame(metrics);save(validation,'candidate_validation_metrics.csv');summary=validation.groupby('candidate').agg(mean_interval_nll=('interval_nll','mean'),mean_auc_5m=('auc_5m','mean'),mean_brier_5m=('brier_5m','mean')).sort_values('mean_interval_nll');save(summary.reset_index(),'candidate_validation_summary.csv');selected=str(summary.index[0]);log('Selected '+selected)
results=[];preds=[];coef=[];models={}
for age in AGES:
 d,idx=samples[age];L=d.interval_lower.to_numpy(float);U=d.interval_upper.to_numpy(float);tr=d.split.ne('test').to_numpy();te=~tr
 for key in dict.fromkeys(['baseline',selected]):
  A=np.c_[mat[key][age][idx][:,ci],d.REGION.eq('춘천시').to_numpy(float)];m=fit(A[tr],L[tr],U[tr]);met,p=evaluate(m,A[te],L[te],U[te]);results.append(dict(candidate=key,AGE=age,split='test',**met));pp=d.loc[te,['GRID_ID','AGE','REGION','DONG','event_observed','interval_lower','interval_upper','spatial_cell']].copy();pp['candidate']=key;pp['prob_event_by_month5']=p;preds.append(pp)
  for region in d.REGION.unique():
   mask=te&d.REGION.eq(region).to_numpy();met,_=evaluate(m,A[mask],L[mask],U[mask]);results.append(dict(candidate=key,AGE=age,REGION=region,split='test_region',**met))
 A=np.c_[mat[selected][age][idx][:,ci],d.REGION.eq('춘천시').to_numpy(float)];full=fit(A,L,U);models[age]={k:v.tolist() if hasattr(v,'tolist') else v for k,v in full.items()};beta=full['theta'][1:-1]/full['sd'];intercept=full['theta'][0]-full['mu']@beta
 for term,b in zip(['Intercept']+aft.COMMON+['REGION_CHUNCHEON','log_shape'],np.r_[intercept,beta,full['theta'][-1]]):coef.append(dict(AGE=age,term=term,beta=b,candidate=selected))
 matrix=G.drop(columns=['split','spatial_cell']).copy()
 for j,c in enumerate(aft.CAT.values()):matrix[c]=mat[selected][age][:,j]
 matrix['AGE']=age;save(matrix,f'grid_huff_dosage_matrix_{age}.csv');_,p=evaluate(full,A,L,U);pp=d[['GRID_ID','AGE','REGION','DONG']].copy();pp['fitted_prob_event_5m']=p;save(pp,f'full_refit_probabilities_{age}.csv')
save(pd.DataFrame(results),'heldout_test_metrics.csv');save(pd.concat(preds),'heldout_test_predictions.csv');save(pd.DataFrame(coef),'selected_full_refit_coefficients.csv')
chosen=alphas[alphas.candidate.eq(selected)] if selected!='baseline' else pd.DataFrame([(f,a,1.) for f in M.facility_id for a in AGES],columns=['facility_id','AGE','alpha']);save(chosen,'selected_facility_alpha.csv')
metadata={'selected':selected,'selection_rule':'lowest macro validation interval NLL across five ages; baseline included','split':'fixed SHA256 500m cells 60/20/20; all ages grouped; not buffered','original_source':str(BASE),'features':aft.COMMON+['REGION_CHUNCHEON'],'formula':'alpha=exp(b*z)/mean_region_category_age(exp(b*z)); M*=M*alpha; X*=sum(M*/max(d,1)^2); original normalization reused','activation':'mean standardized log1p local age flow, card-time-weighted marginal all-age flow, card-weekend-weighted marginal all-age flow; July only; per region/category','card_period':'July 2025 data1 only; 60GU profile sums 60+; original M60 remains 60-69','radius_candidates':RADII,'strength_candidates':STRENGTHS,'models':models,'outcome':'original low-activity selection event, not clinical personal isolation','temporal_status':'original full-period mass and retrospective label construction preserved; spatial test is NOT future-period validation','proxy':'neighborhood activity proxy, not observed facility sales; park/bookstore and transport/general contact mappings are proxies','inference':'no causal/significance claims for tuned full-refit coefficients','inputs_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in INP.iterdir() if p.is_file()},'card_sha256':hashlib.sha256(cardpath.read_bytes()).hexdigest()}
(OUT/'run_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8');log(pd.DataFrame(results).query("split=='test'").to_string(index=False));log('COMPLETE')


