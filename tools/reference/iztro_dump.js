const {astro} = require('iztro');
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = cases.map(c => {
  let a;
  try { a = astro.byLunar(c.lunar, c.hb, c.sex === 'male' ? '\u7537' : '\u5973', c.leap, true, 'ko-KR'); } catch (e) { return null; }
  return {
    solar: a.solarDate,
    five: a.fiveElementsClass, soul: a.soul, body: a.body,
    palaces: a.palaces.map(p => ({
      branch: p.earthlyBranch, stem: p.heavenlyStem, name: p.name,
      major: p.majorStars.map(s => [s.name, s.mutagen || '']),
      minor: p.minorStars.map(s => [s.name, s.mutagen || '']),
      adj: p.adjectiveStars.map(s => s.name),
      range: p.decadal.range, cs: p.changsheng12, bs: p.boshi12,
    })),
  };
});
process.stdout.write(JSON.stringify(out));
