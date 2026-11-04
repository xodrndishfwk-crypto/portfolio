/* Vue 3.5.13, local runtime. No raw model HTML is rendered. */
const { createApp, ref, computed, watch, nextTick, onMounted, onUnmounted } = Vue;
createApp({setup(){
 const periods=ref([]),king=ref(''),periodId=ref(''),question=ref(''),condition=ref(''),matches=ref([]),exploreMessage=ref('');
 const talking=ref(false); let talkTimer=null;
 const isTeaching=computed(()=>talking.value || (busy.value && /작성|정리/.test(progress.value)));
 const chats=ref({}),busy=ref(false),progress=ref(''),error=ref(''),notice=ref(''),lastQuestion=ref(''),navOpen=ref(false),bottom=ref(null);
 const drawer=ref(null),detailMessage=ref(null),sourceNumber=ref(null),detailTab=ref('인용과 원문'),dialog=ref(null),labData=ref(null),labMode=ref('similarity'),topK=ref(7),refresh=ref(false);
 const contextKey=computed(()=>periodId.value||'free_questions');
 const messages=computed(()=>chats.value[contextKey.value]||[]);
 const kings=computed(()=>[...new Set(periods.value.map(p=>p.king))]);
 const availablePeriods=computed(()=>periods.value.filter(p=>!king.value||p.king===king.value));
 const selectedPeriod=computed(()=>periods.value.find(p=>p.id===periodId.value));
 const examples=['임진왜란 때 선조는 언제 의주로 피란 갔어?','태종이 낙마한 일을 사관에게 알리지 말라고 했어?'];
 const clean=s=>(s||'').replace(/\*\*/g,'').replaceAll('정조이 다스리던 시기야.', '정조가 다스리던 시기야.');
 const safeUrl=s=>{try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}};
 const cited=field=>[...new Set((field?.evidence||[]).map(e=>e.number).filter(Number.isInteger))];
 const used=m=>[...new Set(['response','interpretation','aside','ai_translation'].flatMap(k=>cited(m.answer[k])).concat((m.answer.claims||[]).flatMap(c=>cited(c))))].filter(n=>n>=1&&n<=m.sources.length).sort((a,b)=>a-b);
 const primaryBodies=m=>(m.research?.bodies||[]).filter(d=>d.text_original||d.text_translation);
 function dayRecord(m){const a=m.answer,passages=['response','ai_translation','interpretation','aside'];const entries=passages.flatMap(k=>a[k]?.evidence||[]);const n=entries.map(e=>e.number).find(n=>n>=1&&n<=m.sources.length&&m.sources[n-1].metadata.is_primary);if(!n)return null;const source=m.sources[n-1],entry=[...(a.ai_translation?.evidence||[]),...entries].find(e=>e.number===n);return{source,quote:entry?.quote||'',translation:cited(a.ai_translation).includes(n)?a.ai_translation.text:''};}
 const translations=ref({});
 const translationKey=s=>s.metadata.article_id+'|'+s.text;
 const translationFor=s=>translations.value[translationKey(s)];
 async function translateSource(s){const k=translationKey(s);if(translations.value[k]?.loading||translations.value[k]?.translation)return;translations.value[k]={loading:true};try{translations.value[k]=await api('/api/translations',{article_id:s.metadata.article_id,text:s.text});}catch(e){translations.value[k]={error:e.message};}}
 const orderedSources=computed(()=>detailMessage.value?used(detailMessage.value).sort((a,b)=>(a===sourceNumber.value?-1:b===sourceNumber.value?1:a-b)):[]);
 async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-History-Client':'annals-local'},body:JSON.stringify(body)});let data;try{data=await r.json();}catch{throw new Error('서버 응답을 읽지 못했구나. 잠시 뒤 다시 시도해 보렴.');}if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'요청 형식을 확인해 보렴.');return data;}
 let alive=true;
 onUnmounted(()=>{alive=false;clearTimeout(talkTimer);});
 async function scrollBottom(){await nextTick();const writing=document.querySelector('.scroll-letter.ink-writing');if(writing)writing.scrollIntoView({behavior:'smooth',block:'start'});else bottom.value?.scrollIntoView({behavior:'smooth',block:'end'});}
 function persist(){try{localStorage.setItem('annals-chats-v1',JSON.stringify(chats.value));}catch{notice.value='저장 공간이 부족해 이번 대화는 새로고침 후 사라질 수 있단다.';}}
 async function poll(id){const end=Date.now()+300000;while(alive&&Date.now()<end){const j=await api('/api/jobs/'+id);progress.value=j.progress||progress.value;if(j.status==='failed')throw new Error(j.error);if(j.status==='complete')return j;await new Promise(r=>setTimeout(r,900));}throw new Error('기록을 찾는 데 시간이 걸리는구나. 잠시 뒤 다시 확인해 보렴.');}
 const freshScrolls=new Set();
 function push(key,m){freshScrolls.add(m.id);chats.value[key]=[...(chats.value[key]||[]),m].slice(-20);}
 async function send(given,retry=false){const q=(typeof given==='string'?given:question.value).trim();if(busy.value||!q)return;const key=contextKey.value;lastQuestion.value=q;error.value='';busy.value=true;progress.value='어디, 기록을 한번 펼쳐볼까…';question.value='';navOpen.value=false;
  const past=[...(chats.value[key]||[])];const history=past.map(m=>({role:m.role,content:m.content||JSON.stringify({response:m.answer?.response?.text,aside:m.answer?.aside?.text})})).slice(-12);
  if(!retry||past.at(-1)?.content!==q)push(key,{id:crypto.randomUUID(),role:'user',content:q});await scrollBottom();
  try{const start=await api('/api/questions',{question:q,period_id:periodId.value||null,history,search_mode:labMode.value,top_k:topK.value,refresh:refresh.value});const job=await poll(start.job_id);push(key,{id:crypto.randomUUID(),role:'assistant',...job.result,elapsed:job.elapsed});talking.value=true;clearTimeout(talkTimer);talkTimer=setTimeout(()=>talking.value=false,10000);persist();}
  catch(e){error.value=e.message;question.value=q;persist();}finally{busy.value=false;await scrollBottom();}}
 async function explore(){if(busy.value||!condition.value.trim())return;busy.value=true;error.value='';exploreMessage.value='조건과 맞는 기록을 살펴보는 중이란다…';matches.value=[];try{const start=await api('/api/explore',{question:condition.value});const job=await poll(start.job_id);matches.value=job.result.matches;exploreMessage.value=matches.value.length?'조건에 맞는 시기를 찾았단다.':'조건을 뒷받침할 시기는 아직 찾지 못했구나.';}catch(e){exploreMessage.value=e.message;}finally{busy.value=false;}}
 function selectPeriod(p){if(busy.value)return;king.value=p.king;periodId.value=p.id;navOpen.value=false;}
 function changeKing(){if(!availablePeriods.value.some(p=>p.id===periodId.value))periodId.value='';}
 function clearChat(){if(busy.value)return;chats.value[contextKey.value]=[];error.value='';question.value='';persist();}
 function continueRecord(m){const d=dayRecord(m);if(!d)return;send(`방금 설명한 ${d.source.metadata.date || '그날'}의 사건 이후에는 어떤 관련 기록이 이어져? 앞선 대화의 인물과 사건을 이어서 찾아보고, 후속 기록이 있으면 실제 날짜 순으로 설명해 줘. 같은 날 기록의 반복이나 무관한 사건은 제외하고, 이후 기록을 확인하지 못하면 그렇게 말해 줘.`);}
 async function showSource(m,n=null){detailMessage.value=m;sourceNumber.value=n;detailTab.value='인용과 원문';drawer.value='sources'; const ns=n?[n]:used(m);for(const i of ns){const s=m.sources[i-1];if(s?.metadata.source_kind==='한문 원문 전사본')await translateSource(s);}}
 async function openLab(){drawer.value='lab';try{labData.value=await api('/api/lab');}catch(e){notice.value=e.message;}}
 let previousFocus=null;
 watch(drawer,async value=>{if(value){previousFocus=document.activeElement;await nextTick();dialog.value?.focus();}else previousFocus?.focus();});
 function dialogKeys(e){if(!drawer.value)return;if(e.key==='Escape'){drawer.value=null;return;}if(e.key==='Tab'){const els=[...dialog.value.querySelectorAll('button,a[href],input,select,textarea,[tabindex="0"]')].filter(el=>!el.disabled&&el.getClientRects().length);const first=els[0],last=els.at(-1);if(e.shiftKey&&(document.activeElement===first||document.activeElement===dialog.value)){e.preventDefault();last?.focus();}else if(!e.shiftKey&&(document.activeElement===last||document.activeElement===dialog.value)){e.preventDefault();first?.focus();}}}
 watch(periodId,()=>{error.value='';lastQuestion.value='';try{localStorage.setItem('annals-view-v1',JSON.stringify({king:king.value,periodId:periodId.value}));}catch{}});
 onMounted(async()=>{document.addEventListener('keydown',dialogKeys);try{const saved=JSON.parse(localStorage.getItem('annals-chats-v1')||'{}');if(saved&&typeof saved==='object'&&!Array.isArray(saved))for(const [key,arr]of Object.entries(saved))if(Array.isArray(arr))chats.value[key]=arr.filter(m=>m&&typeof m==='object'&&['user','assistant'].includes(m.role)&&(m.role==='user'?typeof m.content==='string':m.answer&&Array.isArray(m.sources))).slice(-20);}catch{}try{periods.value=await api('/api/periods');try{const view=JSON.parse(localStorage.getItem('annals-view-v1')||'{}');const p=periods.value.find(p=>p.id===view.periodId);if(p){king.value=p.king;periodId.value=p.id;}else if(kings.value.includes(view.king)){king.value=view.king;}}catch{}const h=await api('/api/health');if(!h.configured)notice.value='GMS 키 설정이 필요하단다. 시기 목록은 먼저 살펴볼 수 있어.';}catch{error.value='서재에 연결하지 못했구나. 서버 실행 상태를 확인해 보렴.';}});
 onUnmounted(()=>document.removeEventListener('keydown',dialogKeys));
 return{freshScrolls,translations,translationFor,translateSource,isTeaching,periods,king,periodId,question,condition,matches,exploreMessage,messages,kings,availablePeriods,selectedPeriod,examples,busy,progress,error,notice,lastQuestion,navOpen,bottom,drawer,detailMessage,sourceNumber,detailTab,dialog,labData,labMode,topK,refresh,orderedSources,clean,safeUrl,cited,used,dayRecord,primaryBodies,send,explore,selectPeriod,changeKing,clearChat,showSource,openLab,continueRecord};
}}).directive('scroll-letter',{
 mounted(el,{value}){if(!value.animate||matchMedia('(prefers-reduced-motion: reduce)').matches)return;value.consume?.();
  const paper=el.querySelector('.scroll-paper'),brush=el.querySelector('.writing-brush');
  const targets=[...el.querySelectorAll('.answer-text,.interpretation,.story p')];
  const nodes=targets.flatMap(p=>{const w=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);const a=[];while(w.nextNode())a.push({node:w.currentNode,text:w.currentNode.textContent});return a;});
  const count=nodes.reduce((s,n)=>s+n.text.length,0);let frame=0,cancelled=false;
  el.classList.add('unrolling');
  const opening=paper.animate([{clipPath:'inset(0 49% 0 49%)',filter:'brightness(.7)'},{clipPath:'inset(0 0 0 0)',filter:'brightness(1)'}],{delay:180,fill:'backwards',duration:750,easing:'cubic-bezier(.2,.7,.2,1)'});
  if(value.role==='assistant'){targets.forEach(p=>p.style.minHeight=p.getBoundingClientRect().height+'px');el.classList.add('ink-writing');nodes.forEach(n=>{n.node.textContent='';});}
  const finish=()=>{nodes.forEach(n=>{n.node.textContent=n.text;});targets.forEach(p=>p.style.minHeight='');el.classList.remove('ink-writing','unrolling');el.classList.add('letter-finished');};
  el._stopScroll=()=>{cancelled=true;cancelAnimationFrame(frame);opening.cancel();finish();};
  opening.finished.then(()=>{if(cancelled)return;el.classList.remove('unrolling');if(value.role!=='assistant'){finish();return;}
   const start=performance.now(),duration=Math.min(16000,Math.max(1800,count*19));
   function write(now){if(cancelled)return;let remaining=Math.ceil(count*Math.min(1,(now-start)/duration)),tip=null,offset=0;
    for(const item of nodes){const n=Math.min(item.text.length,Math.max(0,remaining));item.node.textContent=item.text.slice(0,n);if(n){tip=item.node;offset=n;}remaining-=item.text.length;}
    if(tip){const range=document.createRange();range.setStart(tip,Math.max(0,offset-1));range.setEnd(tip,offset);const r=range.getBoundingClientRect(),p=el.getBoundingClientRect();brush.style.left=(r.right-p.left)+'px';brush.style.top=(r.bottom-p.top-4)+'px';}
    if(now-start<duration)frame=requestAnimationFrame(write);else finish();
   }frame=requestAnimationFrame(write);
  }).catch(()=>{});
 },beforeUnmount(el){el._stopScroll?.();}
}).mount('#app');
