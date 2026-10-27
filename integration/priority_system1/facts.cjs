/* EP196: controlled intrinsic Gen9 hooks, not legal-team battle observations.
 * Random hooks enumerate both branches; queue/terrain stubs isolate named gates.
 * Showdown MIT licensing applies to the underlying implementation. */
const assert=require('node:assert/strict');
const {Dex,Battle}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
function facts(){
 const rows=[];const noop=()=>{};
 function add(id,rule_id,state,question,options,answer,source,observed){
  assert(options.includes(answer));assert.equal(new Set(options).size,options.length);
  rows.push({id,rule_id,state:{generation:9,...state},question,options,answer,
   evidence:{source,observed,oracle:'Actual pinned hooks/methods with explicitly controlled conditions'}});
 }
 for(const kind of ['quickclaw','quickdraw'])for(const category of ['Physical','Special','Status']){
  const hook=kind==='quickclaw'?dex.items.get(kind):dex.abilities.get(kind), eligible=kind==='quickclaw'||category!=='Status';
  const probability=kind==='quickclaw'?[1,5]:[3,10];const observed=[];
  for(const branch of [false,true]){
   let rng=null;const result=hook.onFractionalPriority.call({add:noop,randomChance:(n,d)=>{rng=[n,d];return branch;}},
    0,{hasAbility:()=>false},null,{category});
   assert.deepEqual(rng,eligible?probability:null);assert.equal(result,eligible&&branch?0.1:undefined);
   observed.push({branch,rng,result:result??null});
  }
  add(`${kind}_${category}`,'first_proc_probability',{effect:hook.name,move_category:category,
   other_order_effects:'None; no Mycelium Might',phase:'Fractional-priority check'},
   'What is the probability this effect activates to move earlier within the same integer-priority bracket?',
   ['0%','20%','30%','50%'],eligible?(kind==='quickclaw'?'20%':'30%'):'0%',
   `data/${kind==='quickclaw'?'items':'abilities'}.ts:${kind}`,observed);
 }
 let rngCalled=false;const clawMight=dex.items.get('quickclaw').onFractionalPriority.call({add:noop,randomChance:()=>{rngCalled=true;return true;}},
  -0.1,{hasAbility:id=>id==='myceliummight'},null,{category:'Status'});
 assert.equal(clawMight,undefined);assert(!rngCalled);
 add('claw_might','quickclaw_mycelium',{ability:'Mycelium Might',item:'Quick Claw',move_category:'Status'},
  'Can Quick Claw activate to bypass Mycelium Might for this move?',['Yes','No'],'No','data/items.ts:quickclaw',{rngCalled});
 for(const effect of ['myceliummight','stall','laggingtail'])for(const category of ['Status','Physical']){
  const data=effect==='laggingtail'?dex.items.get(effect):dex.abilities.get(effect);
  const hook=data.onFractionalPriority;
  const result=typeof hook==='function'?hook.call({},0,{},null,{category}):hook;
  const expected=effect==='myceliummight'&&category!=='Status'?undefined:-0.1;
  assert.equal(result,expected);
  add(`${effect}_${category}`,'last_effect_scope',{effect:data.name,move_category:category,other_order_effects:'None'},
   'Does this effect make the move act later within its integer-priority bracket?', ['Yes','No'],expected===undefined?'No':'Yes',
   `data/${effect==='laggingtail'?'items':'abilities'}.ts:${effect}`,{fractional_priority:result??null});
 }
 for(const grassy of [false,true])for(const grounded of [false,true]){
  const m=dex.moves.get('grassyglide');const result=m.onModifyPriority.call({field:{isTerrain:t=>grassy&&t==='grassyterrain'}},0,{isGrounded:()=>grounded});
  const actual=result??m.priority,expected=grassy&&grounded?1:0;assert.equal(actual,expected);
  add(`glide_${grassy}_${grounded}`,'grassy_glide',{move:'Grassy Glide',terrain:grassy?'Grassy Terrain':'None',user_grounded:grounded,
   other_priority_modifiers:'None'},'What is the move priority?',['0','+1','+2'],String(actual===1?'+1':0),
   'data/moves.ts:grassyglide',{priority:actual});
 }
 for(const grounded of [false,true])for(const priority of [0,0.1,1])for(const semi of [false,true]){
  // Fractional ordering belongs to action.priority; move.priority remains integer.
  const movePriority=priority===0.1?0:priority;
  const effect={id:priority===1?'quickattack':'tackle',priority:movePriority,target:'normal'};
  const result=dex.moves.get('psychicterrain').condition.onTryHit.call({dex,add:noop,hint:noop},
   {isGrounded:()=>grounded,isSemiInvulnerable:()=>semi,isAlly:()=>false},{},effect);
  const blocked=result===null;assert.equal(blocked,grounded&&!semi&&priority>0.1);
  add(`psychic_${grounded}_${priority}_${semi}`,'psychic_terrain_gate',{terrain:'Psychic Terrain',target_grounded:grounded,
   target_semi_invulnerable:semi,attack_order:priority===0.1?'Integer priority 0, Quick Claw activated':`Integer priority ${priority}`,
   target_relation:'Opponent',assumptions:'Isolate terrain gate; do not infer that a move can hit a semi-invulnerable target'},
   'Does Psychic Terrain block this opposing targeted move?', ['Yes','No'],blocked?'Yes':'No',
   'data/moves.ts:psychicterrain.condition.onTryHit',{effect_priority:movePriority,
    action_priority:priority,within_bracket_offset:priority===0.1?0.1:0,result:result??null,blocked});
 }
 for(const selection of ['Physical','Special','Status','Already acted','Switch']){
  const action=['Physical','Special','Status'].includes(selection)?{choice:'move',move:{id:'test',category:selection}}:
   selection==='Switch'?{choice:'switch'}:null;
  const result=dex.moves.get('suckerpunch').onTry.call({queue:{willMove:()=>action}},{},{volatiles:{}});
  const expected=selection==='Physical'||selection==='Special';assert.equal(result!==false,expected);
  add(`sucker_${selection}`,'sucker_punch_success',{move:'Sucker Punch',target_action:selection,
   assumptions:'Target is not recharging; no Protect, immunity or other prevention. Test the move-specific condition only'},
   'Does Sucker Punch pass its move-specific success condition?', ['Yes','No'],expected?'Yes':'No',
   'data/moves.ts:suckerpunch.onTry',{passed:result!==false,priority:dex.moves.get('suckerpunch').priority});
 }
 for(const willAct of [false,true])for(const stallPass of [false,true]){
  const result=dex.moves.get('protect').onPrepareHit.call({queue:{willAct:()=>willAct},runEvent:()=>stallPass},{});
  assert.equal(result,willAct&&stallPass);
  add(`protect_${willAct}_${stallPass}`,'protect_success_gate',{move:'Protect',another_action_remains:willAct,
   consecutive_protection_check_succeeds:stallPass,assumptions:'Priority is unchanged; isolate its preparation condition'},
   'Does Protect pass its preparation condition?', ['Yes','No'],result?'Yes':'No','data/moves.ts:protect.onPrepareHit',{passed:result,priority:4});
 }
 const tr=dex.moves.get('trickroom');assert.equal(tr.priority,-7);
 const duration=tr.condition.durationCallback.call({add:noop},{hasAbility:()=>false});assert.equal(duration,5);
 add('tr_duration','trick_room_duration',{move:'Trick Room',ability:'No duration-altering ability'},
  'What is the total duration, counting the turn it is established?',['3 turns','4 turns','5 turns','7 turns'],'5 turns',
  'data/moves.ts:trickroom.condition',{duration});
 let removed;tr.condition.onFieldRestart.call({field:{removePseudoWeather:id=>{removed=id;}}},{},{hasAbility:()=>false});assert.equal(removed,'trickroom');
 add('tr_restart','trick_room_restart',{move:'Trick Room',field:'Trick Room already active',assumptions:'Move successfully executes'},
  'What happens to the existing Trick Room?',['Ends','Duration refreshes','Stacks'],'Ends','data/moves.ts:trickroom.condition.onFieldRestart',{removed});
 const battle=new Battle({formatid:'gen9customgame',seed:[2026,10,21,196]});
 try{
  for(const side of ['p1','p2'])battle.setPlayer(side,{name:side,team:[{species:'Mew',ability:'No Ability',moves:['thunderwave','protect','quickattack']}]});
  const p=battle.p1.active[0],target=battle.p2.active[0];
  for(const boosted of [false,true])for(const dark of [false,true]){
   p.ability=boosted?'prankster':'noability';p.moveThisTurn='';p.moveSlots[0].pp=99;target.types=[dark?'Dark':'Normal'];target.status='';target.statusState={};
   const move=dex.getActiveMove('thunderwave');move.accuracy=true;move.alwaysHit=true;
   // The move's priority hook sets pranksterBoosted, just as queue resolution does.
   if(boosted){const priority=dex.abilities.get('prankster').onModifyPriority.call({},0,p,target,move);assert.equal(priority,1);}
   battle.actions.runMove(move,p,1);
   const succeeds=target.status==='par';assert.equal(succeeds,!(boosted&&dark));
   add(`prankster_dark_${boosted}_${dark}`,'prankster_dark_gate',{move:'Thunder Wave',source_ability:boosted?'Prankster':'No Ability',
    target_type:dark?'Dark':'Normal',assumptions:'Accuracy forced successful; target initially unstatused; no other immunity, field or blocking effect'},
    'Does this move establish paralysis?', ['Yes','No'],succeeds?'Yes':'No','sim/battle-actions.ts:Prankster target immunity',{succeeds});
  }
  p.ability='noability';
  const clawAction={choice:'move',pokemon:p,move:dex.getActiveMove('tackle'),fractionalPriority:0.1};
  battle.getActionSpeed(clawAction);
  assert.equal(clawAction.priority,0.1);assert.equal(clawAction.move.priority,0);
  for(const row of rows.filter(r=>r.rule_id==='psychic_terrain_gate'&&r.evidence.observed.within_bracket_offset===0.1)){
   row.evidence.observed.action_move_priority_separation_verified=true;
  }
  const actions={};
  for(const choice of ['switch','terastallize','move']){
   const input={choice,pokemon:p};if(choice==='move'){input.moveid='protect';input.targetLoc=0;}
   actions[choice]=battle.queue.resolveAction(input,true)[0];
  }
  assert.equal(actions.switch.order,103);assert.equal(actions.terastallize.order,106);assert.equal(actions.move.order,200);
  for(const [a,b] of [['switch','move'],['terastallize','move'],['switch','terastallize']]){
   assert(battle.comparePriority(actions[a],actions[b])<0);
   add(`phase_${a}_${b}`,'action_phase',{first_action:a,second_action:b,
    assumptions:'Ordinary chosen switch, successful Tera activation, and/or Protect move as applicable; not Pursuit or forced-switch effects'},
    'Which action phase resolves earlier?',[a,b],a,'sim/battle-queue.ts:resolveAction',{orders:[actions[a].order,actions[b].order]});
  }
 }finally{battle.destroy();}
 assert.equal(new Set(rows.map(r=>r.id)).size,rows.length);return rows;
}
module.exports={facts};
if(require.main===module){const r=facts();console.log(JSON.stringify({passed:true,count:r.length,rules:[...new Set(r.map(x=>x.rule_id))]}));}
