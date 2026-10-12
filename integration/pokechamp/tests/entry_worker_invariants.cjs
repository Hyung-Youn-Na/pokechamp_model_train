'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {createRequire}=require('node:module');
const file=require('node:path').resolve(__dirname,'../improved_io/calculator/worker.cjs');
const localRequire=createRequire(file),out={exports:{}};
vm.runInNewContext(fs.readFileSync(file,'utf8')+'\nmodule.exports={pokemon,run,gen};', {
 require:name=>name==='node:readline'?{createInterface:()=>({on:()=>{}})}:localRequire(name),
 process:{stdout:{write:()=>{}},exit:()=>{throw new Error('worker startup failed');}},module:out,
});
const {pokemon,run,gen}=out.exports;
const scenarios=JSON.parse(fs.readFileSync(0,'utf8'));
const snapshot=JSON.stringify(Array.from(gen.species));
for(const s of scenarios) {
 const before=JSON.stringify(s),one=JSON.stringify(run({identity:{test:true},scenarios:[s]}));
 assert.equal(JSON.stringify(run({identity:{test:true},scenarios:[s,s]}).entries[0]),JSON.stringify(JSON.parse(one).entries[0]));
 assert.equal(JSON.stringify(s),before);
 for(const spec of [s.attacker,s.defender]) {
  const p=pokemon(spec),initial=JSON.stringify(p.boosts);
  if(spec.options.ability==='' || spec.entry_effects_observed && /dauntless|intrepid|embody/i.test(spec.options.ability)) {
   for(let q=p,i=0;i<4;i++,q=q.clone()) {assert.ok(!q.ability);assert.ok(!q.species.abilities[0]);assert.equal(JSON.stringify(q.boosts),initial);}
  } else {assert.ok(p.ability);assert.equal(p.clone().ability,p.ability);}
 }
}
assert.equal(JSON.stringify(Array.from(gen.species)),snapshot);
process.stdout.write(JSON.stringify({passed:true,scenarios:scenarios.length,clone_depth:4,input_unchanged:true,shared_species_unchanged:true}));
