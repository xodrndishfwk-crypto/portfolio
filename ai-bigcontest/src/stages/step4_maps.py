"""Offline map renderer: exact UTM-K footprints, no API, no unregistered raster."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.spatial import Delaunay
from shapely.geometry import shape,Point
from pyproj import Transformer

HTML=r"""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · 3D 인프라 중력장</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0c1424;color:#e4edf8;font:15px "Malgun Gothic",sans-serif}
header{padding:22px 28px 14px;background:#111e34;border-bottom:1px solid #2d4059}h1{margin:0 0 8px;font-size:25px}p{margin:7px 0;line-height:1.6;color:#bdcddd}
nav{display:flex;gap:9px;flex-wrap:wrap;padding:12px 28px}select,button,a.btn{color:#dcecff;background:#1b304e;border:1px solid #4c6789;border-radius:7px;padding:8px;cursor:pointer;text-decoration:none}
.note{margin:0 28px 12px;padding:10px;background:#17283f;border-left:3px solid #53dbc7;font-size:13px}
.plots{display:grid;grid-template-columns:1.8fr 1fr;gap:14px;padding:0 28px}section{background:#111e34;border:1px solid #293d58;border-radius:10px;overflow:hidden}
h2{font-size:16px;margin:14px 16px 2px}canvas{display:block;width:100%;height:570px;touch-action:none}
.legend{padding:10px 18px;font-size:12px}.ramp{display:inline-block;width:180px;height:10px;background:linear-gradient(90deg,#440154,#3b528b,#21918c,#5ec962,#fde725)}
#info{min-height:25px;color:#7fe0d1}.tbl{margin:18px 28px;padding:16px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:9px;border-bottom:1px solid #304259;text-align:right}td:first-child,th:first-child{text-align:left}
footer{padding:0 28px 24px;font-size:12px;color:#abbcd1}@media(max-width:950px){.plots{grid-template-columns:1fr}canvas{height:450px}}
</style>
<header><h1>__TITLE__ · 뒤집은 인프라 중력장</h1><p>실제 행정동 경계 위에서 위치별 중력 크기를 아래로 펼쳐 봅니다. 깊이는 시각화용 무차원 값이며 지형·고도·생존개월이 아닙니다.</p></header>
<nav><select id="region"></select><select id="field"></select><select id="extent"><option value="focus">밀집 지역 확대</option><option value="all">전체 행정경계</option></select><button id="reset">시점 초기화</button><label><input id="contour" type="checkbox" checked> 등고선</label><a class="btn" href="index.html">연령 비교로</a></nav>
<div class="note" id="note"></div>
<div class="plots"><section><h2>3차원 · 드래그 회전 / 휠 확대</h2><canvas id="three"></canvas><div class="legend"><span class="ramp"></span> 낮음 → 높음 · 같은 항목은 모든 연령·지역에서 같은 기준</div></section>
<section><h2>2차원 실제 위치 · 마우스로 값 확인</h2><canvas id="flat"></canvas><div class="legend" id="info">미관측 공간은 빈칸으로 유지합니다.</div></section></div>
<section class="tbl"><h2>이 연령의 공통 5종 AFT 계수</h2><p>β와 p는 탐색적 연관성입니다. 공간 상관을 보정하지 않은 모형 기반 p-value이며, 인과 효과가 아닙니다.</p><table><thead><tr><th>변수</th><th>β</th><th>Time Ratio</th><th>95% CI</th><th>p (nominal)</th></tr></thead><tbody>__ROWS__</tbody></table></section>
<footer>좌표: EPSG:5179, 행정동 경계: 2025년 2분기. 삼각형 변 길이 100m 초과 또는 지역 밖 중심점은 연결하지 않습니다. 외부 지도 API와 인터넷 연결 없이 작동합니다.<br>60대 이상 표시는 통신사 60세 이상 라벨 + 카드 60~69세 질량 대용치입니다. X와 라벨은 후향적 분석 자료입니다.</footer>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
"use strict";
const DATA=JSON.parse(document.getElementById("data").textContent),reg=document.getElementById("region"),field=document.getElementById("field");
for(const r of Object.keys(DATA.regions)){let o=new Option(r,r);reg.add(o);}
for(const [k,v] of Object.entries(DATA.fields)){field.add(new Option(v.label,k));}
let az=-.65,el=.82,zoom=1,drag=null,frame=null;
const c3=document.getElementById("three"),c2=document.getElementById("flat");
const stops=[[68,1,84],[59,82,139],[33,145,140],[94,201,98],[253,231,37]];
function color(v,alpha=1){v=Math.max(0,Math.min(1,v));const n=v*4,i=Math.min(3,Math.floor(n)),t=n-i;
return "rgba("+stops[i].map((x,k)=>Math.round(x*(1-t)+stops[i+1][k]*t)).join(",")+","+alpha+")";}
function setup(c){let r=c.getBoundingClientRect(),d=Math.min(window.devicePixelRatio||1,2);c.width=Math.round(r.width*d);c.height=Math.round(r.height*d);let ctx=c.getContext("2d");ctx.setTransform(d,0,0,d,0,0);ctx.clearRect(0,0,r.width,r.height);return {ctx,w:r.width,h:r.height};}
function draw(){
frame=null;const D=DATA.regions[reg.value],F=DATA.fields[field.value],V=D.fields[field.value],missing=V===null;
document.getElementById("note").textContent=F.note+(missing?" | 이 지역은 해당 인프라 좌표 자료가 없어 표시하지 않습니다.":"");
const a=setup(c3),b=setup(c2),focus=document.getElementById("extent").value!=="all",view=focus?D.focus_bounds:D.bounds,mid=[(view[0]+view[2])/2,(view[1]+view[3])/2],span=Math.max(view[2]-view[0],view[3]-view[1]);
function pos(p){return [(p[0]-mid[0])/span,(p[1]-mid[1])/span];}
function project(p,z){let [x,y]=pos(p),u=x*Math.cos(az)-y*Math.sin(az),v=x*Math.sin(az)+y*Math.cos(az);
return [a.w/2+u*Math.min(a.w,a.h)*.78*zoom,a.h*.45+(-v*Math.sin(el)-z*.33*Math.cos(el))*Math.min(a.w,a.h)*.78*zoom,v*Math.cos(el)-z*.33*Math.sin(el)];}
const bb=view,scale=Math.min((b.w-50)/(bb[2]-bb[0]),(b.h-60)/(bb[3]-bb[1]));
function flat(p){return [b.w/2+(p[0]-mid[0])*scale,b.h/2-(p[1]-mid[1])*scale];}
function path(ctx,points,fn,close){ctx.beginPath();points.forEach((p,i)=>{let q=fn(p);i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]);});if(close)ctx.closePath();}
for(const f of D.boundaries){for(const ring of f.rings){path(a.ctx,ring,p=>project(p,-1.4),true);a.ctx.fillStyle="#17263a";a.ctx.fill();path(b.ctx,ring,flat,true);b.ctx.fillStyle="#17263a";b.ctx.fill();}}
if(!missing){
 const vals=V,zz=vals.map(v=>-v/F.scale),colors=vals.map(v=>(v-F.lo)/(F.hi-F.lo||1)),pp=D.points.map((p,i)=>project(p,zz[i])),fp=D.points.map(flat);
 const order=D.triangles.map(t=>({t,depth:(pp[t[0]][2]+pp[t[1]][2]+pp[t[2]][2])/3})).sort((x,y)=>y.depth-x.depth);
 for(const {t} of order){let avg=(colors[t[0]]+colors[t[1]]+colors[t[2]])/3;a.ctx.beginPath();b.ctx.beginPath();t.forEach((i,k)=>{k?a.ctx.lineTo(pp[i][0],pp[i][1]):a.ctx.moveTo(pp[i][0],pp[i][1]);k?b.ctx.lineTo(fp[i][0],fp[i][1]):b.ctx.moveTo(fp[i][0],fp[i][1]);});a.ctx.closePath();b.ctx.closePath();a.ctx.fillStyle=color(avg,.94);a.ctx.fill();b.ctx.fillStyle=color(avg,.86);b.ctx.fill();}
 // Every observed grid remains visible, including isolated cells without triangles.
 for(let i=0;i<fp.length;i++){b.ctx.fillStyle=color(colors[i],.9);b.ctx.fillRect(fp[i][0]-1.2,fp[i][1]-1.2,2.4,2.4);}
 if(document.getElementById("contour").checked){
 for(let k=1;k<8;k++){let level=F.lo+(F.hi-F.lo)*k/8;
 a.ctx.beginPath();b.ctx.beginPath();
 for(const t of D.triangles){let hits=[];
 for(let e=0;e<3;e++){let i=t[e],j=t[(e+1)%3];if((vals[i]<level&&vals[j]>=level)||(vals[j]<level&&vals[i]>=level)){let u=(level-vals[i])/(vals[j]-vals[i]);hits.push([D.points[i][0]+u*(D.points[j][0]-D.points[i][0]),D.points[i][1]+u*(D.points[j][1]-D.points[i][1])]);}}
 if(hits.length===2){let p=project(hits[0],-level/F.scale),q=project(hits[1],-level/F.scale);a.ctx.moveTo(p[0],p[1]);a.ctx.lineTo(q[0],q[1]);p=flat(hits[0]);q=flat(hits[1]);b.ctx.moveTo(p[0],p[1]);b.ctx.lineTo(q[0],q[1]);}}
 a.ctx.strokeStyle="rgba(245,252,255,.55)";a.ctx.lineWidth=.65;a.ctx.stroke();b.ctx.strokeStyle="rgba(245,252,255,.55)";b.ctx.lineWidth=.65;b.ctx.stroke();
 }}
}
for(const f of D.boundaries){for(const ring of f.rings){path(a.ctx,ring,p=>project(p,0),false);a.ctx.strokeStyle="rgba(202,222,246,.45)";a.ctx.lineWidth=.6;a.ctx.stroke();path(b.ctx,ring,flat,false);b.ctx.strokeStyle="#dce9fb";b.ctx.lineWidth=.6;b.ctx.stroke();}
 const q=flat(f.label);b.ctx.fillStyle="#eef5ff";b.ctx.font="10px Malgun Gothic,sans-serif";b.ctx.fillText(f.name,q[0],q[1]);}
a.ctx.fillStyle="#aebfd4";a.ctx.font="12px Malgun Gothic,sans-serif";a.ctx.fillText("지리적 가로·세로 비율 유지 · 높이는 무차원",15,a.h-15);
b.ctx.fillStyle="#aebfd4";b.ctx.font="11px Malgun Gothic,sans-serif";b.ctx.fillText("EPSG:5179 · 실제 행정동 경계",10,b.h-12);
c2.onmousemove=e=>{if(missing)return;let rect=c2.getBoundingClientRect(),px=e.clientX-rect.left,py=e.clientY-rect.top,best=-1,dist=144;
D.points.forEach((p,i)=>{let q=flat(p),d=(q[0]-px)**2+(q[1]-py)**2;if(d<dist){best=i;dist=d;}});
document.getElementById("info").textContent=best<0?"미관측 공간은 빈칸입니다.":D.dongs[best]+" · "+F.label+" = "+V[best].toPrecision(5)+" · 경도 "+D.lonlat[best][0].toFixed(5)+" / 위도 "+D.lonlat[best][1].toFixed(5);};
}
function request(){if(frame===null)frame=requestAnimationFrame(draw);}
c3.onpointerdown=e=>{drag=[e.clientX,e.clientY];c3.setPointerCapture(e.pointerId);};
c3.onpointermove=e=>{if(drag){az+=(e.clientX-drag[0])*.008;el=Math.max(.1,Math.min(1.5,el+(e.clientY-drag[1])*.006));drag=[e.clientX,e.clientY];request();}};
c3.onpointerup=()=>drag=null;c3.onpointercancel=()=>drag=null;
c3.addEventListener("wheel",e=>{e.preventDefault();zoom=Math.max(.5,Math.min(5,zoom*Math.exp(-e.deltaY*.001)));request();},{passive:false});
reg.onchange=()=>{az=-.65;el=.82;zoom=1;request();};field.onchange=request;document.getElementById("extent").onchange=request;document.getElementById("contour").onchange=request;
document.getElementById("reset").onclick=()=>{az=-.65;el=.82;zoom=1;request();};
window.addEventListener("resize",request);draw();
</script></html>"""

def make_maps(grids,raws,matrices,model_fields,comp,boundaries,out):
    from run_step4_aft import AGES,COMMON,CAT,NAMES
    fields={}
    values={}
    for key in ["total"]+list(CAT.values())+["beta_effect"]:
        values[key]={}
        for age in AGES:
            if key=="total":v=raws[age][COMMON].sum(axis=1,min_count=len(COMMON)).to_numpy()
            elif key=="beta_effect":v=np.asarray(model_fields[age])
            else:v=raws[age][key].to_numpy()
            values[key][age]=v
        allv=np.concatenate(list(values[key].values()))
        good=allv[np.isfinite(allv)]
        if key=="beta_effect":
            scale=max(abs(np.quantile(good,.005)),abs(np.quantile(good,.995)),1e-8)
            fields[key]={"label":"AFT β 가중효과 (공통5종)","scale":float(scale),"lo":float(np.quantile(good,.005)),"hi":float(np.quantile(good,.995)),
                         "note":"값=ΣβX (지역·절편 제외), 값이 클수록 모형 내 생존시간 증가 방향. 3D 높이=-값/공통기준. 인과효과·개월 아님."}
        else:
            ref=np.median(good[good>0])
            for age in AGES:values[key][age]=np.log1p(values[key][age]/ref)
            good=np.log1p(good/ref);hi=float(np.quantile(good,.995))
            fields[key]={"label":"공통 5종 총중력" if key=="total" else key[2:]+" 중력",
                         "scale":hi,"lo":0.,"hi":hi,
                         "note":"표시값=log1p(원시 중력합 / 전체 연령·지역 양수 중앙값). 3D 높이=-표시값/공통 99.5% 기준. 색상만 상위0.5% 포화. 총중력은 공통5종 합."}
    geometry={}
    tf=Transformer.from_crs(5179,4326,always_xy=True)
    for region,g in grids.groupby("REGION"):
        xy=g[["X_COORD","Y_COORD"]].to_numpy()
        tri=Delaunay(xy).simplices
        d=np.stack([np.linalg.norm(xy[tri[:,k]]-xy[tri[:,(k+1)%3]],axis=1) for k in range(3)],axis=1)
        tri=tri[d.max(axis=1)<=100.001]
        from shapely.ops import unary_union
        polygon=unary_union([shape(f["geometry"]) for f in boundaries[region]["features"]])
        tri=tri[[polygon.covers(Point(x)) for x in xy[tri].mean(axis=1)]]
        rings=[]
        for feature in boundaries[region]["features"]:
            obj=shape(feature["geometry"]); rr=[]
            for part in ([obj] if obj.geom_type=="Polygon" else obj.geoms):
                rr.append(np.round(np.asarray(part.exterior.coords)/1000,6).tolist())
                for interior in part.interiors:rr.append(np.round(np.asarray(interior.coords)/1000,6).tolist())
            label=obj.representative_point()
            rings.append({"name":feature["properties"]["name"],"rings":rr,"label":[label.x/1000,label.y/1000]})
        # Map extent includes complete administrative boundary as well as observed grid centers.
        bb=np.asarray(polygon.bounds)/1000
        mid=[(bb[0]+bb[2])/2,(bb[1]+bb[3])/2]
        lon,lat=tf.transform(xy[:,0],xy[:,1])
        bins=np.floor(xy/500).astype(int)
        unique,counts=np.unique(bins,axis=0,return_counts=True)
        center=(unique[counts.argmax()]+.5)*.5
        half=4.5 if region=="강남구" else 6.
        focus_bounds=[float(center[0]-half),float(center[1]-half),float(center[0]+half),float(center[1]+half)]
        geometry[region]={"focus_bounds":focus_bounds,"points":np.round(xy/1000,6).tolist(),"triangles":tri.tolist(),"boundaries":rings,
                          "bounds":bb.tolist(),"mid":mid,"range":float(max(bb[2]-bb[0],bb[3]-bb[1])),
                          "dongs":g.DONG.tolist(),"lonlat":np.round(np.c_[lon,lat],6).tolist(),"idx":g.index.to_numpy()}
    for age in AGES:
        regions={}
        for region,d in geometry.items():
            idx=d["idx"];regions[region]={k:v for k,v in d.items() if k!="idx"}
            regions[region]["fields"]={}
            for key in fields:
                arr=values[key][age][idx]
                regions[region]["fields"][key]=None if not np.isfinite(arr).all() else np.round(arr,8).tolist()
        rows=[]
        tab=comp[(comp.AGE==age)&comp.model_scope.eq("pooled_common")]
        for _,r in tab[tab.term.isin(COMMON)].iterrows():
            rows.append(f"<tr><td>{r.term}</td><td>{r.beta:.4f}</td><td>{r.time_ratio:.4g}</td><td>{r.time_ratio_ci_lower:.4g}–{r.time_ratio_ci_upper:.4g}</td><td>{r.p_value_nominal:.3g}</td></tr>")
        payload=json.dumps({"fields":fields,"regions":regions},ensure_ascii=False,separators=(",",":"),allow_nan=False).replace("</","<\\/")
        html=HTML.replace("__TITLE__",NAMES[age]).replace("__ROWS__","".join(rows)).replace("__PAYLOAD__",payload)
        (out/("gravity_3d_"+age+".html")).write_text(html,encoding="utf-8")
        fieldout=grids.copy();fieldout["AGE"]=age
        for key in fields:fieldout[key]=values[key][age]
        fieldout.to_csv(out/("visualization_fields_"+age+".csv"),index=False,encoding="utf-8-sig")
    index=['<!doctype html><meta charset="utf-8"><style>body{font:16px Malgun Gothic,sans-serif;background:#0c1424;color:#dfebfa;padding:32px}a{color:#67ded1}table{border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #42546b;text-align:right}</style><h1>AFT 연령 비교 · 3D 중력장</h1><p>각 연령을 열면 강남·춘천 지도와 총중력 / 인프라별 / β 가중효과를 선택할 수 있습니다.</p>']
    for age in AGES:index.append(f'<p><a href="gravity_3d_{age}.html">{NAMES[age]} · 3D 지도 열기</a></p>')
    table=comp[comp.model_scope.eq("pooled_common")&comp.term.isin(COMMON)].pivot(index="term",columns="AGE",values="beta").reindex(columns=AGES)
    index.append('<h2>공통 5종 β 비교</h2>'+table.to_html(float_format=lambda x:f"{x:.4f}"))
    index.append("<p>β 양수: 시간 증가 방향 / 음수: 감소 방향. 명목 p와 CI는 CSV 및 각 지도에서 확인하십시오.<br>관측기간은 5개월이며, 후향적 연관성 분석입니다. 60GU 라벨과 M60 질량의 연령 정의 차이가 있습니다.</p>")
    (out/"index.html").write_text("".join(index),encoding="utf-8")
    # Scientific static preview, reusable and visually verifiable without a browser.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"]="Malgun Gothic";plt.rcParams["axes.unicode_minus"]=False
    for age in AGES:
        fig=plt.figure(figsize=(15,7),facecolor="#0c1424")
        for j,(region,d) in enumerate(geometry.items()):
            ax=fig.add_subplot(1,2,j+1,projection="3d",facecolor="#111e34")
            idx=d["idx"];xy=np.asarray(d["points"]);tri=np.asarray(d["triangles"]);v=values["total"][age][idx];z=-v/fields["total"]["scale"]
            view=d["bounds"] if region=="강남구" else d["focus_bounds"]
            inside=(xy[:,0]>=view[0])&(xy[:,0]<=view[2])&(xy[:,1]>=view[1])&(xy[:,1]<=view[3])
            tri=tri[inside[tri].all(axis=1)]
            ax.plot_trisurf(xy[:,0],xy[:,1],z,triangles=tri,cmap="viridis_r",linewidth=0,antialiased=True,vmin=-1,vmax=0)
            for f in d["boundaries"]:
                for ring in f["rings"]:
                    from shapely.geometry import LineString,box
                    clipped=LineString(ring).intersection(box(*view))
                    parts=[clipped] if clipped.geom_type=="LineString" else getattr(clipped,"geoms",[])
                    for line in parts:
                        if line.is_empty or line.geom_type!="LineString":continue
                        rr=np.asarray(line.coords);ax.plot(rr[:,0],rr[:,1],np.zeros(len(rr)),color="#a8c5e0",lw=.4,alpha=.65)
            view=d["bounds"] if region=="강남구" else d["focus_bounds"]
            ax.set_xlim(view[0],view[2]);ax.set_ylim(view[1],view[3])
            dx=view[2]-view[0];dy=view[3]-view[1]
            ax.set_box_aspect((dx,dy,max(dx,dy)*.45))
            ax.set_title(region+(" (도심 확대)" if region=="춘천시" else "")+" · "+NAMES[age],color="white",pad=15)
            global_depth=max(float(np.nanmax(values["total"][a]/fields["total"]["scale"])) for a in AGES)
            ax.set_zlim(-global_depth*1.03,.03)
            ax.tricontour(xy[:,0],xy[:,1],z,triangles=tri,levels=np.linspace(-1.4,-.1,8),colors="#e1f7ff",linewidths=.25,alpha=.65)
            ax.set_xlabel("UTM-K X (km)",color="white");ax.set_ylabel("UTM-K Y (km)",color="white")
            ax.set_zlabel("뒤집은 중력 (무차원)",color="white");ax.tick_params(colors="#bed0e4",labelsize=7)
            ax.view_init(elev=30,azim=-60)
        fig.suptitle(NAMES[age]+" | 실제 행정동 경계 위 공통 5종 총중력",color="white",fontsize=16)
        fig.text(.5,.02,"아래로 깊을수록 중력 큼 · 모든 연령 공통 표시 기준 · 빈 공간은 관측 없음",ha="center",color="#bed0e4")
        fig.savefig(out/("gravity_3d_preview_"+age+".png"),dpi=140,facecolor=fig.get_facecolor())
        plt.close(fig)
