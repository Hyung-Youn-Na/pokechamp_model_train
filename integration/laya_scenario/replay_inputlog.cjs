'use strict';
// Run a scenario input log through the simulator's BattleStream (the path a Showdown room uses) and print, as JSON,
// what one side receives: its protocol lines (`|split|` resolved) and its latest request.
// Usage: node replay_inputlog.cjs <showdown-root> <inputlog.json> <p1|p2>
const path = require('node:path');
const fs = require('node:fs');
const [root, logPath, side] = process.argv.slice(2);
const { BattleStream } = require(path.join(root, 'dist', 'sim', 'battle-stream.js'));

(async () => {
	const stream = new BattleStream();
	const lines = [];
	let request = null;
	const reader = (async () => {
		for await (const chunk of stream) {
			const [type, ...rest] = chunk.split('\n');
			if (type === 'update') {
				for (let i = 0; i < rest.length; i++) {
					if (rest[i].startsWith('|split|')) {
						lines.push(rest[i] === `|split|${side}` ? rest[i + 1] : rest[i + 2]);
						i += 2;
					} else {
						lines.push(rest[i]);
					}
				}
			} else if (type === 'sideupdate' && rest[0] === side && rest[1].startsWith('|request|')) {
				request = JSON.parse(rest[1].slice(9));
			} else if (type === 'sideupdate' && rest[0] === side) {
				lines.push(...rest.slice(1));
			}
		}
	})();
	await stream.write(JSON.parse(fs.readFileSync(logPath, 'utf8')).inputlog);
	await new Promise(resolve => setTimeout(resolve, 500));
	stream.writeEnd();
	await reader;
	process.stdout.write(JSON.stringify({ lines, request }));
})();
