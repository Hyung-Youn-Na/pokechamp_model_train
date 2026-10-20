'use strict';
const fs=require('node:fs');
const {TeamValidator}=require('../../../pokemon-showdown/dist/sim/team-validator');
const validator=new TeamValidator('gen9ou'),seen=new Set(),failures=[];
for(const s of JSON.parse(fs.readFileSync(0,'utf8')))for(const side of ['own','other']) {
 const key=JSON.stringify(s.scene[side]);if(seen.has(key))continue;seen.add(key);
 const errors=validator.validateTeam(JSON.parse(key));if(errors)failures.push({scenario_id:s.scenario_id,side,errors});
}
process.stdout.write(JSON.stringify({unique_teams:seen.size,failures}));
