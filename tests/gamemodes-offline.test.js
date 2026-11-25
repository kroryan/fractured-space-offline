// Exercise the released game UI configuration with live, stale and absent flags.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('patch/gamemodes-config.js', 'utf8');
function picker(flag, reply) {
    const requests = [];
    const context = {
        Player: { Rank: { Rank: 68 } }, DataStore: { getSeasonEpisode: () => ({ owned: true }) },
        document: { querySelectorAll: () => [] }, setTimeout: fn => fn(),
        XMLHttpRequest: function () {
            this.open = (_, url) => { this.url = url; };
            this.send = () => requests.push(this);
        }
    };
    context.window = context;
    vm.createContext(context);
    vm.runInContext("String.prototype.format = function(values) { return this.replace(/{{Folder}}/g, values.Folder); };", context);
    vm.runInContext(source, context);
    const config = new context.GameModeConfig();
    config.buildGameObjects();
    const answer = (request, value) => { request.status = 200; request.responseText = JSON.stringify(value); request.onload(); };
    if (flag) answer(requests.shift(), flag);
    if (reply && requests.length) answer(requests.shift(), reply);
    return config;
}
const flag = { offline: true, check: 'http://127.0.0.1:12345/bootstrapper/launch-check', nonce: 'current' };
const active = picker(flag, { nonce: 'current' });
assert.equal(active.offline, true);
assert.equal(active.getConfig('stage-one').find(x => x.Name === 'Online').IsLocked, true);
assert(active.getConfig('stage-two-Training').some(x => x.Id === 'soloVsAiFrontline'));
assert.equal(active.getConfig('stage-three-legacy').length, 5);
assert(active.getConfig('stage-three-legacy').every(x => !x.IsLocked));
assert.equal(picker(flag, { nonce: 'old' }).offline, false);
assert.equal(picker(null, null).offline, false);
assert.equal(picker({ ...flag, check: 'https://example.com/' }, { nonce: 'current' }).offline, false);
console.log('Game modes: Frontline and Legacy available; online locked only for a live matching offline session.');
