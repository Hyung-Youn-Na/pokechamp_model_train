'use strict';
// Test-only memory fixtures. Never loaded by an actor or a Showdown server.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const {Battle, Dex} = require(path.join(root, 'pokemon-showdown/dist/sim'));
const {Format} = require(path.join(root, 'pokemon-showdown/dist/sim/dex-formats'));
const calcRoot = path.join(root, 'integration/pokechamp/improved_io/calculator');
const patch = require(path.join(calcRoot, 'patch.cjs')).patchCalc();
const {Pokemon, Move, Field, Generations, calculate} = require(path.join(calcRoot, 'node_modules/@smogon/calc'));
const gen = Generations.get(9), dex = Dex.mod('gen9');
const id = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
const high = ['Ruination', "Nature's Madness", 'Super Fang', 'Endeavor', 'Final Gambit',
  'Seismic Toss', 'Night Shade', 'Dragon Rage', 'Sonic Boom', 'Counter', 'Mirror Coat',
  'Metal Burst', 'Comeuppance', 'Fissure', 'Guillotine', 'Horn Drill', 'Sheer Cold', 'Pain Split'];
const history = new Set(['counter','mirrorcoat','metalburst','comeuppance']);
function catalog(prior, teams) {
  const entries = new Map();
  function add(name, origin) {
    const move = dex.moves.get(name);
    if (!move.exists && name === 'Nothing') {
      if (!entries.has('nothing')) entries.set('nothing', {id:'nothing',name,origins:[]});
      entries.get('nothing').origins.push(origin); return;
    }
    if (!move.exists) throw new Error(`unknown move ID: ${name} (${origin})`);
    if (!entries.has(move.id)) entries.set(move.id, {id:move.id, name:move.name, origins:[]});
    entries.get(move.id).origins.push(origin);
  }
  for (const name of high) add(name, 'mandatory-high-risk');
  for (const [species, data] of Object.entries(prior.data)) {
    data.moves.forEach((m, i) => {
      add(m.name, `prior-all:${species}`);
      if (i < 4) add(m.name, `prior-default-no-observed:${species}`);
    });
  }
  for (const [team, text] of Object.entries(teams)) {
    for (const line of text.split('\n')) if (line.startsWith('- ')) add(line.slice(2).trim(), `team:${team}`);
  }
  return [...entries.values()].sort((a,b) => a.id.localeCompare(b.id)).map(e => {
    const m = dex.moves.get(e.id);
    if (e.id === 'nothing') return {...e, mechanics:'invalid-placeholder',
      excluded:'원본 Ditto prior의 Nothing은 기술 ID가 아님; 조용히 누락하지 않음'};
    const excluded = m.isZ || m.isMax || m.gen > 9 ? 'Gen9 밖 또는 전용 Z/Max mechanics' :
      m.category === 'Status' && e.id !== 'painsplit' ? '일반 상태 기술: 직접 피해 진단 범위 밖' : null;
    const mechanics = history.has(e.id) ? 'history' : m.ohko ? 'ohko' : e.id === 'painsplit' ? 'hp-redistribution' :
      high.some(n => id(n) === e.id) ? 'fixed-hp' : m.multihit ? 'multihit' :
      m.basePowerCallback || m.onBasePower || m.overrideOffensiveStat || m.overrideDefensiveStat ||
      m.overrideOffensivePokemon || m.onModifyMove || m.onTry || m.onTryHit || m.onTryMove || m.onPrepareHit ||
      m.flags.charge || ['fling','gigatonhammer','temperflare','stompingtantrum'].includes(e.id) ? 'conditional' : 'ordinary';
    return {...e, mechanics, excluded, showdown_nonstandard:m.isNonstandard || null,
      basePower:m.basePower, type:m.type, category:m.category, multihit:m.multihit || null,
      callbacks:Object.keys(m).filter(k => typeof m[k] === 'function')};
  });
}
function pokemon(name='Mew', changes={}) {
  const options = {level:100, ability:'', item:'', nature:'Serious',
    ivs:{hp:31,atk:31,def:31,spa:31,spd:31,spe:31},
    evs:{hp:0,atk:0,def:0,spa:0,spd:0,spe:0}, boosts:{}, curHP:201, status:'', ...changes};
  return {name, options};
}
function fixtures(candidates) {
  const out = [];
  function add(c, label, opts={}) {
    const base = {scenario_id:`${c.id}/${label}`, move:c.name, attacker:pokemon(),
      defender:pokemon('Blissey'), field:{}, mechanics:c.mechanics, condition:label,
      random_factors:Array.from({length:16}, (_,i)=>85+i), hit_condition:'accuracy=true; critical=false except intrinsic guaranteed critical moves', ...opts};
    if (c.mechanics === 'multihit' && !opts.defender) base.defender=pokemon('Mew',{curHP:341});
    out.push(base);
  }
  for (const c of candidates) {
    if (c.excluded) continue;
    add(c, 'base');
    if (['fixed-hp','ohko','hp-redistribution'].includes(c.mechanics)) {
      for (const hp of [1,2,202]) add(c, `target-hp-${hp}`, {defender:pokemon('Blissey',{curHP:hp})});
      add(c, 'boost-tera', {attacker:pokemon('Mew',{boosts:{atk:6,spa:6}, teraType:c.type,
        evs:{hp:0,atk:252,def:0,spa:252,spd:0,spe:4}})});
      add(c, 'protect', {field:{defenderSide:{isProtected:true}}});
      add(c, 'normal-neutral', {defender:pokemon('Mew')});
      add(c, 'ghost', {defender:pokemon('Gengar')});
      add(c, 'wonder-guard', {defender:pokemon('Blissey',{ability:'Wonder Guard'})});
      add(c, 'wonder-guard-super-effective', {defender:pokemon('Shedinja',{curHP:1,ability:'Wonder Guard'})});
      add(c, 'level-50', {attacker:pokemon('Mew',{level:50,curHP:100})});
      add(c, 'mold-breaker', {attacker:pokemon('Mew',{ability:'Mold Breaker'}),
        defender:pokemon('Blissey',{ability:'Wonder Guard'})});
    }
    if (['endeavor','finalgambit','painsplit'].includes(c.id)) {
      for (const hp of [1,100,170,201,202,341]) add(c, `user-hp-${hp}`, {attacker:pokemon('Mew',{curHP:hp})});
    }
    if (c.mechanics === 'history') {
      out.at(-1).representation_gaps=['wrapper에 피격 이력이 없어 피격 없음도 구별 불가'];
      for (const historyMove of ['Tackle','Swift','Double Hit','Splash']) add(c, `received-${id(historyMove)}`,
        {historyMove, representation_gaps:['wrapper에 피격 이력·행동 순서 입력이 없음']});
      add(c, 'previous-turn-hit', {historyMove:'Tackle', staleHistory:true,
        representation_gaps:['wrapper에 직전 턴 피격 이력 입력이 없음']});
      add(c, 'acts-before-hit', {representation_gaps:['wrapper에 이후 상대 행동 입력이 없음']});
    }
    if (c.mechanics === 'ohko') {
      add(c, 'lower-level', {attacker:pokemon('Mew',{level:99})});
      add(c, 'sturdy', {defender:pokemon('Blissey',{ability:'Sturdy'})});
      add(c, 'ice', {defender:pokemon('Glaceon')});
      add(c, 'flying', {defender:pokemon('Dragonite')});
    }
    if (c.mechanics === 'multihit') {
      out.at(-1).representation_gaps=['기본 타수는 seeded Showdown 분기이며 wrapper 타수 지정 불가'];
      const counts = Array.isArray(c.multihit) ? [c.multihit[0], c.multihit[1]] : [c.multihit];
      for (const hits of counts) add(c, `hits-${hits}`, {hits,
        representation_gaps:['wrapper에 명시적 타수 입력이 없음']});
      add(c, 'early-ko', {hits:counts.at(-1), defender:pokemon('Blissey',{curHP:1}),
        representation_gaps:['wrapper는 조기 기절별 타격 경로를 반환하지 않음']});
      for (const ability of ['Skill Link','Technician']) add(c, id(ability), {attacker:pokemon('Mew',{ability}),
        representation_gaps:['타격별 조건부 난수·타수와 wrapper aggregate를 확률분포로 대조하지 않음']});
      add(c, 'loaded-dice', {attacker:pokemon('Mew',{item:'Loaded Dice'}),
        representation_gaps:['Loaded Dice의 seeded 타수 분기와 wrapper 기본 타수는 동등 입력이 아님']});
    }
    if (c.mechanics === 'conditional') {
      const validSpecies={aurawheel:'Morpeko',hyperspacefury:'Hoopa-Unbound',doubleshock:'Pawmot'}[c.id];
      if (validSpecies) add(c,'valid-species',{attacker:pokemon(validSpecies)});
      if (['eruption','waterspout','dragonenergy','reversal'].includes(c.id)) {
        for (const hp of [14,15,34,35,68,69,113,114,171,340]) add(c, `hp-boundary-${hp}`,
          {attacker:pokemon('Mew',{curHP:hp})});
      }
      if (['weatherball','solarbeam','solarblade','thunder','hurricane','blizzard'].includes(c.id)) {
        for (const weather of ['Sun','Rain','Snow']) add(c, `weather-${weather}`,{field:{weather}});
      }
      if (['expandingforce','psyblade','terablast'].includes(c.id)) {
        for (const terrain of ['Psychic','Electric']) add(c, `terrain-${terrain}`,{field:{terrain}});
        add(c,'tera-physical',{attacker:pokemon('Mew',{teraType:'Fire',boosts:{atk:2}})});
      }
      if (['facade','hex','venoshock'].includes(c.id)) {
        add(c,'status-on',{attacker:pokemon('Mew',{status:'brn'}),defender:pokemon('Blissey',{status:'psn'})});
      }
      if (['fling','knockoff','poltergeist','acrobatics'].includes(c.id)) {
        add(c,'item-on',{attacker:pokemon('Mew',{item:'Iron Ball'}),defender:pokemon('Blissey',{item:'Leftovers'})});
      }
      if (['gyroball','electroball'].includes(c.id)) {
        for (const speed of [39,40,41,79,80,81,119,120,121,159,160,161]) {
          const name=speed < 110 ? 'Shuckle' : 'Ditto';
          const base=name === 'Shuckle' ? 15 : 101;
          const iv=Math.min(31,speed-base), ev=(speed-base-iv)*4;
          const atk=pokemon(name,{curHP:100}); atk.options.ivs.spe=iv; atk.options.evs.spe=ev;
          const def=pokemon('Shuckle',{curHP:100}); def.options.ivs.spe=25;
          add(c,`speed-${speed}-vs-40`,{attacker:atk,defender:def});
        }
        for (const spe of [-6,-1,0,1,6]) add(c,`speed-rank-${spe}`,
          {attacker:pokemon('Mew',{boosts:{spe}})});
      }
      for (const hp of [1,170,341]) add(c, `attacker-hp-${hp}`, {attacker:pokemon('Mew',{curHP:hp})});
      for (const boost of [-2,2]) add(c, `rank-${boost}`, {attacker:pokemon('Mew',{boosts:{atk:boost,spa:boost,spe:boost}})});
      for (const name of ['Gastly','Cosmoem']) add(c, `weight-${id(name)}`, {defender:pokemon(name,{curHP:100})});
    }
  }
  // Stable negative and ordinary controls, with all sixteen rolls.
  const control = {id:'earthquake',name:'Earthquake',mechanics:'ordinary'};
  add(control, 'control-air-balloon', {defender:pokemon('Blissey',{item:'Air Balloon'})});
  add({id:'dracometeor',name:'Draco Meteor',mechanics:'ordinary'}, 'control-spa-minus2',
    {attacker:pokemon('Mew',{boosts:{spa:-2}})});
  add(control, 'control-low-hp', {defender:pokemon('Blissey',{curHP:1})});
  return out;
}
function setupMon(p, spec) {
  const o = spec.options;
  p.hp = o.curHP; p.boosts = {...p.boosts,...o.boosts};
  if (o.status) p.setStatus(o.status);
  assert.equal(p.status, o.status, 'status transformation');
  assert.equal(p.ability, id(o.ability || 'No Ability'), 'ability transformation');
  assert.equal(p.item, id(o.item), 'item transformation');
  for (const [stat,n] of Object.entries(o.boosts)) assert.equal(p.boosts[stat],n,'boost transformation');
  if (o.teraType) p.terastallized = o.teraType;
  assert.equal(p.terastallized || null,o.teraType || null,'tera transformation');
  const cp = new Pokemon(gen, spec.name, o);
  if (!o.ability) cp.ability = '';
  assert.equal(p.maxhp, cp.maxHP(), 'maxHP transformation');
  for (const stat of ['atk','def','spa','spd','spe']) assert.equal(p.storedStats[stat], cp.rawStats[stat], `stat transformation ${stat}`);
  assert.ok(p.hp > 0 && p.hp <= p.maxhp, 'fixture HP invalid');
}
function observe(f, factor) {
  const format = new Format({name:'Diagnostic Gen9', id:'diagnosticgen9', mod:'gen9',
    gameType:'singles', ruleset:[], debug:true});
  const battle = new Battle({format, seed:[1,2,3,4]});
  function set(spec, moves) {
    const o=spec.options;
    return {species:spec.name, name:spec.name, level:o.level, nature:o.nature, ability:o.ability || 'No Ability',
      item:o.item, ivs:o.ivs, evs:o.evs, moves};
  }
  battle.setPlayer('p1',{name:'fixture-a',team:[set(f.attacker,[f.move])]});
  battle.setPlayer('p2',{name:'fixture-d',team:[set(f.defender,[f.historyMove || 'Splash'])]});
  const a=battle.p1.active[0], d=battle.p2.active[0];
  setupMon(a,f.attacker); setupMon(d,f.defender);
  if (f.field.weather) {
    const weather={Sun:'sunnyday',Rain:'raindance',Sand:'sandstorm',Snow:'snowscape'}[f.field.weather];
    assert.ok(weather,'unknown weather mapping');
    battle.field.setWeather(weather,a);
    assert.equal(battle.field.weather,weather,'weather transformation');
  }
  if (f.field.terrain) {
    const terrain=f.field.terrain.toLowerCase()+'terrain';
    battle.field.setTerrain(terrain,a);
    assert.equal(battle.field.terrain,terrain,'terrain transformation');
  }
  battle.randomizer = damage => Math.floor(damage * factor / 100);
  // Accuracy is a declared intervention; other probability branches use the fixed seed.
  const run = (name, user, loc, hits) => {
    const m=dex.getActiveMove(name); m.accuracy=true; m.alwaysHit=true; m.willCrit=m.willCrit || false;
    if (hits) m.multihit=hits;
    battle.actions.runMove(m,user,loc);
  };
  const m=dex.moves.get(f.move);
  if (m.beforeTurnCallback) m.beforeTurnCallback.call(battle,a,d);
  const historyHits=[];
  const attackerDamage=a.damage;
  a.damage=function(n,source,effect) {
    const hp=this.hp; const actual=attackerDamage.call(this,n,source,effect);
    if (source === d && effect?.effectType === 'Move') historyHits.push({move:effect.id,before_cap:n,applied:hp-this.hp});
    return actual;
  };
  if (f.historyMove) {
    run(f.historyMove,d,1, f.historyMove === 'Double Hit' ? 2 : undefined);
    if (f.staleHistory) {
      for (const x of a.attackedBy) x.thisTurn=false;
      a.removeVolatile('counter'); a.removeVolatile('mirrorcoat');
      if (m.beforeTurnCallback) m.beforeTurnCallback.call(battle,a,d);
    }
  }
  if (f.field.defenderSide?.isProtected) {
    d.addVolatile('protect',d); assert.ok(d.volatiles.protect,'Protect transformation');
  }
  const before={attacker:a.hp,defender:d.hp};
  const state={attacker:{species:a.species.name,ability:a.ability,item:a.item,status:a.status,boosts:{...a.boosts},tera:a.terastallized,stats:{...a.storedStats}},
    defender:{species:d.species.name,ability:d.ability,item:d.item,status:d.status,boosts:{...d.boosts},tera:d.terastallized,stats:{...d.storedStats}},
    weather:battle.field.weather,terrain:battle.field.terrain,protected:!!d.volatiles.protect};
  const hits=[];
  const damage=d.damage;
  d.damage=function(n, source, effect) {
    const hp=this.hp;
    const actual=damage.call(this,n,source,effect);
    if (source === a && effect?.id === m.id) hits.push({before_cap:n,applied:hp-this.hp});
    return actual;
  };
  // Effective pre-move HP after history is also used by both calculators.
  const effective=JSON.parse(JSON.stringify(f));
  effective.attacker.options.curHP=a.hp; effective.defender.options.curHP=d.hp;
  run(f.move,a,1,f.hits);
  const result={factor,before,state,history_hits:historyHits,after:{attacker:a.hp,defender:d.hp},hits,
    direct_before_cap:hits.reduce((s,h)=>s+h.before_cap,0),
    direct_applied:hits.reduce((s,h)=>s+h.applied,0), log:battle.log.slice(), effective};
  battle.destroy();
  return result;
}
function raw(f) {
  const a=new Pokemon(gen,f.attacker.name,f.attacker.options), d=new Pokemon(gen,f.defender.name,f.defender.options);
  if (!f.attacker.options.ability) a.ability='';
  if (!f.defender.options.ability) d.ability='';
  const move=new Move(gen,f.move, f.hits ? {hits:f.hits} : {});
  const r=calculate(gen,a,d,move,new Field(f.field));
  return {damage:r.damage,range:r.range(), move:{name:r.move.name,hits:r.move.hits}, engine_patch:patch};
}
function execute(f) {
  const observations=f.random_factors.map(n=>observe(f,n));
  // Recalculate each effective pre-move state; history rolls can change the user's HP.
  return {scenario_id:f.scenario_id, observations, raw:observations.map(o=>raw(o.effective))};
}
if (require.main === module) {
  const request=JSON.parse(fs.readFileSync(0,'utf8'));
  if (request.op === 'batch') {
    for (const fixture of request.fixtures) process.stdout.write(JSON.stringify(execute(fixture))+'\n');
    process.exit(0);
  }
  const result=request.op === 'catalog' ? (()=> {const candidates=catalog(request.prior,request.teams);
    return {candidates,fixtures:fixtures(candidates), loaded_sources:Object.keys(require.cache)};})() : execute(request.fixture);
  process.stdout.write(JSON.stringify(result)+'\n');
}
module.exports={catalog,fixtures,observe,raw,execute};
