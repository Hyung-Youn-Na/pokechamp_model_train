'use strict';
const {Battle, Teams} = require('../../../pokemon-showdown/dist/sim');
const {extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
const b=new Battle({format:new Format({name:'Public status oracle',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
const teams=[[
 {name:'Contact',species:'Jirachi',ability:'Serene Grace',moves:['Tackle','Splash']},
 {name:'Bench',species:'Blissey',ability:'Natural Cure',moves:['Splash']},
],[
 {name:'StaticHolder',species:'Zapdos',ability:'Static',teraType:'Water',moves:['Splash']},
 {name:'OtherBench',species:'Mew',ability:'Synchronize',moves:['Splash']},
]];
b.setPlayer('p1',{name:'observer1',team:teams[0]});b.setPlayer('p2',{name:'observer2',team:teams[1]});
const randomChance=b.randomChance;b.randomChance=function(n,d) {return n===3&&d===10 ? true : randomChance.call(this,n,d);};
const out=[];
function snap(phase) {
 out.push({phase,actors:b.sides.map((side,i)=>({protocol:extractChannelMessages(b.log.join('\n'),[i+1])[i+1].join('\n'),request:{...side.activeRequest,rqid:out.length+1},own_team:Teams.export(teams[i])})),
 oracle:b.sides.map(side=>side.pokemon.map(p=>({ident:side.id+': '+p.name,fainted:p.fainted,ability:p.ability,types:p.getTypes(),tera:p.terastallized||null,status:p.status})))});
}
b.makeChoices('move Tackle','move Splash');snap('static_revealed');
b.makeChoices('move Splash','move Splash terastallize');snap('terastallized');
b.p1.active[0].cureStatus();b.p2.active[0].hp=1;
b.makeChoices('move Tackle','move Splash');b.makeChoices('','switch 2');snap('fainted_and_switched');
b.destroy();process.stdout.write(JSON.stringify(out));
