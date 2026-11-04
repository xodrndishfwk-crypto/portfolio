"""Step 3: first transition into the existing monthly selection set (not clinical isolation).
Run: python build_survival_labels.py --scores PATH --output-dir PATH
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd

MONTHS = ["202507","202508","202509","202510","202511","202512"]
AGES = ["20G","30G","40G","50G","60GU"]
RATES = {"20G":.244,"30G":.265,"40G":.295,"50G":.372,"60GU":.394}
DEFAULT = Path(r"./private_inputs/main_work\monthly_grid_results\20261025_195726_925731\04_all_scores.csv")

def trace(states):
    """True=selected, False=observed unselected, None=unobserved. July is t=0."""
    if states[0] is None:
        return dict(status="missing_baseline", duration_T=None, event_observed=None, interval_lower=None, interval_upper=None, last_index=None)
    if states[0]:
        return dict(status="baseline_selected", duration_T=None, event_observed=None, interval_lower=None, interval_upper=None, last_index=0)
    last = 0
    for t in range(1,6):
        if states[t] is None:
            if last == 0:
                return dict(status="no_followup", duration_T=None, event_observed=None, interval_lower=None, interval_upper=None, last_index=0)
            return dict(status="censored_missing", duration_T=last, event_observed=0, interval_lower=last, interval_upper=np.inf, last_index=last)
        if states[t]:
            return dict(status="event", duration_T=t, event_observed=1, interval_lower=t-1, interval_upper=t, last_index=t)
        last = t
    return dict(status="censored_end", duration_T=5, event_observed=0, interval_lower=5, interval_upper=np.inf, last_index=5)

def synthetic_checks():
    cases = [
        ([False,True,False,False,False,False],("event",1,1)),
        ([False,False,False,False,False,True],("event",5,1)),
        ([False]*6,("censored_end",5,0)),
        ([True]*6,("baseline_selected",None,None)),
        ([None,False,False,False,False,False],("missing_baseline",None,None)),
        ([False,None,True,False,False,False],("no_followup",None,None)),
        ([False,False,None,True,False,False],("censored_missing",1,0)),
        ([False,False,True,None,None,None],("event",2,1)),
    ]
    for state, want in cases:
        got=trace(state)
        assert (got["status"],got["duration_T"],got["event_observed"])==want
    return len(cases)

def main(scores, output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    cols=["GRID_ID","DONG","REGION","X_COORD","Y_COORD","AGE","STD_YM","SELECTED","TARGET_RATE","ACTIVITY_RESIDUAL"]
    df=pd.read_csv(scores,usecols=cols,dtype={"GRID_ID":str,"AGE":str,"STD_YM":str},encoding="utf-8-sig")
    df=df[df.STD_YM.isin(MONTHS)].copy()
    if df.empty or set(df.AGE)!=set(AGES): raise ValueError("Expected all five age groups.")
    if df.duplicated(["GRID_ID","AGE","STD_YM"]).any(): raise ValueError("Duplicate grid-age-month.")
    flags=df.SELECTED.astype(str).str.strip().str.lower().map({"true":True,"false":False,"1":True,"0":False})
    if flags.isna().any(): raise ValueError("Missing or unrecognized SELECTED flag.")
    df["SELECTED"]=flags
    if not np.isfinite(df.ACTIVITY_RESIDUAL).all(): raise ValueError("Nonfinite score is not an observed healthy record.")
    for age,rate in RATES.items():
        if not np.allclose(df.loc[df.AGE.eq(age),"TARGET_RATE"],rate): raise ValueError("Unexpected selection quota: "+age)
    if df.groupby("GRID_ID")[["DONG","REGION","X_COORD","Y_COORD"]].nunique().gt(1).any().any():
        raise ValueError("Grid metadata changes across months.")
    meta=df.drop_duplicates("GRID_ID").set_index("GRID_ID")[["DONG","REGION","X_COORD","Y_COORD"]]
    pivot=df.pivot(index=["GRID_ID","AGE"],columns="STD_YM",values="SELECTED").reindex(columns=MONTHS)
    residual=df.pivot(index=["GRID_ID","AGE"],columns="STD_YM",values="ACTIVITY_RESIDUAL").reindex(columns=MONTHS)
    rows=[]
    meta_records=meta.to_dict("index")
    residual_values=residual.reindex(pivot.index).to_numpy()
    for row_number, ((gid,age), values) in enumerate(zip(pivot.index, pivot.to_numpy())):
        states=[None if pd.isna(x) else bool(x) for x in values]
        result=trace(states)
        last=result.pop("last_index")
        row={"GRID_ID":gid,**meta_records[gid],"AGE":age,**result,
             "baseline_month":"202507","last_followup_month":MONTHS[last] if last is not None else "",
             "event_month":MONTHS[int(result["duration_T"])] if result["event_observed"]==1 else "",
             "observed_month_count":sum(x is not None for x in states),"target_rate":RATES[age]}
        for k,m in enumerate(MONTHS):
            row["selected_"+m]=states[k]
            row["residual_"+m]=residual_values[row_number,k]
        rows.append(row)
    audit=pd.DataFrame(rows)
    for c in ["duration_T","event_observed"]:
        audit[c]=audit[c].astype("Int64")
    keep=audit.status.isin(["event","censored_end","censored_missing"])
    labels=audit.loc[keep,["GRID_ID","DONG","REGION","AGE","duration_T","event_observed"]].copy()
    interval=audit.loc[keep,["GRID_ID","DONG","REGION","AGE","interval_lower","interval_upper","event_observed","status"]].copy()
    assert len(audit)==len(pivot)
    assert not labels.duplicated(["GRID_ID","AGE"]).any()
    assert labels.duration_T.between(1,5).all()
    assert (interval.loc[interval.event_observed.eq(1),"interval_upper"]>interval.loc[interval.event_observed.eq(1),"interval_lower"]).all()
    # Independent vectorized check of complete-panel outcomes.
    complete=pivot.notna().all(axis=1)&pivot["202507"].eq(False)
    cp=pivot.loc[complete,MONTHS[1:]].astype(bool).to_numpy()
    expected_event=cp.any(axis=1).astype(int)
    expected_time=np.where(expected_event,cp.argmax(axis=1)+1,5)
    observed=labels.set_index(["GRID_ID","AGE"]).loc[pivot.index[complete]]
    assert np.array_equal(observed.event_observed.astype(int).to_numpy(),expected_event)
    assert np.array_equal(observed.duration_T.astype(int).to_numpy(),expected_time)
    def save(data,name): data.to_csv(output/name,index=False,encoding="utf-8-sig")
    save(labels,"patient_survival_labels.csv")
    save(interval,"patient_survival_interval_labels.csv")
    save(audit,"patient_survival_audit.csv")
    save(audit.loc[~keep],"excluded_baseline_and_no_followup.csv")
    for age in AGES:
        save(labels.loc[labels.AGE.eq(age)],"patient_survival_labels_"+age+".csv")
    summary=audit.groupby(["REGION","AGE","status"],dropna=False).size().rename("count").reset_index()
    save(summary,"label_summary.csv")
    quota=df.groupby(["REGION","AGE","STD_YM"]).agg(n=("GRID_ID","size"),selected=("SELECTED","sum"),target_rate=("TARGET_RATE","first")).reset_index()
    quota["expected_floor"]=np.floor(quota.n*quota.target_rate).astype(int)
    quota["matches_floor"]=quota.selected.eq(quota.expected_floor)
    if not quota.matches_floor.all(): raise ValueError("Existing selection counts disagree with quotas.")
    save(quota,"monthly_selection_check.csv")
    h=hashlib.sha256()
    with open(scores,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    metadata={"input":str(Path(scores).resolve()),"input_sha256":h.hexdigest(),"months":MONTHS,
              "quota":RATES,"event_definition":"first observed SELECTED=True after unselected July",
              "threshold_warning":"Assumed relative screening quotas, NOT official flow-percentile diagnostic thresholds.",
              "time_origin":"July=0; August=1; December=5",
              "missing_policy":"Stop at first missing month. Censor at last contiguous observed unselected month; exclude zero followup. Never resume.",
              "duration_T":"Upper endpoint of first event interval; last observed time for censoring. Integer approximation for ordinary right-censored AFT.",
              "interval_upper_inf":"Right-censored bounds use inf. Exact event time is not observed.",
              "age_note":"60GU is SK flow population age 60+, not card M_60 age 60-69.",
              "leakage_note":"Existing selection and X use retrospective/full-period covariates; results are exploratory, not prospective or causal.",
              "label_rows":len(labels),"audit_rows":len(audit),"events":int(labels.event_observed.sum()),
              "complete_panel_vector_checks":int(complete.sum()),"synthetic_cases_passed":synthetic_checks(),
              "quotas_verified":bool(quota.matches_floor.all())}
    (output/"run_metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(metadata,ensure_ascii=False,indent=2))
    print(summary.to_string(index=False))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scores",type=Path,default=DEFAULT)
    p.add_argument("--output-dir",type=Path,default=Path(__file__).resolve().parent/"results")
    a=p.parse_args()
    main(a.scores,a.output_dir)
