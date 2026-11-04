"""Step 4. Age-specific X, interval-censored Weibull AFT, offline 3D geographic maps.
python run_step4_aft.py --backend auto
auto uses lifelines when installed, otherwise the explicitly reported scipy MLE.
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
from pathlib import Path
import argparse,json,hashlib,warnings,math
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.spatial import Delaunay
from scipy.optimize import minimize, check_grad
from scipy.optimize._numdiff import approx_derivative
from scipy.stats import norm
ROOT=Path(__file__).resolve().parent
AGES=["20G","30G","40G","50G","60GU"]
MASS=["M_20","M_30","M_40","M_50","M_60"]
CAT={"도서관":"X_도서관","병원":"X_의료","버스정류장":"X_버스정류장","지하철역":"X_지하철역","주민센터":"X_주민센터","공원":"X_공원","사교상권":"X_사교"}
COMMON=["X_도서관","X_의료","X_버스정류장","X_공원","X_사교"]
NAMES={"20G":"20대","30G":"30대","40G":"40대","50G":"50대","60GU":"60대 이상"}
def save(df,p): df.to_csv(p,index=False,encoding="utf-8-sig")
def objgrad(theta,X,L,U):
    eta=X@theta[:-1]; rho=np.exp(theta[-1])
    lo=np.where(L>0,np.log(np.maximum(L,1e-300))-eta,0.)
    a=np.where(L>0,np.exp(np.clip(rho*lo,-700,700)),0.)
    cens=np.isinf(U)
    ll=-a.copy()
    db=(rho*a)[:,None]*X
    dr=-rho*a*lo
    ii=~cens
    if ii.any():
        hi=np.log(U[ii])-eta[ii]
        b=np.exp(np.clip(rho*hi,-700,700))
        delta=np.maximum(b-a[ii],1e-300)
        ll[ii]+=np.log(-np.expm1(-delta))
        # exp(-delta)/(1-exp(-delta)) avoids overflow for large delta.
        r=np.exp(-np.minimum(delta,745))/(-np.expm1(-delta))
        db[ii]-=(rho*delta*r)[:,None]*X[ii]
        dr[ii]+=rho*(b*hi-a[ii]*lo[ii])*r
    g=np.r_[db.sum(axis=0),dr.sum()]
    return -ll.sum(),-g

def scipy_fit(data,features):
    # Internal scaling improves conditioning; coefficients and covariance converted back.
    A=data[features].to_numpy(float)
    means=A.mean(axis=0); scales=A.std(axis=0)
    if np.any(scales<1e-12): raise ValueError("constant covariate")
    X=np.c_[np.ones(len(A)),(A-means)/scales]
    L=data.interval_lower.to_numpy(float); U=data.interval_upper.to_numpy(float)
    guess=np.r_[math.log(10),np.zeros(len(features)),0.]
    best=None; attempts=[]
    for shift in [0.,math.log(3)]:
        init=guess.copy();init[0]+=shift
        fit=minimize(objgrad,init,args=(X,L,U),jac=True,method="BFGS",options={"gtol":1e-6,"maxiter":2000})
        gradmax=float(np.max(np.abs(fit.jac)))
        attempts.append({"success":bool(fit.success),"message":str(fit.message),"grad_max":gradmax})
        if best is None or fit.fun<best.fun:best=fit
    if not np.isfinite(best.fun) or np.max(np.abs(best.jac))>.01:
        raise RuntimeError("MLE did not converge: "+str(attempts))
    H=approx_derivative(lambda t:objgrad(t,X,L,U)[1],best.x,method="3-point")
    H=(H+H.T)/2
    eig=np.linalg.eigvalsh(H)
    if eig.min()<=0:raise RuntimeError("Observed information not positive definite.")
    cov=np.linalg.inv(H)
    T=np.eye(len(best.x))
    T[0,1:-1]=-means/scales
    for k in range(len(features)):T[k+1,k+1]=1/scales[k]
    theta=T@best.x
    cov=T@cov@T.T
    se=np.sqrt(np.diag(cov))
    result=pd.DataFrame({"term":["Intercept"]+features+["log_shape"],"beta":theta,"se":se})
    result["p_value_nominal"]=2*norm.sf(np.abs(result.beta/result.se))
    result["beta_ci_lower"]=result.beta-1.96*result.se
    result["beta_ci_upper"]=result.beta+1.96*result.se
    return result,{"engine":"scipy_interval_weibull_mle","log_likelihood":-float(best.fun),"shape":float(np.exp(theta[-1])),
                   "gradient_max":float(np.max(np.abs(best.jac))),"information_condition":float(eig.max()/eig.min()),"optimizer_attempts":attempts}

def lifelines_fit(data,features):
    from lifelines import WeibullAFTFitter
    af=WeibullAFTFitter(penalizer=0.)
    with warnings.catch_warnings(record=True) as ws:
        af.fit_interval_censoring(data[features+["interval_lower","interval_upper"]],lower_bound_col="interval_lower",upper_bound_col="interval_upper")
    sm=af.summary
    rows=[]
    for term in ["Intercept"]+features:
        q=sm.loc[("lambda_",term)]
        rows.append({"term":term,"beta":q["coef"],"se":q["se(coef)"],"p_value_nominal":q["p"],"beta_ci_lower":q["coef lower 95%"],"beta_ci_upper":q["coef upper 95%"]})
    q=sm.loc[("rho_","Intercept")]
    rows.append({"term":"log_shape","beta":q["coef"],"se":q["se(coef)"],"p_value_nominal":q["p"],"beta_ci_lower":q["coef lower 95%"],"beta_ci_upper":q["coef upper 95%"]})
    return pd.DataFrame(rows),{"engine":"lifelines.WeibullAFTFitter.fit_interval_censoring","log_likelihood":float(af.log_likelihood_),"shape":float(np.exp(q["coef"])),"warnings":[str(w.message) for w in ws]}

def tests():
    rng=np.random.default_rng(417)
    X=np.c_[np.ones(30),rng.normal(size=(30,2))]
    L=rng.integers(0,5,30).astype(float);U=L+1;U[::4]=np.inf;L[::4]=5
    t=np.array([2.,.1,-.2,.2])
    err=check_grad(lambda p:objgrad(p,X,L,U)[0],lambda p:objgrad(p,X,L,U)[1],t)
    if err>1e-4:raise AssertionError("gradient error "+str(err))
    # Synthetic known direction and parameters, interval observations/right censoring.
    n=2500
    z=rng.normal(size=n)
    time=np.exp(1.5+.4*z)*rng.weibull(1.4,n)
    lower=np.minimum(np.floor(time),5)
    upper=np.where(time<5,lower+1,np.inf)
    sim=pd.DataFrame({"x":z,"interval_lower":lower,"interval_upper":upper})
    r,_=scipy_fit(sim,["x"])
    b=float(r.loc[r.term.eq("x"),"beta"].iloc[0])
    assert abs(b-.4)<.1
    return {"analytic_gradient_error":float(err),"synthetic_true_beta":.4,"synthetic_estimated_beta":b}

def main(backend="auto",output=None):
    out=Path(output or ROOT/"results");out.mkdir(parents=True,exist_ok=True)
    inp=ROOT/"inputs"
    grids=pd.read_csv(inp/"grid_locations.csv",dtype={"GRID_ID":str})
    mass=pd.read_csv(inp/"mass_all_ages.csv",dtype={"facility_id":str})
    labels=pd.read_csv(inp/"patient_survival_labels.csv",dtype={"GRID_ID":str})
    intervals=pd.read_csv(inp/"patient_survival_interval_labels.csv",dtype={"GRID_ID":str})
    params=pd.read_csv(inp/"normalization_parameters.csv")
    if grids.GRID_ID.duplicated().any() or mass.facility_id.duplicated().any():raise ValueError("Duplicate input keys")
    if labels.duplicated(["GRID_ID","AGE"]).any():raise ValueError("Duplicate labels")
    ready=mass.READY_FOR_HUFF.astype(str).str.lower().isin(["true","1"])
    mass=mass.loc[ready].copy()
    assert np.isfinite(mass[MASS+["X_COORD","Y_COORD"]]).all().all()
    matrices={};raws={}
    for age in AGES:
        matrices[age]=grids.copy();raws[age]=grids.copy()
        for c in CAT.values():matrices[age][c]=np.nan;raws[age][c]=np.nan
    coverage=[]
    for region,g in grids.groupby("REGION"):
        for category,col in CAT.items():
            f=mass[(mass.region==region)&mass["카테고리"].eq(category)]
            coverage.append({"REGION":region,"category":category,"column":col,"n_poi":len(f)})
            if f.empty:continue
            values=np.empty((len(g),5))
            for start in range(0,len(g),512):
                d=cdist(g.iloc[start:start+512][["X_COORD","Y_COORD"]],f[["X_COORD","Y_COORD"]])
                values[start:start+512]=np.maximum(d,1.)**-2 @ f[MASS].to_numpy()
            q=params[params.column.eq(col)].iloc[0]
            for k,age in enumerate(AGES):
                raws[age].loc[g.index,col]=values[:,k]
                matrices[age].loc[g.index,col]=(np.log1p(values[:,k]/q.positive_raw_median)-q.log_min)/(q.log_max-q.log_min)
    save(pd.DataFrame(coverage),out/"category_coverage.csv")
    original=pd.read_csv(inp/"step2_M20_matrix.csv",dtype={"GRID_ID":str}).set_index("GRID_ID")
    check=matrices["20G"].set_index("GRID_ID").loc[original.index,list(CAT.values())]
    assert np.allclose(check.to_numpy(),original[list(CAT.values())].to_numpy(),equal_nan=True,rtol=1e-10,atol=1e-12)
    for age in AGES:
        save(matrices[age],out/("grid_huff_dosage_matrix_"+age+".csv"))
        save(raws[age],out/("grid_huff_dosage_raw_"+age+".csv"))
    test_result=tests()
    if backend=="auto":
        try:import lifelines; backend="lifelines"
        except ImportError:backend="scipy"
    if backend not in ["lifelines","scipy"]:raise ValueError(backend)
    fitfun=lifelines_fit if backend=="lifelines" else scipy_fit
    comparison=[];diagnostics=[];predictions=[];model_fields={}
    for age in AGES:
        lab=labels.loc[labels.AGE.eq(age)]
        bounds=intervals.loc[intervals.AGE.eq(age),["GRID_ID","interval_lower","interval_upper"]]
        data=lab.merge(bounds,on="GRID_ID",validate="one_to_one").merge(matrices[age],on=["GRID_ID","REGION","DONG"],validate="one_to_one",how="left",indicator=True)
        assert data["_merge"].eq("both").all()
        data["REGION_CHUNCHEON"]=data.REGION.eq("춘천시").astype(int)
        for scope in ["pooled_common","강남구","춘천시"]:
            d=data.copy() if scope=="pooled_common" else data[data.REGION.eq(scope)].copy()
            fs=COMMON+["REGION_CHUNCHEON"] if scope=="pooled_common" else [c for c in CAT.values() if d[c].notna().all()]
            fs=[c for c in fs if d[c].std()>1e-12]
            if d[fs].isna().any().any():raise ValueError("Missing exposure; never impute absent POI as zero.")
            result,diag=fitfun(d,fs)
            result["AGE"]=age;result["model_scope"]=scope
            result["time_ratio"]=np.exp(np.clip(result.beta,-700,700))
            result["time_ratio_ci_lower"]=np.exp(np.clip(result.beta_ci_lower,-700,700))
            result["time_ratio_ci_upper"]=np.exp(np.clip(result.beta_ci_upper,-700,700))
            result.loc[result.term.eq("log_shape"),["time_ratio","time_ratio_ci_lower","time_ratio_ci_upper"]]=np.nan
            result["time_ratio_per_0_1_X"]=np.exp(np.clip(result.beta*.1,-700,700))
            result["p_value"]=result["p_value_nominal"]
            result["parameter_role"]=np.where(result.term.isin(COMMON+["X_지하철역","X_주민센터"]),"infrastructure",np.where(result.term.eq("REGION_CHUNCHEON"),"region_adjustment",np.where(result.term.eq("Intercept"),"log_scale_intercept","log_shape")))
            result.loc[result.term.isin(["Intercept","log_shape"]),["time_ratio","time_ratio_ci_lower","time_ratio_ci_upper","time_ratio_per_0_1_X"]]=np.nan
            result["engine"]=diag["engine"]
            comparison.append(result)
            diag.update(AGE=age,model_scope=scope,n=len(d),events=int(d.event_observed.sum()),features=fs)
            diagnostics.append(diag)
            print(age,scope,len(d),diag["engine"],diag["log_likelihood"],flush=True)
            # Training descriptive risk in observed horizon, no extrapolated median claims.
            beta=result.set_index("term").beta
            eta=beta["Intercept"]+d[fs].to_numpy()@beta[fs].to_numpy()
            eventprob=-np.expm1(-np.exp(np.clip(diag["shape"]*(np.log(5.)-eta),-700,700)))
            pp=d[["GRID_ID","AGE","REGION","DONG","duration_T","event_observed"]].copy()
            pp["model_scope"]=scope;pp["fitted_event_probability_by_month5"]=eventprob
            predictions.append(pp)
            if scope=="pooled_common":
                model_fields[age]=(matrices[age][COMMON].to_numpy()@beta[COMMON].to_numpy()).tolist()
                save(d.drop(columns="_merge"),out/("aft_training_"+age+".csv"))
    comp=pd.concat(comparison,ignore_index=True)
    save(comp,out/"aft_age_comparison_results.csv")
    save(comp[comp.model_scope.eq("pooled_common")],out/"aft_primary_age_comparison.csv")
    wide=comp[comp.model_scope.eq("pooled_common")&comp.term.isin(COMMON)].pivot(index="term",columns="AGE",values=["beta","time_ratio","p_value_nominal"])
    wide.to_csv(out/"aft_primary_age_comparison_wide.csv",encoding="utf-8-sig")
    save(pd.concat(predictions,ignore_index=True),out/"aft_fitted_training_probabilities.csv")
    with (out/"model_diagnostics.json").open("w",encoding="utf-8") as f:json.dump(diagnostics,f,ensure_ascii=False,indent=2)
    metadata={"backend":backend,"lambda":2.,"distance_floor_m":1.,"normalization":"Step2 M20 reference reused for all ages; other ages may exceed [0,1].",
              "primary":"Five common infrastructure types + region indicator; seven/five type regional supplements.",
              "M60_definition":"60-69, mismatched to SK 60GU (60+); oldest model is proxy, not strict age alignment.",
              "p_values":"Naive model-based Wald p-values, no spatial clustering or causal identification.",
              "retrospective_only":"Full-period mass and later dated source covariates; no prospective validation.",
              "interval_fit":"Event (L,U], right censor (L,inf), no exact-time event flag passed to lifelines interval API.",
              "tests":test_result,"M20_reproduction":"passed","models":len(diagnostics),
              "inputs_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inp.iterdir() if p.is_file()}}
    (out/"run_metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    from step4_maps import make_maps
    make_maps(grids,raws,matrices,model_fields,comp,json.loads((inp/"boundaries.json").read_text(encoding="utf-8")),out)
    return comp

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend",choices=["auto","lifelines","scipy"],default="auto")
    ap.add_argument("--output-dir",type=Path)
    a=ap.parse_args()
    main(a.backend,a.output_dir)
