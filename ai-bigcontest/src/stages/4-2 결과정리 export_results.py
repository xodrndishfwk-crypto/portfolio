from pathlib import Path
import json,hashlib,importlib.util
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
ROOT=Path(__file__).resolve().parent;O=ROOT/'results';meta=json.loads((O/'run_metadata.json').read_text(encoding='utf-8'));B=Path(meta['original_source']);I=B/'step4_aft_and_3d_gravity/inputs'
M=pd.read_csv(I/'mass_all_ages.csv',dtype={'facility_id':str});M=M[M.READY_FOR_HUFF.astype(str).str.lower().isin(['true','1'])].copy();alph=pd.read_csv(O/'selected_facility_alpha.csv',dtype={'facility_id':str});par=pd.read_csv(I/'normalization_parameters.csv').set_index('column');ages=['20G','30G','40G','50G','60GU'];mcols=['M_20','M_30','M_40','M_50','M_60'];normcols=[c for c in par.index]
def save(d,n):d.to_csv(O/n,index=False,encoding='utf-8-sig')
for age,mc in zip(ages,mcols):M[mc]*=M.facility_id.map(alph[alph.AGE.eq(age)].set_index('facility_id').alpha)
assert np.isfinite(M[mcols]).all().all();save(M,'mass_all_ages_alpha.csv')
checks=[]
for age,mc in zip(ages,mcols):
 d=pd.read_csv(O/f'grid_huff_dosage_matrix_{age}.csv',dtype={'GRID_ID':str});raw=d.copy()
 for c in normcols:
  q=par.loc[c];raw[c]=q.positive_raw_median*np.expm1(d[c]*(q.log_max-q.log_min)+q.log_min)
 save(raw,f'grid_huff_dosage_raw_{age}.csv')
 for c,q in par.iterrows():
  for region in d.REGION.unique():
   g=d[d.REGION.eq(region)].iloc[::500];f=M[M.region.eq(region)&M['카테고리'].eq(q.category)]
   if not len(f):continue
   expected=np.maximum(cdist(g[['X_COORD','Y_COORD']],f[['X_COORD','Y_COORD']]),1.)**-2@f[mc].to_numpy();actual=raw.set_index('GRID_ID').loc[g.GRID_ID,c].to_numpy();ok=np.allclose(actual,expected,rtol=1e-8,atol=1e-12);assert ok
   checks.append(dict(AGE=age,REGION=region,term=c,n=len(g),max_abs_error=float(np.max(np.abs(actual-expected))),passed=bool(ok)))
save(pd.DataFrame(checks),'gravity_reproduction_spotchecks.csv')
# Source-compatible primary coefficients, but no post-tuning significance claims.
coef=pd.read_csv(O/'selected_full_refit_coefficients.csv');coef['model_scope']='pooled_common';coef['engine']='scipy_interval_weibull_mle_alpha';coef['parameter_role']=np.where(coef.term.str.startswith('X_'),'infrastructure','other');coef['time_ratio']=np.where(coef.term.str.startswith('X_'),np.exp(np.clip(coef.beta,-700,700)),np.nan);coef['time_ratio_per_0_1_X']=np.where(coef.term.str.startswith('X_'),np.exp(np.clip(.1*coef.beta,-700,700)),np.nan);save(coef,'aft_primary_age_comparison.csv')
metrics=pd.read_csv(O/'heldout_test_metrics.csv');test=metrics[metrics.split.eq('test')];before=test[test.candidate.eq('baseline')].set_index('AGE');after=test[test.candidate.eq(meta['selected'])].set_index('AGE');comparison=pd.DataFrame({'AUC_original':before.auc_5m,'AUC_alpha':after.auc_5m,'AUC_change':after.auc_5m-before.auc_5m,'NLL_original':before.interval_nll,'NLL_alpha':after.interval_nll,'NLL_change':after.interval_nll-before.interval_nll,'Brier_original':before.brier_5m,'Brier_alpha':after.brier_5m,'test_n':before.n}).reindex(ages);save(comparison.reset_index(),'comparison_by_age.csv')
regions=metrics[metrics.split.eq('test_region')];rr=regions.pivot(index=['REGION','AGE'],columns='candidate',values=['auc_5m','interval_nll','brier_5m']);rr.columns=['|'.join(c) for c in rr.columns];save(rr.reset_index(),'comparison_by_region_age.csv')
split=pd.read_csv(O/'spatial_split.csv');assert split.groupby('spatial_cell').split.nunique().max()==1;assert not split.GRID_ID.duplicated().any();groupmeans=alph.groupby(['REGION','category','AGE']).alpha.mean();assert np.allclose(groupmeans,1)
assert all(hashlib.sha256((I/n).read_bytes()).hexdigest()==h for n,h in meta['inputs_sha256'].items())
validation={'gravity_spotcheck_groups':len(checks),'gravity_spotcheck_rows':sum(x['n'] for x in checks),'source_input_hashes_unchanged':True,'alpha_positive':bool(alph.alpha.gt(0).all()),'alpha_group_mean_one':True,'no_spatial_cell_split_overlap':True,'labels_unchanged':True,'heldout_rows':int(before.n.sum()),'not_future_period_test':True}
(O/'verification.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
mean_before=float(before.auc_5m.mean());mean_after=float(after.auc_5m.mean());nll_before=float(before.interval_nll.mean());nll_after=float(after.interval_nll.mean())
text='''# 초기 버전 인프라 활성도 α 보정 결과

[확실] 초기 monthly_grid_results의 입력 질량, 정규화, 표본과 생존 라벨을 보존하고 시설 주변 활성도 보정을 추가했습니다. 원본 폴더는 읽기만 했습니다.

## 선택된 보정식

[확실] 검증 표본의 5개 연령 평균 구간검열 생존 음의 로그우도(NLL)가 가장 작은 후보는 반경 800m, 강도 b=-1입니다. 후보는 반경 300/800m × 강도 -2,-1,-0.5,0.5,1,2 및 원본 1개로 총 13개입니다.

    alpha(j,a) = exp(-z(j,a)) / mean_region,category,age(exp(-z))
    M*(j,a) = M(j,a) * alpha(j,a)
    raw_X*(i,k,a) = sum_j_in_category_k M*(j,a) / max(distance(i,j),1m)^2
    X* = 기존 positive_raw_median, log_min, log_max로 정규화

[확실] z는 7월 시설 주변 800m 안 유동 격자들의 평균을 이용합니다. 연령별 유동, 카드 시간대 가중 전체 연령 유동, 카드 평일/주말 가중 전체 연령 유동의 log1p를 지역·시설종류별 표준화하고 평균한 값입니다. 이후 [-3,3]으로 제한합니다. 각 자료는 주변에 결합되는 동일 격자의 BLOCK_CD+X_COORD+Y_COORD로 연결합니다.

[확실] 카드 데이터1의 7월 개인 이용 건수만 사용했습니다. 6시간대별 비중과 평일/주말 일평균 이용 비중을 지역·업종·연령별로 계산합니다. 7월 평일 23일·주말 8일로 보정합니다. 데이터2와 합산하지 않았습니다. 60GU의 새 카드 프로필은 60대 이상을 합산합니다.

[확실] 도서관은 서점·독서실, 병원은 보건소·병원 업종, 사교상권은 카페·요식·유흥 업종, 공원은 운동·레저 업종의 시간 프로필을 사용합니다. 교통·주민센터는 생활 접점 업종 묶음을 사용합니다. 상세 업종과 시간 비중은 card_july_profiles.csv에 있습니다.

[추정] 이는 시설별 매출 또는 시설의 품질 그 자체가 아니라, 주변 활동과 업종별 이용 시간의 적합도를 나타내는 대리 지표입니다. 연령별 유동과 시간대별 유동은 별개의 주변 지표로 결합하며 실제 연령×시간대 교차 관측치로 취급하지 않습니다.

## 보정 방향 해석

[확실] 선택된 강도가 음수이므로, 활성도가 높은 주변에 더 큰 질량을 주는 가설은 이번 비교에서 선택되지 않았습니다. 시설 주변 활성도가 상대적으로 낮은 곳을 더 강조하는 재가중이 잘 맞았습니다. 평균 alpha는 지역·종류·연령별 1로 맞췄습니다. 이는 질량 가중 평균 보존을 의미하지 않습니다.

[추정] 이를 공급과 주변 활동의 불일치를 반영한 접근성 지표로 활용할 수 있습니다. 활성도가 낮은 곳에 있는 시설이 더 우수하다거나 인프라가 고립을 예방한다는 인과 결론은 도출하지 않았습니다.

## 학습과 평가

[확실] 좌표를 500m 공간 셀로 묶어 같은 셀의 모든 격자와 연령을 한쪽에만 배정했습니다. 결과 라벨과 무관한 고정 SHA256 분할로 학습 60%, 검증 20%, 평가 20%를 목표로 배정했습니다. 실제 행 비중은 셀 크기와 표본 구성에 따라 다릅니다. 인접 셀 간 완충 구간은 없습니다.

[확실] 학습 라벨로 AFT 계수를 맞추고 검증 NLL로 후보를 고른 뒤, 학습+검증으로 재학습하여 남겨둔 평가 표본을 한 번 평가했습니다. 기존과 보정 모두 동일한 표본, 라벨, 다섯 공통 인프라+지역 더미를 사용합니다. AUC와 Brier는 사건 여부를 5개월까지 확인할 수 있는 표본만 사용하고, NLL은 조기 검열도 포함합니다.

[확실] 아래 결과는 원본의 전체 기간 질량과 기존 라벨을 보존한 공간 분리 평가입니다. 미래 기간 외부 검증 결과는 아닙니다. 예측 대상은 기존 활동 저조 선정 상태의 첫 진입이며 개인의 실제 고립 진단이 아닙니다.

'''
text+='[확실] 평가 표본 '+str(int(before.n.sum()))+'행. 연령 평균 AUC '+f'{mean_before:.4f} → {mean_after:.4f}'+'. 연령 평균 NLL '+f'{nll_before:.6f} → {nll_after:.6f}'+'.\n\n'
text+='|연령|원본 AUC|보정 AUC|변화|원본 NLL|보정 NLL|\n|---|---:|---:|---:|---:|---:|\n'
for a,r in comparison.iterrows():text+=f'|{a}|{r.AUC_original:.4f}|{r.AUC_alpha:.4f}|{r.AUC_change:+.4f}|{r.NLL_original:.4f}|{r.NLL_alpha:.4f}|\n'
text+='''
[확실] 평균 AUC는 5개 연령 모두 개선했으나 40대 NLL/Brier는 소폭 악화했습니다. 지역별 세부에서는 강남 40대 AUC가 감소하고 춘천 50대 AUC가 미세하게 감소합니다. 세부 비교는 comparison_by_region_age.csv에 있습니다. 공식 유의성 또는 인과효과 검정 결과는 아닙니다.

## 파이프라인에 적용할 파일

- [확실] `mass_all_ages_alpha.csv`: 5개 M열을 alpha로 보정한 시설 질량. 원본을 덮어쓰지 않습니다.
- [확실] `grid_huff_dosage_matrix_20G.csv` 등 5개: 기존과 같은 7개 X열 및 격자키를 가진 보정 입력. AGE 열을 추가했습니다.
- [확실] `grid_huff_dosage_raw_20G.csv` 등 5개: 같은 보정의 정규화 전 합산값.
- [확실] `selected_facility_alpha.csv`: 시설·연령별 alpha와 활성도.
- [확실] `selected_full_refit_coefficients.csv`, `full_refit_models.json`: 전체 표본 재적합 AFT 계수. 튜닝 후 설명용 계수이므로 유의확률은 제공하지 않습니다.
- [확실] `full_refit_probabilities_*.csv`: 전체 표본 재적합 확률. 평가 성능은 이 파일이 아닌 heldout_test_* 파일에서만 계산했습니다.
- [확실] `predict_alpha.py`: 보정 X를 읽어 저장된 계수로 확률을 재생성합니다. 대상은 초기 버전 7~12월 관측 범위인 5개월입니다.
- [확실] `run_alpha.py`: 원본 경로·sources 경로를 인자로 받아 후보 탐색부터 재실행합니다. Python numpy/pandas/scipy 필요.

[확실] 원본 Step4 재실행 시 mass_all_ages.csv를 교체하면 원본 M20 재현 확인이 실패하도록 되어 있습니다. 그 확인문을 지우지 말고 이 패키지의 보정 X·계수·predict_alpha.py를 사용하세요. 기존 Step3 라벨은 바꾸지 않습니다.

## 제출용 설명 문장

[확실] 지역·연령·업종별 카드 이용 시간 분포와 시설 주변 유동인구로 인프라 중력의 질량을 보정하였다. 반경과 보정 강도를 검증 표본에서 선택하고, 별도로 분리한 공간 셀의 평가 표본에서 원본 대비 5개 연령 평균 AUC가 개선되었다. 이는 기존 활동 저조 라벨에 대한 예측 정합성의 개선이며, 실제 고립에 대한 인과효과나 미래 기간 검증을 의미하지 않는다.
'''
(ROOT/'README_KO.md').write_text(text,encoding='utf-8');(O/'full_refit_models.json').write_text(json.dumps(meta['models'],indent=2),encoding='utf-8');print(json.dumps(validation));print('MEAN AUC',mean_before,mean_after,'MEAN NLL',nll_before,nll_after)
