/* Оценщик. Если задан EVAL_ENDPOINT — POST {record, checklist} → {items:{critId:{answer,explanation,evidence:[idx],checked}}}.
 * Иначе — демо-оценщик на правилах (RU/KZ/EN), чтобы фронт работал без бэкенда. Подмените на LLM-вызов на сервере. */
(function (root) {
  const R = {
    greet: /здравствуйте|добрый|привет|сәлем|сәлеметсіз|қайырлы|hello|\bhi\b|good (morning|afternoon|evening)/i,
    intro: /меня зовут|менің атым|атым|my name|this is|i am|i'm/i,
    farewell: /до свидания|всего доброго|хорошего дня|сау болыңыз|қош болыңыз|goodbye|have a (great|nice)|take care|\bbye\b/i,
    negative: /недовол|ужас|безобраз|плохо|не работает|жалоб|жаман|істемей|ашу|angry|unacceptable|complain|worst/i,
    apology: /извин|сожале|простите|кешір|өкін|sorry|apolog/i,
    polite: /пожалуйста|спасибо|рахмет|thank|please/i,
    needsId: /баланс|остаток|парол|қалдық|balance|password|заблокир|бұғат/i,
    idCheck: /иин|кодов|подтвержд|жсн|кодтық|verify|id number|security question|code word/i,
    offer: /ещё чем|что-нибудь ещё|басқа сұрақ|anything else/i,
    gross: /дурак|идиот|тупой|кретин|ақымақ|stupid|idiot|moron/i,
    bypass: /личный номер|переведите мне|частном порядке|жеке нөмір|жеке кеңес|personal number|transfer the money to me|private consultation/i
  };
  const idxs = (tr, speaker, re) => tr.map((m, i) => (m.speaker === speaker && re.test(m.text) ? i : -1)).filter((i) => i >= 0);
  const rangeNote = (tr) => `проверены реплики 0–${tr.length - 1}`;

  function demoItem(c, tr) {
    const ops = tr.map((m, i) => i).filter((i) => tr[i].speaker === 'operator');
    const cls = tr.map((m, i) => i).filter((i) => tr[i].speaker === 'client');
    const firstOp = ops[0];
    switch (c.id) {
      case 'c1': {
        if (firstOp === undefined) return { answer: 'no', explanation: 'Оператор не отвечал.', evidence: [], checked: rangeNote(tr) };
        const t = tr[firstOp].text, ok = R.greet.test(t) && R.intro.test(t);
        return { answer: ok ? 'yes' : 'no', evidence: [firstOp], explanation: ok ? 'Первый ответ содержит приветствие и представление.' : 'В первом ответе нет приветствия и/или представления.' };
      }
      case 'c2': {
        const first = cls[0] !== undefined ? tr[cls[0]].text : '';
        if (first.length >= 60) return { answer: 'na', evidence: [cls[0]], explanation: 'Первое сообщение клиента содержит достаточно деталей для ответа.' };
        const asked = ops.slice(0, 2).filter((i) => /\?/.test(tr[i].text));
        return asked.length ? { answer: 'yes', evidence: asked, explanation: 'Оператор уточнил недостающее до ответа.' }
          : { answer: 'no', evidence: ops.slice(0, 1), explanation: 'Уточняющих вопросов до ответа не было.', checked: rangeNote(tr) };
      }
      case 'c3': {
        const need = idxs(tr, 'client', R.needsId);
        if (!need.length) return { answer: 'na', evidence: [], explanation: 'Запрос не требовал идентификации (общий вопрос).', checked: rangeNote(tr) };
        const chk = idxs(tr, 'operator', R.idCheck);
        return chk.length ? { answer: 'yes', evidence: chk, explanation: 'Проверка личности подтверждена в диалоге.' }
          : { answer: 'no', evidence: need, explanation: 'Требовалась проверка личности, в чате она не подтверждена.', checked: rangeNote(tr) };
      }
      case 'c4': {
        if (!cls.length) return { answer: 'na', evidence: [], explanation: 'Клиент не сформулировал запрос.' };
        const unclear = tr.some((m) => m.speaker === 'client' && /не понял|непонятно|ничего не|still/i.test(m.text));
        const v = unclear ? 10 : ops.length >= 2 ? 20 : 15;
        return { answer: v, evidence: ops.slice(-1), explanation: unclear ? 'Клиент переспрашивает — вопрос закрыт не полностью.' : 'Запрос клиента получил ответ по существу.' };
      }
      case 'c5': {
        const neg = idxs(tr, 'client', R.negative);
        if (neg.length) { const ap = idxs(tr, 'operator', R.apology); return ap.length ? { answer: 'yes', evidence: ap, explanation: 'Клиент выразил недовольство; оператор извинился и отреагировал.' } : { answer: 'no', evidence: neg, explanation: 'Недовольство клиента осталось без реакции.' }; }
        const p = tr.map((m, i) => (m.speaker === 'operator' && (R.polite.test(m.text) || R.greet.test(m.text)) ? i : -1)).filter((i) => i >= 0);
        return p.length ? { answer: 'yes', evidence: p.slice(0, 1), explanation: 'Оператор вежлив, жалоб нет.' } : { answer: 'no', evidence: ops.slice(0, 1), explanation: 'Признаков вежливости нет.' };
      }
      case 'c6': {
        const short = ops.filter((i) => tr[i].text.trim().length < 6);
        return short.length ? { answer: 7, evidence: short, explanation: 'Есть заметный сбой в формулировках.' } : { answer: 10, evidence: ops.slice(0, 1), explanation: 'Ответы ясные и связные.' };
      }
      case 'c7': {
        const last = tr[tr.length - 1];
        if (!last || last.speaker !== 'operator') return { answer: 'na', evidence: [tr.length - 1], explanation: 'Чат оборвался до возможности завершить.' };
        return R.farewell.test(last.text) ? { answer: 'yes', evidence: [tr.length - 1], explanation: 'Оператор попрощался.' }
          : { answer: 'no', evidence: [tr.length - 1], explanation: 'Чат закрыт без прощания. Основание — последняя реплика оператора.' };
      }
      case 'c8': {
        const g = idxs(tr, 'operator', R.gross), b = idxs(tr, 'operator', R.bypass);
        if (g.length || b.length) return { answer: 'yes', evidence: [...g, ...b], explanation: b.length ? 'Предложение услуги в обход компании.' : 'Оскорбление клиента.' };
        return { answer: 'no', evidence: [], explanation: 'Ни одно из трёх нарушений не выявлено.', checked: rangeNote(tr) };
      }
      default: { // новые/изменённые критерии: ключевые слова
        const kw = (c.keywords || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
        const hit = tr.map((m, i) => (m.speaker === 'operator' && kw.some((k) => m.text.toLowerCase().includes(k)) ? i : -1)).filter((i) => i >= 0);
        const maxV = Math.max(...(c.steps || [{ v: 1 }]).map((s) => +s.v));
        const ans = c.type === 'scale' ? (hit.length ? maxV : 0) : c.type === 'flag' ? (hit.length ? 'yes' : 'no') : hit.length ? 'yes' : 'no';
        return { answer: ans, evidence: hit, explanation: hit.length ? 'Найдены реплики по ключевым словам критерия.' : 'Подтверждения не найдено.', checked: hit.length ? undefined : rangeNote(tr) };
      }
    }
  }

  async function run(record, checklist, endpoint) {
    if (endpoint) {
      const r = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ record, checklist }) });
      if (!r.ok) throw new Error('Сервис оценки: HTTP ' + r.status);
      return (await r.json()).items;
    }
    await new Promise((res) => setTimeout(res, 250));
    const items = {};
    checklist.criteria.forEach((c) => { items[c.id] = demoItem(c, record.transcript); });
    return items;
  }
  root.Evaluator = { run };
})(window);
