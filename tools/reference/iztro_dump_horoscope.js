const {astro} = require('iztro');
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(c => {
  try {
    const a = astro.byLunar(c.lunar, c.hb, c.sex === 'male' ? '男' : '女', c.leap, true, 'ko-KR');
    const h = a.horoscope(c.target);
    const br = i => a.palaces[i].earthlyBranch;
    return {solar: a.solarDate,
      yearly: [br(h.yearly.index), h.yearly.heavenlyStem + h.yearly.earthlyBranch, h.yearly.mutagen],
      monthly: [br(h.monthly.index), h.monthly.heavenlyStem + h.monthly.earthlyBranch, h.monthly.mutagen],
      daily: [br(h.daily.index), h.daily.heavenlyStem + h.daily.earthlyBranch, h.daily.mutagen],
      lunarTarget: h.lunarDate};
  } catch (e) { return {err: String(e)}; }
})));
