"""Reproduce alpha-adjusted five-month AFT probabilities from saved X and models."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=Path(__file__).resolve().parent/'results');p.add_argument('--output',type=Path);args=p.parse_args()
r=args.results;meta=json.loads((r/'run_metadata.json').read_text(encoding='utf-8'));models=json.loads((r/'full_refit_models.json').read_text(encoding='utf-8'));out=[]
for age,m in models.items():
 d=pd.read_csv(r/f'grid_huff_dosage_matrix_{age}.csv',dtype={'GRID_ID':str});features=meta['features'][:-1];A=np.c_[d[features].to_numpy(),d.REGION.eq('춘천시').to_numpy(float)];X=np.c_[np.ones(len(A)),(A-np.array(m['mu']))/np.array(m['sd'])];theta=np.array(m['theta']);eta=X@theta[:-1];shape=np.exp(theta[-1]);q=d[['GRID_ID','REGION','DONG','AGE']].copy();q['prob_event_by_month5']=-np.expm1(-np.exp(np.clip(shape*(np.log(5)-eta),-50,50)));out.append(q)
output=args.output or r/'all_grid_alpha_probabilities.csv';pd.concat(out,ignore_index=True).to_csv(output,index=False,encoding='utf-8-sig');print('Wrote',output)
