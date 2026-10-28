'use strict';
// Local Showdown server for one scenario: an imported battle whose input log replays battle-gen9ou-39 up to the start
// of turn 2. A person types `/scenario` (any room); the server creates a fresh copy of that battle, seats the bot as p2
// and the person as p1, so every game starts from the same turn-2 position. One game at a time.
// Same server settings as laya_play/showdown_server.cjs: --no-security, untimed, one worker, explicit bind.
// A person who leaves the battle room for ABANDON_SECONDS loses it, like laya-play's timer rule.
// Usage: node scenario_server.cjs <showdown-root> <port> <bind> <inputlog.json> <bot name>

const path = require('node:path');
const fs = require('node:fs');

const [root, portArg, bind, logPath, botName] = process.argv.slice(2);
if (!root || !path.isAbsolute(root) || !logPath || !botName) {
	throw new Error('usage: scenario_server.cjs <showdown-root> <port> <bind> <inputlog.json> <bot name>');
}
const port = Number(portArg || 8000);
const inputLog = JSON.parse(fs.readFileSync(logPath, 'utf8')).inputlog;
const ABANDON_SECONDS = 300;
if (!process.argv.includes('--no-security')) process.argv.push('--no-security');

process.chdir(root);
const configLoader = require(path.join(root, 'dist', 'server', 'config-loader.js'));
configLoader.Config.forcetimer = false;
configLoader.Config.repl = false;
const server = require(path.join(root, 'dist', 'server', 'index.js'));
server.listen(port, bind || '127.0.0.1', 1);

const botID = ('' + botName).toLowerCase().replace(/[^a-z0-9]+/g, '');
let room = null;
let games = 0;
let awaySince = null;

function log(message) {
	process.stdout.write(`[scenario] ${message}\n`);
}

function seat(user, slot) {
	const battle = room.battle;
	battle[slot].invite = user.id;   // joinGame gives an invited user the player symbol
	user.joinRoom(room.roomid);
	if (!battle.joinGame(user, slot)) throw new Error(`could not seat ${user.name} as ${slot}`);
	log(`${user.name} seated as ${slot} in ${room.roomid}`);
}

function start(user) {
	if (user.id === botID) throw new Chat.ErrorMessage('The bot cannot start a scenario.');
	if (room && !room.battle.ended) {
		throw new Chat.ErrorMessage(`A scenario game is already running (${room.roomid}); finish or forfeit it first.`);
	}
	const bot = Users.get(botID);
	if (!bot || !bot.connected) throw new Chat.ErrorMessage(`${botName} is not online yet; try again in a moment.`);
	room = Rooms.createBattle({ format: 'gen9ou', players: [], inputLog });
	if (!room) throw new Chat.ErrorMessage('Could not create the scenario battle.');
	games += 1;
	awaySince = null;
	room.add(`|html|<div class="broadcast-blue"><strong>laya scenario</strong>: battle-gen9ou-39 from turn 2 ` +
		`(game ${games}). You are p1 (NHJ's team, reconstructed); ${botName} is p2.</div>`).update();
	// The bot first, so the person's battle opens with someone there to answer it.
	seat(bot, 'p2');
	seat(user, 'p1');
}

// Chat plugins load after this module; add the command once the built-in commands are in place.
const install = setInterval(() => {
	if (!global.Chat || !Chat.commands || !Chat.commands.help) return;
	clearInterval(install);
	Chat.loadPlugin({
		commands: {
			scenario(target, roomContext, user) {
				start(user);
			},
			scenariohelp: [`/scenario - Start the battle-gen9ou-39 turn-2 scenario against ${botName}.`],
		},
	}, 'laya-scenario');
	log(`ready: type /scenario to play against ${botName}`);
}, 200);

setInterval(() => {
	try {
		if (!room) return;
		const battle = room.battle;
		if (battle.ended) {
			log(`${room.roomid} ended`);
			room = null;
			return;
		}
		awaySince = battle.p1.active ? null : awaySince ?? Date.now();
		if (awaySince && Date.now() - awaySince > ABANDON_SECONDS * 1000) {
			log(`${battle.p1.name} left ${room.roomid} for ${ABANDON_SECONDS}s; forfeiting p1`);
			battle.forfeitPlayer(battle.p1, ' left the battle and lost.');
		}
	} catch (error) {
		log(`error: ${error && error.stack || error}`);
	}
}, 1000);
