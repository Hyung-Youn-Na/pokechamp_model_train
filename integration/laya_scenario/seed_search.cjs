'use strict';
// Find a PRNG seed whose turn 1 replays battle-gen9ou-39 exactly, then print the input log that stops at turn 2.
// Usage: node seed_search.cjs <showdown-root> <scenario.json> [max-tries]
const path = require('node:path');
const fs = require('node:fs');
const [root, specPath, triesArg] = process.argv.slice(2);
const { Battle } = require(path.join(root, 'dist', 'sim', 'battle.js'));
const { PRNG } = require(path.join(root, 'dist', 'sim', 'prng.js'));
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));

function play(seed) {
	const battle = new Battle({ formatid: spec.format, seed });
	const inputs = [`>start ${JSON.stringify({ formatid: spec.format, seed })}`];
	for (const side of ['p1', 'p2']) {
		const opts = { name: spec.players[side].name, team: spec.players[side].team };
		battle.setPlayer(side, opts);
		inputs.push(`>player ${side} ${JSON.stringify(opts)}`);
	}
	for (const [side, choice] of spec.choices) {
		if (!battle.choose(side, choice)) throw new Error(`rejected ${side} ${choice}`);
		inputs.push(`>${side} ${choice}`);
	}
	const log = battle.log.map(l => l.replace(/^\|t:\|.*$/, '')).filter(Boolean);
	return { battle, inputs, log };
}

// What one side receives: its own `|split|` blocks show the exact line, the other side's show the public line.
function view(log, side) {
	const out = [];
	for (let i = 0; i < log.length; i++) {
		if (log[i].startsWith('|split|')) {
			out.push(log[i] === `|split|${side}` ? log[i + 1] : log[i + 2]);
			i += 2;
		} else {
			out.push(log[i]);
		}
	}
	return out;
}

function turnOne(log) {
	const start = log.indexOf('|turn|1');
	const end = log.indexOf('|turn|2');
	return start < 0 || end < 0 ? null : log.slice(start, end + 1).filter(l => l !== '|');
}

const want = spec.turn1;
const tries = Number(triesArg || 20000);
const damage = new Map();
for (let i = 0; i < tries; i++) {
	const seed = PRNG.generateSeed();
	const { battle, inputs, log } = play(seed);
	const got = turnOne(view(log, spec.viewer));
	const hit = got && got.find(l => l.startsWith('|-damage|p2a'));
	if (hit) damage.set(hit, (damage.get(hit) || 0) + 1);
	if (got && got.length === want.length && got.every((l, k) => l === want[k])) {
		process.stdout.write(JSON.stringify({ seed, tries: i + 1, inputlog: inputs.join('\n') }) + '\n');
		process.exit(0);
	}
	if (i === 0) process.stderr.write(got ? got.join('\n') + '\n' : log.join('\n') + '\n');
}
process.stderr.write('no seed matched; damage seen: ' + JSON.stringify([...damage]) + '\n');
process.exit(1);
