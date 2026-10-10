'use strict';
const StrikeAnalysis=(()=>{
const names=['Martin','Daphne','Niles','Frasier','Roz'];
function parse(line){
 const named=key=>{const m=line.match(new RegExp('(?:^| )'+key+' (-?\\d+|[XYZ])(?: |$)'));return m?(/^[-\d]+$/.test(m[1])?Number(m[1]):m[1]):null;};
 const list=key=>{const m=line.match(new RegExp('(?:^| )'+key+' ((?:-?\\d+ ){4}-?\\d+)(?: |$)'));return m?m[1].split(' ').map(Number):null;};
 const common={raw:line,mole:named('MOLE'),axis:named('AXIS')};
 const scores=line.match(/^SCORES 0:(-?\d+) 1:(-?\d+) 2:(-?\d+) 3:(-?\d+) 4:(-?\d+)$/);
 if(scores){const peaks=scores.slice(1).map(Number);return {...common,type:'sweep',mode:'v1',valid:peaks.reduce((mask,v,i)=>v>=0?mask|(1<<i):mask,0),clipped:0,winner:null,threshold:10000,peaks,samples:null};}
 if(line==='OK SENSORS ENABLED')return {...common,type:'enabled'};
 if(line==='OK SENSORS DISABLED')return {...common,type:'disabled'};
 if(line.startsWith('IMPACT_REJECTED'))return {...common,type:'rejected'};
 if(line.includes('HIT_DEBUG FIFO SWEEP '))return {...common,type:'sweep',ms:named('MS'),valid:named('VALID_MASK'),clipped:named('CLIPPED_MASK'),winner:named('WINNER'),threshold:named('THRESHOLD'),peaks:list('PEAKS'),samples:list('SAMPLES')};
 if(line.includes('HIT_DEBUG FIFO ARM '))return {...common,type:'arm',delay:named('DELAY_MS'),baselineMs:named('BASELINE_MS'),threshold:named('THRESHOLD')};
 if(line.includes('HIT_DEBUG FIFO BASE '))return {...common,type:'base',value:named('VALUE'),samples:named('SAMPLES')};
 if(line.includes('HIT_DEBUG FIFO WAIT_QUIET '))return {...common,type:'quiet'};
 if(line.includes('HIT_DEBUG FIFO SETTLING_RESTART'))return {...common,type:'settling'};
 if(/FIFO (LOST|CLEAR_FAILED)|ERROR FIFO|FIFO_CONFIG_RETRY/.test(line))return {...common,type:'error'};
 const hit=line.match(/(?:^| )HIT (\d+) (\d+) (-?\d+)(?: |$)/);if(hit)return {...common,type:'hit',mole:Number(hit[1]),mux:Number(hit[2]),strength:Number(hit[3])};
 return {...common,type:'unknown'};
}
class Recorder{
 constructor(){this.session=null;this.rows=[];this.keys=new Set();this.last=null;this.maxima=names.map(()=>null);this.maximaClipped=names.map(()=>false);this.baselines=names.map(()=>null);this.errors=names.map(()=>null);this.applied=null;this.sweep=null;this.phase='No observed ARM';this.gaps=0;this.identity={};this.desired={};}
 marker(message){this.rows.push({type:'gap',message,recorded_at:new Date().toISOString()});this.gaps++;}
 ingest(d){this.identity={application:d.application,firmware:d.firmware};const serial=d.serial;if(!serial?.session_id)return;const session=serial.session_id;
 if(this.session!==session){if(this.session!==null)this.marker('Controller session changed; continuity and running maxima reset.');this.session=session;this.keys.clear();this.last=null;this.maxima=names.map(()=>null);this.maximaClipped=names.map(()=>false);this.baselines=names.map(()=>null);this.errors=names.map(()=>null);this.applied=null;this.sweep=null;this.phase='No observed ARM in this session';}
 const lines=serial.recent_serial_lines;if(!Array.isArray(lines))return;const key=o=>JSON.stringify([session,o.timestamp,o.line]);
 if(this.last&&lines.length&&!lines.some(o=>key(o)===this.last)&&lines.some(o=>!this.keys.has(key(o))))this.marker('Possible gap: previous observation is no longer in the bounded serial ring.');
 for(const observation of lines){if(typeof observation.line!=='string')continue;const k=key(observation);if(this.keys.has(k))continue;this.keys.add(k);const event={...parse(observation.line),timestamp:observation.timestamp,session_id:session};this.rows.push(event);
 if(event.type==='arm'){this.applied=event;this.phase='Settling';this.baselines=names.map(()=>null);this.errors=names.map(()=>null);this.sweep=null;}
 if(event.type==='settling')this.phase='Settling restarted by pneumatic command';
 if(event.type==='quiet')this.phase='Waiting for quiet baseline';
 if(event.type==='base'&&Number.isInteger(event.mole)&&event.mole>=0&&event.mole<5){this.baselines[event.mole]=event.value;this.errors[event.mole]=null;this.phase=this.baselines.every(v=>v!==null)?'Baseline accepted; watching for strike':'Collecting quiet baselines';}
 if(event.type==='error'){this.phase='Incomplete data / setup error';if(Number.isInteger(event.mole)&&event.mole>=0&&event.mole<5)this.errors[event.mole]=event.raw;}
 if(event.type==='sweep'){this.sweep=event;if(event.peaks)event.peaks.forEach((v,i)=>{if(event.valid!==null&&(event.valid&(1<<i))){if(this.maxima[i]===null||v>this.maxima[i]){this.maxima[i]=v;this.maximaClipped[i]=Boolean(event.clipped&(1<<i));}else if(v===this.maxima[i])this.maximaClipped[i] ||= Boolean(event.clipped&(1<<i));}});this.phase=event.valid===31?(Number.isInteger(event.winner)&&event.winner>=0?'Strike accepted; awaiting rearm':'Watching for strike'):'Incomplete comparison; not a valid hit';}
 if(event.type==='enabled')this.phase='V1 detection enabled';
 if(event.type==='disabled')this.phase='Detection disabled';
 if(event.type==='rejected')this.phase='Impact rejected; detection continues';
 if(event.type==='hit')this.phase=`Accepted HIT ${names[event.mole]??event.mole}; V3 resumes after cooldown`;
 }
 if(lines.length)this.last=key(lines[lines.length-1]);
 if(this.rows.length>5000){this.rows=this.rows.slice(-4999);this.marker('Recorder capacity reached; oldest dashboard observations discarded.');}
 // Keys cover the current ring, keeping memory bounded while deduplicating repeated polls.
 this.keys=new Set(lines.map(key));
 }
 export(){return {exported_at:new Date().toISOString(),session_id:this.session,desired_settings:this.desired,last_applied_arm:this.applied,identities:this.identity,gaps:this.gaps,observations:this.rows};}
}
return {parse,Recorder,names};
})();
if(typeof module!=='undefined')module.exports=StrikeAnalysis;

const SensorDashboard=(()=>{
 let timer=null,token=0;
 function stop(){token++;clearTimeout(timer);timer=null;}
 function mount({root,index,request,execute,escape}){
 stop();const run=token,recorder=new StrikeAnalysis.Recorder();let paused=false,inFlight=false,failures=0;
 const e=escape,show=v=>v===null||v===undefined?'—':e(v);
 root.innerHTML=`<div class="notice">Cached diagnostic observations only: recording sends no serial commands. V3 reports V1 capture scores and classified hits. Observations are bounded and may have gaps; verify reported identities.</div><div class="grid"><section class="panel full"><h3>Strike recorder</h3><div class="actions"><button id="sensorPause">Pause recording</button><button id="sensorExport">Export recording JSON</button></div><p id="sensorStatus">Connecting…</p><p id="sensorIdentity" class="muted"></p><div id="sensorTable"></div><div id="sensorPlot"></div><p class="muted">V3 scores are the largest max-minus-min XYZ range in a shared 75 ms capture, not force or piston speed. 2048 counts ≈ 1g at ±16g. A clipped value is a measurement limit. Receipt timestamps and Arduino batch uptime are not exact strike times.</p></section><section class="panel"><h3>V3 detection</h3><p>FIFO and live FIFO tuning are disabled. Firmware uses 10 ms trigger scans, a shared 75 ms capture, a 10,000-count minimum score and 15% winning margin, with a 500 ms cooldown and 750 ms global settling after movement.</p><pre id="hitApplied">V1 settings are fixed in firmware.</pre><h3>Bench test without scoring</h3><ol><li>Enter maintenance and wait for DONE.</li><li>Raise moles and enable sensors; wait for each receipt.</li><li>Strike and inspect SCORES, HIT or IMPACT_REJECTED. Detection resumes after cooldown.</li><li>Disable sensors, lower moles, then Resume for a fresh game.</li></ol><div class="actions"><button data-sensor-action="maintenance">Enter maintenance</button><button data-sensor-action="MOLES ALL UP" data-maintenance>Raise all moles</button><button data-sensor-action="SENSORS ENABLE" data-maintenance>Enable sensors</button><button data-sensor-action="SENSORS DISABLE" data-maintenance>Disable sensors</button><button data-sensor-action="MOLES ALL DOWN" data-maintenance>Lower all moles</button><button data-sensor-action="resume">Resume / fresh game</button></div></section><section class="panel full"><h3>Communication and sensor observations</h3><pre id="sensorComms"></pre><details><summary>Recent recorder lines, including unknown formats</summary><pre id="sensorRaw"></pre></details><p class="muted">Raw sensors.last_values are separate health observations; they are not capture scores. For longer captures use Logs with a UTC since filter and up to 2000 lines per source; inspect errors and truncation flags. Dashboard export retains up to 5000 observations.</p></section></div>`;
 const q=id=>root.querySelector('#'+id);
 root.querySelectorAll('[data-sensor-action]').forEach(b=>b.onclick=()=>{const action=b.dataset.sensorAction;execute(action==='maintenance'?'/maintenance':action==='resume'?'/resume':'/serial',action==='maintenance'||action==='resume'?{}:{command:action},b.textContent)});
 q('sensorPause').onclick=()=>{paused=!paused;q('sensorPause').textContent=paused?'Resume recording':'Pause recording';if(paused){recorder.marker('Recording paused by administrator; observations may be missed.');q('sensorStatus').textContent='Recording paused';}};
 q('sensorExport').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...recorder.export(),cabinet_index:index},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`cabinet-${index+1}-strikes.json`;a.click();URL.revokeObjectURL(url)};
 function render(d){const sweep=recorder.sweep;q('sensorStatus').textContent=`${recorder.phase} · ${recorder.rows.length} observations · ${recorder.gaps} gap markers · sampled ${new Date().toLocaleTimeString()}`;q('sensorIdentity').textContent=`Application ${d.application?.version??'unknown'} · running firmware ${JSON.stringify(d.firmware?.running_identity??'unknown')} · session ${recorder.session??'unknown'}`;q('hitApplied').textContent=recorder.applied?JSON.stringify(recorder.applied,null,2):'V3: shared 75 ms capture; minimum 10000; winner margin 15%; cooldown 500 ms.';
 q('sensorTable').innerHTML=`<table style="width:100%;text-align:left"><thead><tr><th>Mole</th><th>Baseline (legacy)</th><th>Capture score</th><th>Test max</th><th>Samples (legacy)</th><th>Observation</th></tr></thead><tbody>${StrikeAnalysis.names.map((name,i)=>{const valid=sweep?.valid!=null&&Boolean(sweep.valid&(1<<i)),clipped=sweep?.clipped!=null&&Boolean(sweep.clipped&(1<<i));return `<tr><td>${i} ${name}</td><td>${show(recorder.baselines[i])}</td><td>${show(sweep?.peaks?.[i])}${clipped?' (limit)':''}</td><td>${show(recorder.maxima[i])}${recorder.maximaClipped[i]?' (limit)':''}</td><td>${show(sweep?.samples?.[i])}</td><td>${e(recorder.errors[i]||(sweep?`${valid?'valid':'incomplete'}${clipped?' / clipped':''}${sweep.winner===i?' / winner':''}`:'no sweep'))}</td></tr>`}).join('')}</tbody></table>`;
 const history=recorder.rows.filter(r=>r.type==='sweep'&&r.peaks&&r.session_id===recorder.session).slice(-60),threshold=recorder.applied?.threshold??sweep?.threshold;const max=Math.max(1,threshold??0,...history.flatMap(r=>r.peaks));const colors=['#57d4b1','#ffba75','#87aaff','#de91e8','#ff887d'];let chart=`<svg role="img" aria-label="Recent five-mole peaks and applied threshold" viewBox="0 0 800 230" style="width:100%;max-height:260px"><text x="45" y="18" fill="#94a7bb" font-size="12">${max} counts · chronological batches; spacing is not elapsed time</text>`;
 if(threshold!=null){const y=190-threshold/max*155;chart+=`<line x1="45" y1="${y}" x2="780" y2="${y}" stroke="#e6edf4" stroke-dasharray="5 5"/><text x="45" y="${y-4}" fill="#e6edf4" font-size="11">Current applied threshold ${threshold}</text>`;}
 colors.forEach((color,i)=>{const pts=history.map((r,n)=>[45+n/Math.max(1,history.length-1)*735,190-r.peaks[i]/max*155]);let path='',connected=false;history.forEach((r,n)=>{if(r.valid!==null&&(r.valid&(1<<i))){path+=(connected?'L':'M')+pts[n].join(',')+' ';connected=true;}else connected=false;});chart+=`<path fill="none" stroke="${color}" d="${path}"/>`;history.forEach((r,n)=>{if(r.valid===31&&r.winner===i)chart+=`<circle cx="${pts[n][0]}" cy="${pts[n][1]}" r="4" fill="${color}"/>`;if(r.clipped&(1<<i))chart+=`<text x="${pts[n][0]}" y="${pts[n][1]}" fill="${color}">×</text>`});chart+=`<text x="${45+i*145}" y="220" fill="${color}" font-size="12">${StrikeAnalysis.names[i]}</text>`});q('sensorPlot').innerHTML=chart+'</svg>'+ '<p class="muted">Dots mark accepted winners; × marks clipping. Invalid sensor data breaks its line. Recent gates / hits: '+recorder.rows.filter(r=>['enabled','disabled','rejected','arm','settling','quiet','hit','error','gap'].includes(r.type)).slice(-8).map(r=>e(r.type==='gap'?'GAP: '+r.message:r.raw)).join('<br>')+'</p>';
 q('sensorRaw').textContent=recorder.rows.slice(-100).map(r=>r.type==='gap'?`GAP ${r.message}`:`${r.timestamp} ${r.raw}`).join('\n');q('sensorComms').textContent=JSON.stringify({serial:d.serial,health_monitor:d.health_monitor,hardware_recovery:d.hardware_recovery,recent_errors:d.recent_errors},null,2);}
 async function poll(){if(run!==token)return;if(!paused&&!inFlight){inFlight=true;try{const r=await request(index,'/diagnostics');if(run!==token)return;if(!r.ok)throw Error(r.data?.error||`HTTP ${r.status}`);if(failures)recorder.marker('Diagnostics connection recovered; continuity may be incomplete.');failures=0;recorder.ingest(r.data);render(r.data);}catch(error){failures++;if(run===token)q('sensorStatus').textContent=`Recording unavailable: ${error.message}; backing off`;}finally{inFlight=false;}}if(run===token)timer=setTimeout(poll,failures?Math.min(30000,1000*2**failures):1000);}
 poll();
 }
 return {mount,stop};
})();
