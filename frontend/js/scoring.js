/* Расчёт итогового балла по правилам чек-листа Freedom CQA.
 * answer: 'yes' | 'no' | 'na' для yesno/flag; число | 'na' для scale.
 */
(function (root) {
  const maxOf = (c) => Math.max(...(c.steps || []).map((s) => +s.v), 1);

  function finalAnswer(item) {
    return item && item.decision ? item.decision.answer : item ? item.answer : undefined;
  }

  function compute(checklist, items) {
    const crits = checklist.criteria.filter((c) => c.type !== 'flag');
    const rows = crits.map((c) => {
      const a = finalAnswer(items[c.id]);
      const na = a === 'na' || a === undefined || a === null;
      let frac = 0;
      if (!na) frac = c.type === 'scale' ? Math.min(Number(a) / maxOf(c), 1) : a === 'yes' ? 1 : 0;
      return { id: c.id, section: c.section || '', weight: +c.weight || 0, applicable: !na && (+c.weight || 0) > 0, frac, answer: a };
    });
    const sumW = rows.filter((r) => r.applicable).reduce((s, r) => s + r.weight, 0);
    rows.forEach((r) => {
      r.effWeight = r.applicable && sumW > 0 ? (r.weight / sumW) * 100 : 0; // максимум остаётся 100
      r.points = r.frac * r.effWeight;
    });
    const total = sumW > 0 ? Math.round(rows.reduce((s, r) => s + r.points, 0) * 100) / 100 : null;
    const sections = {};
    rows.forEach((r) => {
      const k = r.section || '—';
      sections[k] = sections[k] || { points: 0, max: 0 };
      sections[k].points += r.points;
      sections[k].max += r.effWeight;
    });
    Object.values(sections).forEach((s) => { s.points = Math.round(s.points * 100) / 100; s.max = Math.round(s.max * 100) / 100; });
    const flagCrit = checklist.criteria.find((c) => c.type === 'flag');
    const flag = flagCrit ? finalAnswer(items[flagCrit.id]) === 'yes' : false;
    return { total, rows, sections, flag };
  }

  const api = { compute, maxOf, finalAnswer };
  if (typeof module !== 'undefined') module.exports = api; else root.Scoring = api;
})(typeof window !== 'undefined' ? window : globalThis);
