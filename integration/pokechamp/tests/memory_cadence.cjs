'use strict';
const {Battle}=require('../../../pokemon-showdown/dist/sim');
const {Format}=require('../../../pokemon-showdown/dist/sim/dex-formats');
const {extractChannelMessages}=require('../../../pokemon-showdown/dist/sim/battle');
const b=new Battle({format:new Format({name:'Memory cadence fixture',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
const set={species:'Mew',ability:'Synchronize',nature:'Hardy',moves:['Splash']};
b.setPlayer('p1',{name:'memory-one',team:[set]});b.setPlayer('p2',{name:'memory-two',team:[set]});
let last=0;const rows=[];
for(let i=1;i<=31;i++) {
 let protocol=b.log.slice(last).join('\n');
 if(process.argv.includes('--actor-only')) protocol=extractChannelMessages(protocol,[1])[1].join('\n');
 rows.push({request:{...JSON.parse(JSON.stringify(b.p1.activeRequest)),rqid:i},protocol});
 last=b.log.length;b.makeChoices('move 1','move 1');
}
process.stdout.write(JSON.stringify(rows));b.destroy();
