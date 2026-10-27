const {core}=require('./core.cjs');
const {facts}=require('./facts.cjs');
console.log(JSON.stringify([...core(),...facts()]));
