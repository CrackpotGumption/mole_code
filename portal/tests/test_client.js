// Exercise actual browser control tracking with simulated API results.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
async function scenario(path, body, responses) {
  const elements = new Map();
  const document = {
    querySelector(s) {
      if (!elements.has(s)) elements.set(s, {value:'3000', textContent:'', className:''});
      return elements.get(s);
    },
    querySelectorAll() { return []; }
  };
  const calls = [];
  const context = vm.createContext({document, console, AbortSignal, URLSearchParams, setInterval, clearInterval,
    setTimeout, fetch: () => new Promise(() => {}),
    next: async (i, route, payload) => {
      calls.push({route, payload});
      if (!responses.length) throw Error('Unexpected request');
      const response = responses.shift();
      if (response instanceof Error) throw response;
      return response;
    }
  });
  vm.runInContext(source, context);
  vm.runInContext("selected=0; models=[{}]; cabinets=[{name:'Test'}]; confirmControl=async()=>true; pollState=async()=>{}; updateStatus=()=>{}; request=next;", context);
  await vm.runInContext(`execute(${JSON.stringify(path)},${JSON.stringify(body)},'Test control')`, context);
  return {calls, message: elements.get('#activity').textContent};
}
(async () => {
  const accepted = data => ({ok:true,status:202,data});
  const ok = data => ({ok:true,status:200,data});
  const serial = await scenario('/serial',{command:'PING'},[
    accepted({receipt:{id:42,session_id:'session-new'}}), ok({status:'SENT'}), ok({status:'OK',response:['ACK 42 OK']})
  ]);
  assert.equal(serial.calls[1].route, '/commands/42?session=session-new');
  assert.match(serial.message,/completed/);
  const host = await scenario('/host/actions',{action:'update'},[
    accepted({id:'operation'}), ok({status:'DONE',result:{id:'job'}}),
    ok([{id:'job',status:'RUNNING'}]), ok([{id:'job',status:'DONE'}])
  ]);
  assert.equal(host.calls[2].route,'/host/jobs');
  assert.equal(host.calls.length,4);
  assert.match(host.message,/completed/);
  const failure = await scenario('/host/actions',{action:'reboot'},[new Error('Connection lost')]);
  assert.equal(failure.calls.length,1);
  assert.match(failure.message,/execution is uncertain/);
  const rejection = await scenario('/game/reset',{confirm:'RESET GAME'},[
    accepted({id:'op'}),ok({status:'ERROR',error:'Not in maintenance'})
  ]);
  assert.match(rejection.message,/Not in maintenance/);
  assert.doesNotMatch(rejection.message,/completed/);
  console.log('4 client workflow tests passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
