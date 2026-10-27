'use strict';
const rows=[];
for(let p=1;p<=5;p++)rows.push(...require(`./p${p}.cjs`).rows());
console.log(JSON.stringify(rows));
