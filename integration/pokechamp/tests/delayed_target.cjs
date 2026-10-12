'use strict';
const {Battle, extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
function run(move, caster) {
  const b = new Battle({format: new Format({name:'Delayed target regression', mod:'gen9', gameType:'singles', ruleset:[]}), seed:[1,2,3,4]});
  const target = caster === 'p1' ? 'p2' : 'p1';
  const teams = {
    [caster]: [{species:'Slowking', moves:[move,'Splash'], ability:'Regenerator'}],
    [target]: [{species:'Mew', moves:['Healing Wish'], ability:'Synchronize'},
      {species:'Blissey', moves:['Splash'], ability:'Natural Cure'}],
  };
  for (const side of ['p1','p2']) b.setPlayer(side,{name:side,team:teams[side]});
  const rows = [];
  function snap(phase) {
    rows.push({phase, protocol:extractChannelMessages(b.log.join('\n'),[1])[1].join('\n'),
      pending: Object.keys(b[target].slotConditions[0]), hp:b[target].active[0].hp,
      occupant:b[target].active[0].name});
  }
  b.makeChoices('move 1','move 1'); snap('fainted_target');
  const choice = {[caster]:'', [target]:'switch 2'};
  b.makeChoices(choice.p1,choice.p2); snap('replacement');
  choice[caster]='move 2'; choice[target]='move 1';
  b.makeChoices(choice.p1,choice.p2); snap('before_resolution');
  b.makeChoices(choice.p1,choice.p2); snap('resolved');
  b.destroy(); return {move,caster,target,rows};
}
process.stdout.write(JSON.stringify(['Future Sight','Doom Desire'].flatMap(m => ['p1','p2'].map(s => run(m,s)))));
