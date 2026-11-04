from pathlib import Path
import pandas as pd,numpy as np,json,re,hashlib,zipfile
import geopandas as gpd
from pyproj import Transformer
ROOT=Path(r'./private_inputs/main_work')
OUT=ROOT/'infrastructure_gravity_mass_results'/pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
OUT.mkdir(parents=True,exist_ok=True)
MONTHS=[f'2025{m:02}' for m in range(7,13)]
AGES=[20,30,40,50,60]
audit={'source_root':str(ROOT),'period':MONTHS,'ages':'20-29,30-39,40-49,50-59,60-69; exclude 70+','card_main':'data2 personal only; data1 not combined','warnings':[]}
def save(d,n):d.to_csv(OUT/n,index=False,encoding='utf-8-sig')
def find(pattern):
 f=[p for p in ROOT.rglob(pattern) if 'monthly_grid_results' not in p.parts]
 if len(f)!=1:raise ValueError(f'{pattern}: {len(f)} files')
 return f[0]
def readcsv(p,**kwargs):
 for enc in ['utf-8-sig','cp949']:
  try:return pd.read_csv(p,encoding=enc,**kwargs)
  except UnicodeDecodeError:pass
 raise ValueError(f'encoding {p}')
def fid(source,key):return hashlib.sha256((source+'|'+str(key)).encode()).hexdigest()[:20]
# Aggregate only one overlapping view of card records.
card_path=find('신한카드_빅콘테스트2026_데이터2.txt')
card=pd.read_csv(card_path,sep='\t',encoding='cp949',dtype={'TA_YMD':str,'AGE_CCD':str})
audit['card_raw_rows']=len(card)
keys=['TA_YMD','MCT_SGG_CD','MCT_RY_CD','CLN_SGG_CD','SEX_CCD','AGE_CCD']
audit['card_exact_duplicate_rows']=int(card.duplicated().sum())
audit['card_duplicate_key_rows']=int(card.duplicated(keys,False).sum())
if card.duplicated(keys).any():raise ValueError('data2 duplicate aggregate key; investigate before summing')
card['month']=card.TA_YMD.str[:6]
card['age']=pd.to_numeric(card.AGE_CCD.str.extract(r'(\d+)')[0],errors='coerce')
card['region']=card.MCT_SGG_CD.map({'서울 강남구':'강남구','강원 춘천시':'춘천시'})
if card.region.isna().any():raise ValueError('unknown card region')
if not set(card.month).issubset(set(MONTHS)):raise ValueError('unexpected date')
for c in ['TS_AT','USE_CNT']:card[c]=pd.to_numeric(card[c],errors='raise')
if card[['TS_AT','USE_CNT']].isna().any().any():raise ValueError('null card amount or count')
q=card[card.age.isin(AGES)].copy()
audit['card_target_age_rows']=len(q)
audit['card_months']=sorted(card.month.unique().tolist())
audit['card_dates_by_month']=card.groupby('month').TA_YMD.nunique().astype(int).to_dict()
monthly=q.groupby(['region','month','MCT_RY_CD','age'],as_index=False)[['TS_AT','USE_CNT']].sum().rename(columns={'MCT_RY_CD':'card_industry','TS_AT':'amount','USE_CNT':'count'})
save(monthly,'card_industry_monthly.csv')
industry_means=monthly.groupby(['region','card_industry','age'],as_index=False).agg(total_amount=('amount','sum'),total_count=('count','sum'),observed_months=('month','nunique'))
industry_means['monthly_mean_amount']=industry_means.total_amount/6
industry_means['monthly_mean_count']=industry_means.total_count/6
industry_means.loc[industry_means.observed_months!=6,['monthly_mean_amount','monthly_mean_count']]=np.nan
save(industry_means,'card_industry_six_month_average.csv')
audit['card_target_totals']={'amount':int(q.TS_AT.sum()),'count':int(q.USE_CNT.sum())}
assert int(monthly.amount.sum())==int(q.TS_AT.sum())
assert int(monthly['count'].sum())==int(q.USE_CNT.sum())
del card,q
mapping=[
 ('library_learning','도서관','서점','proxy','도서관 직접 결제가 아닌 독서문화 소비 대리변수'),
 ('library_learning','도서관','독서실','proxy','스터디카페 분리 불가; 독서실 업종 전체를 대리변수로 사용'),
 ('hospital_public','병원','보건소','broad_category','보건소·보건지소·보건진료소를 보건소 카드업종에 연결'),
 ('hospital_general','병원','일반병원','broad_category','의원·병원·요양·정신병원 등을 일반병원 카드업종에 연결'),
 ('hospital_general_complex','병원','종합병원','category','종합병원 카드업종'),
 ('hospital_dental','병원','치과병원','broad_category','치과의원 포함'),
 ('hospital_korean','병원','한의원','broad_category','한방병원 포함'),
 ('social_cafe','사교상권','커피전문점','category','카페 매장에 지역 커피전문점 소비 균등 배분'),
 ('social_entertainment','사교상권','유흥업소','category','일반/무도 유흥 주점만 연결; 요리 주점과 구분'),
 ('social_cooking_pub','사교상권',None,'unsupported','요리 주점의 매출을 카드의 한식/기타요식/유흥업소 중 어디로 배분할지 식별 불가'),
 ('park','공원',None,'unsupported','무료 공원 이용을 카드 결제로 측정할 수 없어 질량 결측'),
 ('resident_center','주민센터',None,'unsupported','세금공과금은 주민센터 방문 소비가 아니므로 사용하지 않음'),
 
 ('metro_station','지하철역',None,'unsupported','복합 고속버스/철도/여객선 업종을 지하철 소비로 사용하지 않음'),
 ('bus_stop','버스정류장',None,'unsupported','시내버스 정류장별 결제 식별 불가')]
mapping=pd.DataFrame(mapping,columns=['mass_group','infra_category','card_industry','match_type','reason'])
save(mapping,'industry_mapping.csv')
donor=mapping[mapping.card_industry.notna()]
assert not donor.card_industry.duplicated().any(),'avoid reuse of same consumption in multiple mass groups'
known=set(monthly.card_industry)
if not set(donor.card_industry)<=known:raise ValueError('mapped industry absent')
catmonthly=monthly.merge(donor[['mass_group','card_industry']],on='card_industry',how='inner').groupby(['region','month','age','mass_group'],as_index=False)[['amount','count']].sum()
save(catmonthly,'card_category_monthly.csv')
# Do not interpret missing monthly aggregates as zero.
means=catmonthly.groupby(['region','age','mass_group']).agg(total_amount=('amount','sum'),total_count=('count','sum'),observed_months=('month','nunique')).reset_index()
means['monthly_mean_amount']=means.total_amount/6
means['monthly_mean_count']=means.total_count/6
means.loc[means.observed_months!=6,['monthly_mean_amount','monthly_mean_count']]=np.nan
# Assemble source records without fabricating absent facilities.
rows=[]
def add(source,key,name,cat,sub,region,address,lon,lat,group,coord_status='source_coordinate',temporal='2025_existence_unverified'):
 rows.append(dict(facility_id=fid(source,key),name=name,category=cat,subcategory=sub,region=region,address=address,longitude=lon,latitude=lat,mass_group=group,source_file=source,coord_source_status=coord_status,temporal_status=temporal))
master_path=find('*01_infrastructure_master.csv')
master=readcsv(master_path)
for r in master.to_dict('records'):
 cat=r['시설분류'];group='library_learning' if cat=='도서관' else 'park'
 add(master_path.name,r['시설ID'],r['시설명'],cat,r['시설유형'],r['지역'],r['주소'],r['경도'],r['위도'],group,str(r['좌표상태']))
hospital_path=find('1.병원정보서비스*.csv')
h=readcsv(hospital_path)
h['region']=np.select([h.주소.fillna('').str.contains(r'^서울.*강남구'),h.주소.fillna('').str.contains(r'^강원.*춘천시')],['강남구','춘천시'],default='')
h=h[h.region!=''].copy()
h['opened']=pd.to_datetime(h.개설일자,errors='coerce')
for r in h.to_dict('records'):
 sub=str(r['종별코드명'])
 if '보건' in sub:group='hospital_public'
 elif '치과' in sub:group='hospital_dental'
 elif '한방' in sub or '한의' in sub:group='hospital_korean'
 elif '종합' in sub or '상급' in sub:group='hospital_general_complex'
 else:group='hospital_general'
 status='opened_after_2025' if pd.notna(r['opened']) and r['opened']>pd.Timestamp('2025-12-31') else ('opened_by_2025' if pd.notna(r['opened']) else '2025_existence_unverified')
 add(hospital_path.name,r['암호화요양기호'],r['요양기관명'],'병원',sub,r['region'],r['주소'],r['좌표(X)'],r['좌표(Y)'],group,temporal=status)
for pattern,region in [('*강남구_동주민센터*.csv','강남구'),('*춘천시_행정복지센터*.csv','춘천시')]:
 p=find(pattern);d=readcsv(p)
 for i,r in enumerate(d.to_dict('records')):
  if region=='강남구':name=r['주민센터명']+' 주민센터';address=r['소재지'];lon=r['경도'];lat=r['위도']
  else:name=r['읍면동명'];address=r['소재지도로명주소'];lon=lat=np.nan
  add(p.name,i,name,'주민센터','행정복지센터',region,address,lon,lat,'resident_center')
# Read only needed columns from 360MB of store files.
retail=[]
usecols=['상가업소번호','상호명','지점명','상권업종소분류명','시군구명','도로명주소','경도','위도']
social_types={'카페':'social_cafe','일반 유흥 주점':'social_entertainment','무도 유흥 주점':'social_entertainment','요리 주점':'social_cooking_pub'}
for p in sorted((ROOT/'인프라').glob('*상가*.csv')):
 for d in pd.read_csv(p,encoding='utf-8-sig',usecols=usecols,chunksize=100000):
  d=d[d.시군구명.isin(['강남구','춘천시']) & d.상권업종소분류명.isin(social_types)].copy()
  for r in d.to_dict('records'):
   name=r['상호명']+((' '+str(r['지점명'])) if pd.notna(r['지점명']) else '')
   add(p.name,r['상가업소번호'],name,'사교상권',r['상권업종소분류명'],r['시군구명'],r['도로명주소'],r['경도'],r['위도'],social_types[r['상권업종소분류명']])
# Local transport inputs: preserve source IDs and select physically located points.
transport_nodes=[]
transport_boundaries={}
for code,region in [('11230','강남구'),('32010','춘천시')]:
 transport_boundaries[region]=gpd.read_file(find(f'bnd_dong_{code}_2025_2Q.shp')).to_crs(4326).geometry.union_all()
bus_path=find('국토교통부_전국 버스정류장 위치정보_20251031.csv')
bus=readcsv(bus_path)
if bus['정류장번호'].duplicated().any():raise ValueError('bus source ID duplicated')
bus['위도']=pd.to_numeric(bus['위도'],errors='coerce');bus['경도']=pd.to_numeric(bus['경도'],errors='coerce')
valid_bus=bus['경도'].between(124,132)&bus['위도'].between(33,39)
bp=gpd.GeoSeries(gpd.points_from_xy(bus.loc[valid_bus,'경도'],bus.loc[valid_bus,'위도']),index=bus.index[valid_bus],crs=4326)
for region,geom in transport_boundaries.items():
 indices=bp.index[bp.intersects(geom)]
 for r in bus.loc[indices].to_dict('records'):
  city=str(r['도시명'])
  city_match=('서울' in city) if region=='강남구' else ('춘천' in city)
  status='공식정류장좌표_경계내' if city_match else '재확인_원본도시명과공간지역불일치'
  add(bus_path.name,r['정류장번호'],r['정류장명'],'버스정류장','버스정류장',region,'',r['경도'],r['위도'],'bus_stop',status,'snapshot_20251031_earlier_month_existence_unverified')
  transport_nodes.append(dict(region=region,kind='bus_stop',source_id=r['정류장번호'],name=r['정류장명'],source_city=city,longitude=r['경도'],latitude=r['위도'],source_node_type='',status=status))
metro_path=find('서울시 지하철역 연계 지하도 공간정보.csv')
metro=readcsv(metro_path)
metro=metro[(metro['노드링크 유형']=='NODE')&metro['노드 WKT'].notna()].copy()
mg=gpd.GeoDataFrame(metro,geometry=gpd.GeoSeries.from_wkt(metro['노드 WKT'],crs=4326),crs=4326)
for region,geom in transport_boundaries.items():
 sub=mg[mg.geometry.intersects(geom)].copy()
 if sub.empty:continue
 for station,g in sub.groupby('지하철역명'):
  if pd.isna(station):continue
  g=g.to_crs(5179)
  x=g.geometry.x.to_numpy();y=g.geometry.y.to_numpy()
  # Choose an actual network node closest to centroid, not a fabricated station centroid.
  order=np.lexsort((g['노드 ID'].to_numpy(),(x-x.mean())**2+(y-y.mean())**2))
  r=g.iloc[int(order[0])]
  point=gpd.GeoSeries([r.geometry],crs=5179).to_crs(4326).iloc[0]
  add(metro_path.name,region+'|'+station,station+'역','지하철역','지하도노드_실제역중심점아님',region,'',point.x,point.y,'metro_station','지하도NODE_대표점_출입구유형미확인','snapshot_date_unknown')
  for rr in sub[sub.지하철역명==station].to_dict('records'):
   transport_nodes.append(dict(region=region,kind='metro_access_node',source_id=rr['노드 ID'],name=station,source_city=rr['시군구명'],longitude=rr['geometry'].x,latitude=rr['geometry'].y,source_node_type=rr['노드 유형 코드'],status='source_node_semantics_unverified'))
transport_nodes=pd.DataFrame(transport_nodes)
tt=Transformer.from_crs(4326,5179,always_xy=True)
transport_nodes['X_COORD'],transport_nodes['Y_COORD']=tt.transform(transport_nodes.longitude.to_numpy(),transport_nodes.latitude.to_numpy())
save(transport_nodes,'transport_source_nodes.csv')
audit['transport_source_counts']=transport_nodes.groupby(['region','kind']).size().to_dict()
audit['transport_source_counts']={'|'.join(k):int(v) for k,v in audit['transport_source_counts'].items()}
audit['transport_notes']=['bus platform IDs preserved; opposing platforms not merged','bus source city vs point-region mismatch retained for manual review','metro grouped by station name per region, one actual node representative per station; not a verified station center or entrance','Seoul metro dataset does not provide Chuncheon rail stations','transport masses remain null; intercity bus/rail/ferry aggregate not mapped to local subway or bus stops']

infra=pd.DataFrame(rows)
assert not infra.facility_id.duplicated().any()
for c in ['longitude','latitude']:infra[c]=pd.to_numeric(infra[c],errors='coerce')
infra['coord_valid']=infra.longitude.between(124,132)&infra.latitude.between(33,39)
trans=Transformer.from_crs(4326,5179,always_xy=True)
infra['X_COORD']=np.nan;infra['Y_COORD']=np.nan
good=infra.coord_valid
infra.loc[good,'X_COORD'],infra.loc[good,'Y_COORD']=trans.transform(infra.loc[good,'longitude'].to_numpy(),infra.loc[good,'latitude'].to_numpy())
infra['location_status']=np.where(infra.coord_valid,'source_point_unverified','missing_or_invalid_coordinate')
boundaries=[]
for code,region in [('11230','강남구'),('32010','춘천시')]:
 b=gpd.read_file(find(f'bnd_dong_{code}_2025_2Q.shp')).to_crs(5179)
 geom=b.geometry.union_all()
 idx=infra.coord_valid & infra.region.eq(region)
 pts=gpd.GeoSeries(gpd.points_from_xy(infra.loc[idx,'X_COORD'],infra.loc[idx,'Y_COORD']),index=infra.index[idx],crs=5179)
 covered=pts.intersects(geom)
 infra.loc[covered.index,'location_status']=np.where(covered,'inside_expected_region','outside_expected_region')
infra['coord_review_flag']=infra.coord_source_status.str.contains('재확인|의심',na=False)
infra['eligibility_reason']=np.select([~infra.coord_valid,infra.location_status.ne('inside_expected_region'),infra.coord_review_flag,infra.temporal_status.eq('opened_after_2025'),~infra.mass_group.isin(donor.mass_group)],['missing_coordinate','outside_expected_region','source_coordinate_needs_review','opened_after_2025','no_valid_card_industry'],default='eligible_proxy')
infra['eligible']=infra.eligibility_reason.eq('eligible_proxy')
npoints=infra[infra.eligible].groupby(['region','mass_group']).size().rename('allocation_poi_count').reset_index()
means=means.merge(npoints,on=['region','mass_group'],how='left',validate='many_to_one')
means['per_poi_monthly_amount']=means.monthly_mean_amount/means.allocation_poi_count
means['per_poi_monthly_count']=means.monthly_mean_count/means.allocation_poi_count
means['raw_mass']=np.nan;means['M']=np.nan
# For each age, normalize per-point amount and counts by their mean across eligible POIs.
for age in AGES:
 idx=means.age.eq(age)&means.allocation_poi_count.gt(0)&means.observed_months.eq(6)&means.per_poi_monthly_amount.gt(0)&means.per_poi_monthly_count.gt(0)
 v=means.loc[idx];n=v.allocation_poi_count
 avg_amount=float((v.per_poi_monthly_amount*n).sum()/n.sum())
 avg_count=float((v.per_poi_monthly_count*n).sum()/n.sum())
 raw=np.sqrt((v.per_poi_monthly_amount/avg_amount)*(v.per_poi_monthly_count/avg_count))
 scale=float((raw*n).sum()/n.sum())
 means.loc[idx,'raw_mass']=raw;means.loc[idx,'M']=raw/scale
 audit[f'normalization_{age}']=dict(mean_per_poi_amount=avg_amount,mean_per_poi_count=avg_count,raw_mass_weighted_mean=scale,reference_pois=int(n.sum()))
save(means,'region_category_age_mass.csv')
detail=infra.merge(pd.DataFrame({'age':AGES}),how='cross').merge(means,on=['region','mass_group','age'],how='left',validate='many_to_one')
detail.loc[~detail.eligible,'M']=np.nan
detail['mass_basis']='region_industry_equal_allocation_proxy_not_facility_sales'
save(detail,'infrastructure_mass_detail.csv')
wide=detail.pivot(index='facility_id',columns='age',values='M').rename(columns={20:'M_20',30:'M_30',40:'M_40',50:'M_50',60:'M_60'}).reset_index()
final=infra.merge(wide,on='facility_id',validate='one_to_one')
final['READY_FOR_HUFF']=final.eligible & final[['M_20','M_30','M_40','M_50','M_60']].notna().all(axis=1)
reasons=donor.groupby('mass_group').agg(card_industries=('card_industry',lambda x:'|'.join(x)),match_type=('match_type',lambda x:'|'.join(sorted(set(x))))).reset_index()
final=final.merge(reasons,on='mass_group',how='left',validate='many_to_one')
final['MASS_BASIS']='시군구_대응업종소비_균등배분_추정질량'
final=final.rename(columns={'name':'명칭','category':'카테고리'})
first=['명칭','카테고리','X_COORD','Y_COORD','M_20','M_30','M_40','M_50','M_60']
final=final[first+[c for c in final if c not in first]]
save(final,'infrastructure_gravity_mass.csv')
save(final[final.READY_FOR_HUFF],'infrastructure_gravity_mass_ready.csv')
review=final[~final.READY_FOR_HUFF]
save(review,'manual_review_and_unsupported.csv')
coverage=final.groupby(['region','카테고리'],as_index=False).agg(records=('facility_id','size'),ready=('READY_FOR_HUFF','sum'))
coverage=coverage.merge(pd.MultiIndex.from_product([['강남구','춘천시'],['도서관','병원','지하철역','버스정류장','주민센터','공원','사교상권']],names=['region','카테고리']).to_frame(index=False),on=['region','카테고리'],how='right')
coverage[['records','ready']]=coverage[['records','ready']].fillna(0).astype(int)
coverage['note']=np.where(coverage.records.eq(0),'source_POI_missing',np.where(coverage.ready.eq(0),'unsupported_card_or_coordinate','proxy_mass_available'))
save(coverage,'category_coverage.csv')
# Meaningful validations: no donor reuse, monthly reconciliation, balanced allocation, nonnegative mass, spatial validity.
assert final[['M_20','M_30','M_40','M_50','M_60']].stack().dropna().gt(0).all()
assert final.loc[final.READY_FOR_HUFF,['X_COORD','Y_COORD','M_20','M_30','M_40','M_50','M_60']].notna().all().all()
assert final.loc[final.READY_FOR_HUFF,'location_status'].eq('inside_expected_region').all()
for age in AGES:
 assert np.isclose(final.loc[final[f'M_{age}'].notna(),f'M_{age}'].mean(),1)
v=means.dropna(subset=['M'])
assert np.allclose(v.per_poi_monthly_amount*v.allocation_poi_count,v.monthly_mean_amount)
assert np.allclose(v.per_poi_monthly_count*v.allocation_poi_count,v.monthly_mean_count)
audit['facility_count']=len(final);audit['ready_count']=int(final.READY_FOR_HUFF.sum())
audit['unready_reason_counts']=final.loc[~final.READY_FOR_HUFF,'eligibility_reason'].value_counts().astype(int).to_dict()
audit['category_coverage']=coverage.to_dict('records')
audit['sparse_month_groups']=means[means.observed_months.ne(6)][['region','age','mass_group','observed_months']].to_dict('records')
audit['formula']='A_bar=sum(amount Jul-Dec)/6; C_bar=sum(count Jul-Dec)/6; allocate each group equally across N eligible points. r=sqrt((A_bar/N / mean_point_A_age)*(C_bar/N / mean_point_C_age)); M=r/mean_point_r_age'
audit['files']=[dict(path=str(p),bytes=p.stat().st_size) for p in [card_path,master_path,hospital_path]]
(OUT/'data_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
readme=f"""# Step 1: infrastructure gravity mass
[확실] 주 결과: infrastructure_gravity_mass.csv. {len(final):,}개 시설 원장을 보존하며, 다섯 연령 질량과 좌표가 모두 있는 사용 가능 목록은 infrastructure_gravity_mass_ready.csv ({int(final.READY_FOR_HUFF.sum()):,}개)입니다.
[확실] M이 비어 있는 값은 0이 아닙니다. 결제 대응 업종 부재, 좌표 누락/검토, 지역 외 좌표, 2025년 이후 개설 등으로 산출하지 않은 값입니다.
[확실] 신한카드 데이터2 한 종류만 사용했습니다. 데이터1과 데이터2는 집계 차원이 다르고 거래별 중복을 분리할 식별자가 없어 더하지 않았습니다. 법인 제외, 남녀 합산, 소비자 거주 시도 합산, 2025-07~12 여섯 달입니다.
[확실] M_60은 60~69세입니다. 70세 이상을 포함하지 않습니다.
[확실] 결제금액/건수는 카드 원자료 단위를 그대로 보존합니다. 전국 카드소비나 시설별 실측 매출로 확대하지 않았습니다.

## 계산식 (모델 가정)
[추정] 지역×대응 업종그룹×연령별 여섯 달 총액/6 및 총건수/6을 구합니다. 관측월이 여섯 달 미만이면 월평균을 비웁니다. 누락을 0으로 바꾸지 않습니다.
[추정] A=월평균금액/N, C=월평균건수/N. N은 같은 지역·업종그룹의 좌표/시점 조건을 통과한 시설 수입니다.
[추정] 연령별 모든 배분 대상 시설에서의 A 평균, C 평균으로 각각 나눈 후 기하평균 r=sqrt((A/mean(A))*(C/mean(C)))을 구합니다. 최종 M=r/mean(r)이며 연령별 전체 평균=1입니다. 금액·건수 동일 가중치와 균등 배분은 검증된 사실이 아닌 설정입니다.
[추정] 같은 지역·업종그룹의 시설들은 같은 M을 갖습니다. 카드에 개별 가맹점 식별자·좌표가 없기 때문에 시설별 차이를 알아낼 수 없습니다. 연면적·의사수·시설규모로 차등 가중하지 않았습니다.
[추정] 시설 수가 바뀌거나 제외 시설을 복구하면 N과 정규화 기준이 바뀌므로 반드시 전체 계산을 다시 실행해야 합니다.

## 업종 연결
[추정] 도서관에는 서점+독서실 소비를 독서문화 선호의 대리변수로 연결했습니다. 도서관 직접 매출/이용자 수가 아닙니다.
[추정] 병원은 일반/종합/치과/한방/보건 그룹으로 나누어 대응합니다. 의원과 치과의원·한방병원 등은 카드의 더 넓은 분류로 매핑됩니다.
[확실] 카페는 커피전문점, 일반/무도 유흥 주점은 유흥업소 업종으로 연결합니다. 식사 가능한 요리 주점은 결제 업종을 식별할 수 없어 M을 비웠습니다. 야간 유흥시설을 공공 개입 거점으로 추천해도 된다는 뜻은 아닙니다.
[확실] 무료 공원·주민센터의 질량을 소비로 측정할 근거가 없어 비웠습니다. 세금공과금, 놀이공원/레저타운 소비를 대신 끼워 넣지 않았습니다.
[확실] 청년센터는 사용자 요청으로 분석 범위에서 제외했습니다. 추가된 버스정류장과 서울 지하철 연계 지하도 NODE 자료를 읽어 교통시설을 추가했습니다. 춘천 철도역은 서울 자료에 포함되지 않습니다.
[확실] 지하철·시내버스 질량은 공란입니다. 고속버스/철도/여객선 소비로 임의 대체하지 않았습니다. 지하철 대표점은 실제 지하도 노드 한 개이며 역 중심이나 검증된 출입구가 아닙니다. 노드/링크 1행을 역 1곳으로 세지 않았습니다. 원본 도시명과 공간 지역이 다른 버스정류장은 재확인 대상으로 표시했습니다.
[확실] 다른 카테고리의 결제를 중복 배분하지 않도록 하나의 카드 업종은 한 질량 그룹에만 연결했습니다.

## 공간과 시점
[확실] X_COORD/Y_COORD=EPSG:5179 (UTM-K), 원본 경위도=EPSG:4326. 병원 원본 좌표(X)/(Y)는 경도/위도라 반드시 변환했습니다.
[확실] 위치는 제공된 대표점입니다. 출입구·도로망 거리를 뜻하지 않습니다. 2025년 2분기 강남·춘천 경계와 대조했습니다. 원장에서 재확인 표시된 공원/도서관은 사용 가능 목록에서 제외했습니다.
[불확실] 인프라 원장의 기준은 2023~2026년으로 2025년 소비와 다릅니다. 병원은 2025-12 이후 개설을 제외했지만 2025년 폐업 여부·월별 시설 개수는 복원하지 못했습니다. 상가의 2025년 존재 여부는 미검증입니다.
[추정] 이것은 과거 소비를 현재 시설 공급에 배분한 탐색 모델용 proxy입니다. 개별 시설의 실측 매출 또는 검증된 허프 매력도가 아닙니다.
[확실] 시설 ID 단위 중복과 배분 금액/건수 합계 보존, 질량 양수, 연령별 평균=1을 검사했습니다.

## 파일
- infrastructure_gravity_mass.csv: 요청 컬럼을 앞에 둔 전체 원장, 뒤에 출처·매칭·좌표상태·사용가능 여부
- infrastructure_gravity_mass_ready.csv: 좌표·다섯 연령 질량이 모두 있는 하위집합
- infrastructure_mass_detail.csv: 시설×연령 상세와 월평균, 균등배분액/건수, M
- card_industry_monthly.csv: 지역×월×업종×연령 카드 원집계
- card_industry_six_month_average.csv: 지역×업종×연령별 여섯 달 총액/건수와 월평균
- card_category_monthly.csv: 질량 업종그룹별 월 집계
- region_category_age_mass.csv: 그룹별 N, 월평균, 배분값, 정규화
- industry_mapping.csv: 업종 매핑과 대리변수/미지원 이유
- manual_review_and_unsupported.csv: 미산출·좌표검토 대상
- category_coverage.csv: 청년센터 제외, 지하철역·버스정류장 포함 인프라의 입력·질량 확보 범위
- transport_source_nodes.csv: 버스정류장과 지하철 연계 원본 노드 좌표·원본 ID·유형·지역명 검토 상태
- data_audit.json: 처리 건수·제외 사유·공식·검증 기록
- build_gravity_mass.py: 재현 코드 (ROOT/OUT 경로 수정 후 실행)
"""
(OUT/'README.md').write_text(readme,encoding='utf-8')


# Surrounding-cafe model replaces the prior category-specific proxy masses.
from scipy.spatial import cKDTree
RADII=[100,300,500]
PRIMARY_RADIUS=300
BASE_MASS=1.0  # Explicit modeling baseline: no nearby cafe does not imply zero facility attractiveness.
for filename in ['infrastructure_gravity_mass.csv','infrastructure_gravity_mass_ready.csv','infrastructure_mass_detail.csv','README.md','data_audit.json']:
 src=OUT/filename
 if src.exists():
  target={'infrastructure_gravity_mass.csv':'infrastructure_direct_card_mass.csv','infrastructure_gravity_mass_ready.csv':'infrastructure_direct_card_mass_ready.csv','infrastructure_mass_detail.csv':'direct_card_mass_detail.csv','README.md':'README_direct_card.md','data_audit.json':'data_audit_direct_card.json'}[filename]
  src.replace(OUT/target)
base=final.copy()
for age in AGES:base[f'ORIGINAL_CARD_M_{age}']=base[f'M_{age}'];base[f'M_{age}']=np.nan
usable=base.coord_valid & base.location_status.eq('inside_expected_region') & ~base.coord_review_flag & base.temporal_status.ne('opened_after_2025')
base['SURROUND_ELIGIBLE']=usable
# Cafes have independent store IDs and geocoded source locations; include all age-independent cafe supply points.
cafes=base[usable & base.mass_group.eq('social_cafe')].copy()
assert not cafes.facility_id.duplicated().any()
supply=cafes.groupby('region').size().rename('REGION_CAFE_COUNT').reset_index()
cafe_means=means[means.mass_group.eq('social_cafe')][['region','age','monthly_mean_amount','monthly_mean_count','observed_months']].merge(supply,on='region',validate='many_to_one')
cafe_means['PER_CAFE_MONTHLY_AMOUNT']=cafe_means.monthly_mean_amount/cafe_means.REGION_CAFE_COUNT
cafe_means['PER_CAFE_MONTHLY_COUNT']=cafe_means.monthly_mean_count/cafe_means.REGION_CAFE_COUNT
save(cafe_means,'surrounding_cafe_region_age_coefficients.csv')
# Point buffers are straight-line, share no target-flow labels, and exclude each cafe target's own store.
parts=[];links=[]
for region,tgt in base[usable].groupby('region'):
 refs=cafes[cafes.region==region].reset_index(drop=True)
 if refs.empty:raise ValueError(f'{region}: no cafe source points')
 xy=refs[['X_COORD','Y_COORD']].to_numpy()
 tree=cKDTree(xy)
 targets=tgt[['X_COORD','Y_COORD']].to_numpy()
 matches=tree.query_ball_point(targets,max(RADII))
 boundary=transport_boundaries[region]
 projected_boundary=gpd.GeoSeries([boundary],crs=4326).to_crs(5179).iloc[0].boundary
 edge=gpd.GeoSeries(gpd.points_from_xy(tgt.X_COORD,tgt.Y_COORD),crs=5179).distance(projected_boundary).to_numpy()
 for k,(idx,r) in enumerate(tgt.iterrows()):
  indices=np.array(matches[k],dtype=int)
  if len(indices):
   indices=indices[refs.iloc[indices].facility_id.to_numpy()!=r.facility_id]
  distances=np.sqrt(((xy[indices]-targets[k])**2).sum(axis=1)) if len(indices) else np.array([])
  for radius in RADII:
   valid=distances<=radius
   near=distances[valid]
   weighted=float(np.maximum(0,1-near/radius).sum())
   parts.append(dict(facility_id=r.facility_id,region=region,radius_m=radius,nearby_cafe_count=int(valid.sum()),distance_weighted_cafe_count=weighted,nearest_cafe_within_500m=float(distances.min()) if len(distances) else np.nan,boundary_coverage_caution=bool(edge[k]<radius)))
  for j,distance in zip(indices,distances):
   links.append(dict(facility_id=r.facility_id,cafe_facility_id=refs.iloc[j].facility_id,region=region,distance_m=round(float(distance),4)))
surround=pd.DataFrame(parts)
nearlinks=pd.DataFrame(links)
save(surround,'surrounding_cafe_supply_by_radius.csv')
save(nearlinks,'facility_cafe_pairs_within_500m.csv')
assert not (nearlinks.facility_id==nearlinks.cafe_facility_id).any()
assert not nearlinks.duplicated(['facility_id','cafe_facility_id']).any()
long=surround.merge(cafe_means,on='region',validate='many_to_many')
long['ESTIMATED_NEARBY_MONTHLY_AMOUNT']=long.distance_weighted_cafe_count*long.PER_CAFE_MONTHLY_AMOUNT
long['ESTIMATED_NEARBY_MONTHLY_COUNT']=long.distance_weighted_cafe_count*long.PER_CAFE_MONTHLY_COUNT
long['ENV_SCORE']=np.nan;long['M']=np.nan;long['M_ENV_ONLY']=np.nan
norms=[]
for (radius,age),g in long.groupby(['radius_m','age']):
 ia=g.ESTIMATED_NEARBY_MONTHLY_AMOUNT.mean()
 ic=g.ESTIMATED_NEARBY_MONTHLY_COUNT.mean()
 if ia<=0 or ic<=0:raise ValueError('No nonzero surroundings to normalize')
 raw=np.sqrt(g.ESTIMATED_NEARBY_MONTHLY_AMOUNT/ia*g.ESTIMATED_NEARBY_MONTHLY_COUNT/ic)
 env=raw/raw.mean()
 mass=(BASE_MASS+env)/(BASE_MASS+env).mean()
 long.loc[g.index,'ENV_SCORE']=env;long.loc[g.index,'M_ENV_ONLY']=env;long.loc[g.index,'M']=mass
 norms.append(dict(radius_m=int(radius),age=int(age),amount_reference_mean=float(ia),count_reference_mean=float(ic),environment_raw_mean=float(raw.mean()),base_mass=BASE_MASS))
long['estimate_status']=np.where(long.nearby_cafe_count.eq(0),'no_nearby_cafe_baseline_only','estimated_from_cafe_supply_and_region_consumption')
save(long,'surrounding_consumption_mass_detail.csv')
save(pd.DataFrame(norms),'surrounding_mass_normalization.csv')
p300=long[long.radius_m.eq(PRIMARY_RADIUS)]
wide=p300.pivot(index='facility_id',columns='age',values='M').rename(columns={20:'M_20',30:'M_30',40:'M_40',50:'M_50',60:'M_60'}).reset_index()
new=base.drop(columns=['M_20','M_30','M_40','M_50','M_60']).merge(wide,on='facility_id',how='left',validate='one_to_one')
new=new.merge(surround[surround.radius_m.eq(PRIMARY_RADIUS)],on=['facility_id','region'],how='left',validate='one_to_one')
new['READY_FOR_HUFF']=new.SURROUND_ELIGIBLE & new[['M_20','M_30','M_40','M_50','M_60']].notna().all(axis=1)
new['MASS_BASIS']='300m_주변카페공급x지역연령별소비_추정'
new['mass_status']=np.select([~new.SURROUND_ELIGIBLE,new.nearby_cafe_count.eq(0)],['coordinate_or_time_review','baseline_only_no_cafe'],default='surrounding_consumption_proxy')
new['ORIGINAL_CARD_ELIGIBILITY_REASON']=new['eligibility_reason']
new['ORIGINAL_CARD_ELIGIBLE']=new['eligible']
new['eligible']=new['SURROUND_ELIGIBLE']
new['eligibility_reason']=np.where(new['READY_FOR_HUFF'],'surrounding_consumption_proxy_or_baseline',new['ORIGINAL_CARD_ELIGIBILITY_REASON'])
new=new.rename(columns={'card_industries':'ORIGINAL_CARD_INDUSTRIES','match_type':'ORIGINAL_CARD_MATCH_TYPE'})
new=new[['명칭','카테고리','X_COORD','Y_COORD','M_20','M_30','M_40','M_50','M_60']+[c for c in new if c not in ['명칭','카테고리','X_COORD','Y_COORD','M_20','M_30','M_40','M_50','M_60']]]
# A cafe-count zero is observed supply within the chosen buffer, not actual zero facility use.
save(new,'infrastructure_gravity_mass.csv')
save(new[new.READY_FOR_HUFF],'infrastructure_gravity_mass_ready.csv')
save(new[~new.READY_FOR_HUFF],'manual_review_and_unsupported.csv')
comparison=long.pivot(index=['facility_id','age'],columns='radius_m',values='M')
sensitivity=[]
for age in AGES:
 a=comparison.xs(age,level='age')
 # Pearson correlation of average ranks equals Spearman correlation, no optional stats package.
 for r in [100,500]:
  sensitivity.append(dict(age=age,primary_radius=300,comparison_radius=r,rank_correlation=float(a[300].rank().corr(a[r].rank())),poi_count=len(a)))
save(pd.DataFrame(sensitivity),'radius_sensitivity.csv')
coverage=new.groupby(['region','카테고리'],as_index=False).agg(records=('facility_id','size'),ready=('READY_FOR_HUFF','sum'),baseline_only=('mass_status',lambda s:s.eq('baseline_only_no_cafe').sum()))
save(coverage,'category_coverage.csv')
assert len(new)==len(base) and not new.facility_id.duplicated().any()
assert not new.카테고리.eq('청년센터').any()
for age in AGES:
 assert np.isfinite(new.loc[new.READY_FOR_HUFF,f'M_{age}']).all()
 assert new.loc[new.READY_FOR_HUFF,f'M_{age}'].gt(0).all()
 assert np.isclose(new.loc[new.READY_FOR_HUFF,f'M_{age}'].mean(),1)
for radius in RADII:
 assert long[long.radius_m==radius].groupby('age').M.mean().sub(1).abs().max()<1e-10
assert new.loc[~new.SURROUND_ELIGIBLE,['M_20','M_30','M_40','M_50','M_60']].isna().all().all()
config=dict(method='surrounding cafe supply times regional age-specific consumption proxy',radius_m=PRIMARY_RADIUS,sensitivity_radii=RADII,baseline_mass=BASE_MASS,age_definition='20-29,30-39,40-49,50-59,60-69',ready=int(new.READY_FOR_HUFF.sum()),records=len(new),baseline_only=int(new.mass_status.eq('baseline_only_no_cafe').sum()),no_data=int((~new.READY_FOR_HUFF).sum()),boundary_caution=int(new.boundary_coverage_caution.fillna(False).sum()),formula='w=max(0,1-d/R); E_amount=sum(w)*regional_monthly_cafe_amount/N_cafes; E_count analogous; raw=sqrt((E_amount/mean(E_amount))*(E_count/mean(E_count))); ENV_SCORE=raw/mean(raw); M=(1+ENV_SCORE)/mean(1+ENV_SCORE)',notes=['not observed nearby sales','same-region cafes only; border omission flagged','overlapping buffers reuse context; not disjoint consumption budgets','self cafe excluded','within a region, age differences are only from regional coefficients; individual cafe age preferences unavailable','baseline 1 is a model assumption; zero-cafe points not proven unattractive','meters are Euclidean, not walking-route distance','2026 store snapshot with 2025 card data','metro node is approximate station representative; Chuncheon rail absent'])
(OUT/'data_audit.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
readme=f"""# 주변 카페 소비 기반 질량 v4 · 5개 연령
[확실] 청년센터 제외. 버스정류장·서울 지하도노드 기반 지하철 대표점 추가. 시설 {len(new):,}개 중 {int(new.READY_FOR_HUFF.sum()):,}개에 질량 산출.
[추정] 이것은 시설 반경 안 실제 결제액이 아니라, 주변 카페 공급과 해당 시군구의 연령별 커피전문점 소비를 결합한 모델용 대리변수입니다.

## 공식
[확실] 데이터2의 2025년 7~12월 커피전문점 소비를 남녀·소비자 거주지에 걸쳐 합산했습니다. 20대,30대,40대,50대,60대(60~69세)를 각각 계산합니다.
[추정] 시설 반경 R 안 카페에 w=max(0,1-d/R)을 부여합니다. 기본 R=300m이고 100m·500m 결과도 저장합니다. 직선거리이며 카페인 시설 자체의 매장은 제외합니다.
[추정] 지역 월평균 금액/해당 지역 카페 수를 카페당 평균 금액으로 둡니다. 주변 추정 소비금액=카페당 평균 금액×합계(w). 건수도 같습니다.
[추정] 금액·건수를 각각 연령별 전체 시설 평균으로 나누고 기하평균을 계산해 ENV_SCORE를 만듭니다. ENV_SCORE 자체도 평균1로 조정합니다.
[추정] 기본 M=(1+ENV_SCORE)/mean(1+ENV_SCORE). 기본 질량 1은 주변에 카페가 없다는 이유만으로 시설 자체의 매력도를 0으로 만들지 않기 위한 명시적 가정입니다. 실제 매력도 검증 결과가 아닙니다.
[확실] 주변 카페가 0개이면 ENV_SCORE=0, 기본 M=0.5입니다(전체 ENV_SCORE 평균1 기준). BASE_MASS=0으로 바꾸면 순수 주변환경 질량이 되며 무카페 시설의 M=0이 됩니다. 상세표의 M_ENV_ONLY가 그 시나리오입니다.

## 중요한 해석
[확실] 카드에는 개별 매장 좌표·실제 매장별 결제가 없으므로 주변의 실제 소비를 복원한 값이 아닙니다.
[추정] 모든 시설에 같은 방식의 주변 환경 지표를 적용했습니다. 도서관 면적·의사수·직접 소비 질량은 새로운 M에 섞지 않았습니다. 이전 M은 ORIGINAL_CARD_M_20/30/40/50/60 열과 infrastructure_direct_card_mass.csv에 보존합니다.
[확실] 같은 지역 안에서는 연령별로 카페 위치가 동일합니다. 연령 차이는 시군구 소비 계수에서만 오므로 개별 카페의 연령별 선호도 차이를 알아낸 것이 아닙니다.
[확실] 버퍼가 겹치면 같은 카페가 여러 시설의 환경 지표에 포함됩니다. 이 값들을 더해서 지역 실제 소비 총액이라고 해석하면 안 됩니다.
[불확실] 경계 밖 카페를 결합하지 않았으므로 경계 근처는 공급을 과소평가할 수 있습니다. boundary_coverage_caution으로 표시합니다.
[불확실] 상가가 2026년, 카드가 2025년이라는 시점 차이, 지하철의 대표노드 위치 오차가 남아 있습니다. 좌표 누락·공식자료 재확인·지역 외 지점·2025년 이후 개설 병원은 결측으로 남깁니다.
[추정] 카페 접근성이 시설의 사회적 고립 예방 효과를 의미하지 않습니다. 이후 허프의 시설까지 거리 항과 '시설 주변 환경'은 공간적 대상을 구분합니다.
[확실] 같은 격자·월의 유동으로 만든 활동저조 점수를 이 질량의 독립적 검증 정답으로 사용하지 않았습니다.

## 파일
- infrastructure_gravity_mass.csv: 요청한 7개 컬럼을 앞에 둔 전체 시설 원장
- infrastructure_gravity_mass_ready.csv: 좌표·다섯 연령 질량 조건을 통과한 목록
- surrounding_consumption_mass_detail.csv: 시설×반경×연령별 금액·건수 추정값과 ENV_SCORE, M, 순수 환경질량
- surrounding_cafe_supply_by_radius.csv: 반경별 카페 수·거리 가중 합계·경계 주의
- surrounding_cafe_region_age_coefficients.csv: 지역별·연령별 실제 카드 집계와 카페당 배분 계수
- facility_cafe_pairs_within_500m.csv: 원본 시설 ID와 카페 ID별 거리, 자기 매장 제외
- radius_sensitivity.csv: 300m 대비 100m/500m 질량 순위 상관
- category_coverage.csv / manual_review_and_unsupported.csv: 범위·검토 목록
- infrastructure_direct_card_mass.csv / direct_card_mass_detail.csv: 이전 직접 업종 매핑 방식의 별도 보존값
- transport_source_nodes.csv: 버스·지하철 연계 노드 원본 좌표와 유형
- 나머지 card_ 파일 / industry_mapping.csv: 원카드 집계·이전 방식 근거
- build_surrounding_mass.py: 재현 코드. 실행 시 main work/infrastructure_gravity_mass_results/실행시각에 저장
"""
(OUT/'README.md').write_text(readme,encoding='utf-8')
print('SURROUNDING RESULT',json.dumps(config,ensure_ascii=False))
