(function () {
  const KEY = 'cqa-state-v1';
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const fmt = (n) => (n === null || n === undefined ? '—' : (Math.round(n * 100) / 100).toString());

  let S;
  try { S = JSON.parse(localStorage.getItem(KEY)); } catch (e) { S = null; }
  if (!S) S = { records: [], checklists: [clone(window.DEFAULT_CHECKLIST)], activeCl: 'cl-default', results: {}, appeals: [], endpoint: '', apiUrl: '', exportMeta: { teamName: 'Название команды', modelMode: 'local', modelName: 'Название модели' }, ui: { view: 'dialogs' } };
  S.exportMeta = S.exportMeta || { teamName: 'Название команды', modelMode: 'local', modelName: 'Название модели' };
  S.ui = S.ui || { view: 'dialogs' };
  let draft = null;
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} };
  const activeCl = () => S.checklists.find((c) => c.id === S.activeCl) || S.checklists[0];
  const rec = (id) => S.records.find((r) => r.conversation_id === id);
  function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 2600); }

  /* ---------- вспомогательное ---------- */
  const cls = (v) => (v === null ? '' : v >= 80 ? 'hi' : v >= 55 ? 'mid' : 'lo');
  const REL = new WeakMap(); // реплика → секунды от начала звонка (исходная метка остаётся в title)
  const mmss = (t) => String(Math.floor(t / 60)).padStart(2, '0') + ':' + String(Math.floor(t % 60)).padStart(2, '0');
  const indexRecords = () => S.records.forEach((r) => { if (r.channel === 'voice call' && r.transcript.length) { const t0 = Date.parse(r.transcript[0].timestamp); r.transcript.forEach((m) => REL.set(m, Math.max(0, (Date.parse(m.timestamp) - t0) / 1000))); } });
  const tsView = (m) => (REL.has(m) && isFinite(REL.get(m)) ? mmss(REL.get(m)) : m.timestamp);
  const SHIFT_DEFAULT = -3; // метка реплики = момент получения распознанной фразы, сама фраза звучала раньше
  const shiftOf = (id) => ((S.audioShift || {})[id] ?? SHIFT_DEFAULT);
  const offsetSec = (r, i) => (r.channel === 'voice call' ? (REL.get(r.transcript[i]) || 0) : 0);
  const ansLabel = (c, a) => {
    if (a === 'na' || a === undefined) return 'N/A';
    if (c.type === 'scale') return `${a} / ${Scoring.maxOf(c)}`;
    if (c.type === 'flag') return a === 'yes' ? 'Выявлено' : 'Не выявлено';
    return a === 'yes' ? 'Да' : 'Нет';
  };
  const ansTag = (c, a) => { const bad = c.type === 'flag' ? a === 'yes' : a === 'no' || a === 0; const good = c.type === 'flag' ? a === 'no' : a === 'yes' || (c.type === 'scale' && a === Scoring.maxOf(c)); return a === 'na' ? 'tag' : bad ? 'tag red' : good ? 'tag green' : 'tag amber'; };
  const resultOf = (id) => { const r = S.results[id]; return r ? { r, calc: Scoring.compute(r.checklist, r.items) } : null; };
  const openAppeals = () => S.appeals.filter((a) => a.status === 'open');

  /* ---------- шапка ---------- */
  function renderNav() {
    const tabs = [['dialogs', 'Диалоги'], ['card', 'Карточка'], ['appeals', 'Апелляции'], ['checklist', 'Чек-лист']];
    $('#nav').innerHTML = tabs.map(([k, l]) => `<button data-act="nav" data-v="${k}" class="${S.ui.view === k ? 'on' : ''}">${l}${k === 'appeals' && openAppeals().length ? `<span class="cnt">${openAppeals().length}</span>` : ''}</button>`).join('');
    const c = activeCl(); $('#cl-pill').textContent = `${c.name} · v${c.version}`;
  }

  /* ---------- Диалоги ---------- */
  function viewDialogs() {
    const rows = S.records.map((r) => {
      const x = resultOf(r.conversation_id), ap = S.appeals.filter((a) => a.convId === r.conversation_id);
      return `<tr class="click" data-act="open" data-id="${esc(r.conversation_id)}"><td><b>${esc(r.conversation_id)}</b></td>
      <td><span class="tag ${r.channel === 'voice call' ? 'blue' : ''}">${r.channel === 'voice call' ? '☎ звонок' : '✉ чат'}</span></td><td>${esc(r.language)}</td><td>${r.transcript.length}</td>
      <td>${x ? `<span class="score ${cls(x.calc.total)}">${fmt(x.calc.total)}</span>` : '<span class="small">не оценён</span>'}</td>
      <td>${x && x.calc.flag ? '<span class="tag red">грубая ошибка</span>' : ''}</td>
      <td>${ap.length ? `<span class="tag gold">${ap.length}</span>` : ''}</td>
      <td><button class="btn sm" data-act="evalone" data-id="${esc(r.conversation_id)}">Оценить</button></td></tr>`;
    }).join('');
    return `<div class="panel"><h2>Источник данных</h2><div class="row">
      <input id="api-url" style="flex:1;min-width:260px" placeholder="URL GET (DEV или контрольный group_id)" value="${esc(S.apiUrl)}">
      <button class="btn primary" data-act="loadurl">Загрузить по URL</button>
      <label class="btn" style="margin:0;text-transform:none;letter-spacing:0;color:inherit">Файл JSON<input type="file" id="file-in" accept=".json" hidden></label>
      <button class="btn" data-act="demo">Демо-данные</button></div>
      <p class="small" style="margin:8px 0 0">Если браузер блокирует запрос (CORS), загрузите ответ API файлом или проксируйте через бэкенд.</p></div>
    <div class="panel" style="margin-top:18px"><div class="row"><h2 style="margin:0">Диалоги · ${S.records.length}</h2><div class="spacer"></div>
      <span class="small">Чек-лист:</span><select id="cl-select" style="width:auto">${S.checklists.map((c) => `<option value="${c.id}" ${c.id === S.activeCl ? 'selected' : ''}>${esc(c.name)} v${c.version}</option>`).join('')}</select>
      <button class="btn primary" data-act="evalall" ${S.records.length ? '' : 'disabled'}>Оценить все</button>
      <button class="btn" data-act="export-results" ${Object.keys(S.results).length ? '' : 'disabled'}>Скачать оценки JSON</button></div>
      <div class="row" style="margin-top:10px"><label class="small">Команда <input id="export-team" value="${esc(S.exportMeta.teamName)}"></label><label class="small">Режим модели <select id="export-mode"><option value="local" ${S.exportMeta.modelMode === 'local' ? 'selected' : ''}>local</option><option value="remote" ${S.exportMeta.modelMode === 'remote' ? 'selected' : ''}>remote</option></select></label><label class="small">Модель <input id="export-model" value="${esc(S.exportMeta.modelName)}"></label></div>
      ${S.records.length ? `<table style="margin-top:12px"><thead><tr><th>ID</th><th>Канал</th><th>Язык</th><th>Реплик</th><th>Итог</th><th>Флаг</th><th>Апеляций</th><th></th></tr></thead><tbody>${rows}</tbody></table>` : '<div class="empty">Загрузите диалоги: по URL, файлом или демо-набором.</div>'}</div>`;
  }

  async function evaluate(id) {
    const r = rec(id), cl = clone(activeCl()), old = S.results[id];
    const items = await Evaluator.run(r, cl, S.endpoint);
    const sig = (c) => JSON.stringify([c.type, c.weight, c.rule, c.steps]);
    if (old) cl.criteria.forEach((c) => { // сохраняем решения проверяющего для неизменённых критериев
      const oc = old.checklist.criteria.find((x) => x.id === c.id), oi = old.items[c.id];
      if (oc && oi && oi.decision && sig(oc) === sig(c)) { items[c.id].decision = oi.decision; }
    });
    S.results[id] = { clId: cl.id, clVersion: cl.version, checklist: cl, items, at: new Date().toISOString() };
    save();
  }
  async function evaluateMany(ids) {
    toast('Идёт оценка…');
    try { for (const id of ids) await evaluate(id); toast(`Оценено диалогов: ${ids.length}`); } catch (e) { toast('Ошибка: ' + e.message); }
    render();
  }

  function exportResults() {
    const results = S.records.filter((r) => S.results[r.conversation_id]).map((record) => {
      const stored = S.results[record.conversation_id];
      const calc = Scoring.compute(stored.checklist, stored.items);
      const criteria = stored.checklist.criteria.map((c) => {
        const item = stored.items[c.id] || {};
        const answer = Scoring.finalAnswer(item);
        const value = answer === undefined || answer === null || answer === 'na'
          ? null : c.type === 'flag' ? answer === 'yes' : c.type === 'scale' ? Number(answer) : answer === 'yes';
        return {
          criterion_id: c.id,
          value,
          rationale: item.decision ? `${item.explanation || ''}${item.decision.reason ? ` Решение проверяющего: ${item.decision.reason}` : ''}`.trim() : (item.explanation || ''),
          evidence_turns: (item.evidence || []).filter((i) => Number.isInteger(i) && i >= 0 && i < record.transcript.length).map((i) => i + 1)
        };
      });
      return { conversation_id: record.conversation_id, status: 'ok', criteria, score: { final_score: calc.total, critical_flag: calc.flag } };
    });
    if (!results.length) return toast('Сначала оцените хотя бы один диалог');
    const payload = { schema_version: '1.0', team_name: S.exportMeta.teamName || 'Название команды', model: { mode: S.exportMeta.modelMode || 'local', name: S.exportMeta.modelName || 'Название модели' }, results };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = `cqa-results-${new Date().toISOString().slice(0, 10)}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(`Скачан JSON: ${results.length} оценок`);
  }

  /* ---------- Карточка ---------- */
  function viewCard() {
    const r = rec(S.ui.cardId);
    if (!r) return '<div class="panel empty">Выберите диалог в списке «Диалоги».</div>';
    const x = resultOf(r.conversation_id);
    const ev = new Set(); if (x) Object.values(x.r.items).forEach((i) => (i.evidence || []).forEach((e) => ev.add(e)));
    const msgs = r.transcript.map((m, i) => `<div class="msg ${m.speaker} ${ev.has(i) ? 'hl' : ''}" id="m-${i}"><span class="ts" title="${esc(m.timestamp)}">${esc(tsView(m))}</span><span class="who">${m.speaker}</span><span>${esc(m.text)}</span>${r.audio_url ? `<button class="seek" data-act="seek" data-i="${i}" title="Перейти к фрагменту записи">▶</button>` : ''}</div>`).join('');
    const audio = r.audio_url ? `<audio id="player" controls preload="metadata"></audio><div class="small" id="audio-msg" style="margin:-4px 0 6px"></div>
      <div class="row small" style="margin-bottom:10px;gap:8px">Сдвиг, с <input id="shift" type="number" step="0.5" style="width:84px;padding:4px 8px"><button class="btn sm" data-act="syncpos" title="Нажмите ▶ у реплики, найдите её место в записи и нажмите здесь">Привязать к позиции плеера</button><button class="btn sm" data-act="resetshift">Сброс</button></div>` : '';
    return `<div class="row" style="margin-bottom:14px"><button class="btn" data-act="nav" data-v="dialogs">← К списку</button><h2 style="color:var(--text)">${esc(r.conversation_id)}</h2>
      <span class="tag">${esc(r.channel)}</span><span class="tag">${esc(r.language)}</span><div class="spacer"></div>
      <button class="btn primary" data-act="evalone" data-id="${esc(r.conversation_id)}">${x ? 'Переоценить' : 'Запустить оценку'}</button></div>
    <div class="grid2"><div class="panel sticky"><h2>Транскрипт</h2>${audio}<div class="transcript">${msgs}</div></div>
    <div>${x ? resultPanel(r, x) : '<div class="panel empty">Оценка не запускалась. Нажмите «Запустить оценку».</div>'}</div></div>`;
  }

  function resultPanel(r, x) {
    const { calc } = x, cl = x.r.checklist, items = x.r.items;
    const col = calc.total === null ? '' : calc.total >= 80 ? 'var(--green)' : calc.total >= 55 ? 'var(--amber)' : 'var(--red)';
    const secs = Object.entries(calc.sections).map(([k, v]) => `<div class="sec"><span>${esc(k)}</span><span>${fmt(v.points)} / ${fmt(v.max)}</span></div><div class="bar"><i style="width:${v.max ? (v.points / v.max) * 100 : 0}%"></i></div>`).join('');
    const crits = cl.criteria.map((c) => critHtml(r, c, items[c.id], calc.rows.find((q) => q.id === c.id))).join('');
    const flagC = cl.criteria.find((c) => c.type === 'flag');
    const origTotal = Scoring.compute(cl, Object.fromEntries(Object.entries(items).map(([k, v]) => [k, { answer: v.answer }]))).total;
    return `<div class="panel"><div class="row" style="align-items:flex-start;gap:22px"><div class="ring" style="--p:${calc.total || 0};--c:${col}"><div><div><b>${fmt(calc.total)}</b><small>из 100</small></div></div></div>
      <div style="flex:1;min-width:220px"><h2>Итог</h2>${secs}<p class="small" style="margin:8px 0 0">${origTotal !== calc.total ? `Исходный итог: <b>${fmt(origTotal)}</b> → после пересмотра: <b>${fmt(calc.total)}</b>. ` : ''}Чек-лист v${x.r.clVersion}</p></div></div>
      ${flagC ? `<div class="flagbox ${calc.flag ? 'bad' : 'ok'}">${calc.flag ? '⚠ Грубая ошибка выявлена — отмечено отдельно, баллы не затрагивает' : '✓ Грубых ошибок не выявлено'}</div>` : ''}</div>
      <div class="panel" style="margin-top:18px"><h2>Критерии</h2>${crits}</div>`;
  }

  function critHtml(r, c, it, row) {
    if (!it) return '';
    const fin = Scoring.finalAnswer(it), na = fin === 'na';
    const chips = (it.evidence || []).filter((i) => r.transcript[i]).map((i) => `<span class="chip" data-act="jump" data-i="${i}">${esc(tsView(r.transcript[i]))}</span>`).join(' ');
    const quotes = (it.evidence || []).filter((i) => r.transcript[i]).slice(0, 2).map((i) => `<div class="quote">${esc(r.transcript[i].speaker)}: ${esc(r.transcript[i].text)}</div>`).join('');
    const pts = c.type === 'flag' ? '' : `<span class="small">${na ? 'вес перераспределён' : `${fmt(row.points)} из ${fmt(row.effWeight)}`} · вес ${c.weight}</span>`;
    const ap = S.appeals.filter((a) => a.convId === r.conversation_id && a.critId === c.id);
    const hist = (it.decision || ap.length) ? `<div class="hist">${ap.map((a) => `Апелляция (${a.status === 'open' ? 'на рассмотрении' : 'решена'}): «${esc(a.comment)}»<br>`).join('')}${it.decision ? `Исходная оценка: <b>${esc(ansLabel(c, it.answer))}</b> → решение: <b>${esc(ansLabel(c, it.decision.answer))}</b> — ${esc(it.decision.reason)}<br>Финальная: <b>${esc(ansLabel(c, fin))}</b>` : ''}</div>` : '';
    return `<div class="crit ${na ? 'na' : ''}"><div class="crit-h"><h3>${esc(c.title)}</h3><span class="${ansTag(c, fin)}">${esc(ansLabel(c, fin))}</span>${pts}
      <button class="btn sm" data-act="appeal" data-c="${c.id}" data-id="${esc(r.conversation_id)}">Оспорить</button></div>
      <p>${esc(it.explanation || '')}</p>${it.checked ? `<p class="small">Проверенный участок: ${esc(it.checked)}</p>` : ''}
      ${na && c.naRule ? `<p class="small">Условие N/A: ${esc(c.naRule)}</p>` : ''}${quotes}${chips ? `<div class="row" style="gap:6px">${chips}</div>` : ''}${hist}</div>`;
  }

  /* ---------- Апелляции / проверяющий ---------- */
  function viewAppeals() {
    const list = S.appeals.slice().reverse();
    const sel = S.appeals.find((a) => a.id === S.ui.appealId);
    const l = list.map((a) => { const x = S.results[a.convId], c = x && x.checklist.criteria.find((q) => q.id === a.critId);
      return `<div class="list-item ${sel && sel.id === a.id ? 'on' : ''}" data-act="pick" data-id="${a.id}"><div class="row"><b>${esc(a.convId)}</b><div class="spacer"></div><span class="tag ${a.status === 'open' ? 'amber' : 'green'}">${a.status === 'open' ? 'открыта' : 'решена'}</span></div><div class="small">${esc(c ? c.title : a.critId)}</div></div>`; }).join('');
    return `<div class="split"><div class="panel"><h2>Обращения · ${S.appeals.length}</h2>${l || '<div class="empty">Нет апелляций. Откройте карточку и нажмите «Оспорить».</div>'}</div>
      <div>${sel ? reviewPanel(sel) : '<div class="panel empty">Выберите обращение слева.</div>'}</div></div>`;
  }

  function reviewPanel(a) {
    const r = rec(a.convId), x = S.results[a.convId];
    if (!r || !x) return '<div class="panel empty">Диалог или оценка недоступны.</div>';
    const c = x.checklist.criteria.find((q) => q.id === a.critId), it = x.items[a.critId];
    const ev = (it.evidence || []).filter((i) => r.transcript[i]);
    const center = ev.length ? ev[0] : 0, from = Math.max(0, center - 2), to = Math.min(r.transcript.length - 1, center + 2);
    const frag = r.transcript.slice(from, to + 1).map((m, k) => { const i = from + k; return `<div class="msg ${m.speaker} ${ev.includes(i) ? 'hl' : ''}"><span class="ts">${esc(tsView(m))}</span><span class="who">${m.speaker}</span><span>${esc(m.text)}</span></div>`; }).join('');
    const opts = c.type === 'scale' ? c.steps.map((s) => `<option value="${s.v}">${s.v} — ${esc(s.label)}</option>`).join('') + (c.na ? '<option value="na">N/A</option>' : '')
      : c.type === 'flag' ? '<option value="yes">Выявлено</option><option value="no">Не выявлено</option>'
      : '<option value="yes">Да</option><option value="no">Нет</option>' + (c.na ? '<option value="na">N/A</option>' : '');
    const cur = Scoring.finalAnswer(it), before = resultOf(a.convId).calc.total;
    return `<div class="panel"><div class="row"><h2 style="margin:0">${esc(c.title)}</h2><div class="spacer"></div><button class="btn sm" data-act="open" data-id="${esc(a.convId)}">Открыть карточку</button></div>
      <p class="small">Диалог ${esc(a.convId)} · оценка сейчас: <b>${esc(ansLabel(c, cur))}</b> · итог ${fmt(before)}</p>
      <label>Комментарий клиента/оператора</label><div class="quote">${esc(a.comment)}</div>
      <label>Обоснование системы</label><div class="quote">${esc(it.explanation)}</div>
      <label>Фрагмент диалога</label>${frag}
      ${a.status === 'open' ? `<label>Решение</label><select id="rv-ans">${opts}</select>
        <label>Причина</label><textarea id="rv-reason" rows="3" placeholder="Почему оценка подтверждена или изменена"></textarea>
        <div class="row" style="margin-top:12px"><button class="btn" data-act="decide" data-mode="keep">Подтвердить оценку</button><button class="btn primary" data-act="decide" data-mode="change">Изменить оценку</button></div>`
      : `<div class="hist">Решение: <b>${esc(ansLabel(c, it.decision ? it.decision.answer : it.answer))}</b> — ${esc(a.resolution || '')}<br>Исходная: <b>${esc(ansLabel(c, it.answer))}</b>. Итог после решения: <b>${fmt(before)}</b></div>`}</div>`;
  }

  /* ---------- Чек-лист ---------- */
  function viewChecklist() {
    if (!draft) draft = clone(activeCl());
    const sel = S.ui.editCrit && draft.criteria.find((c) => c.id === S.ui.editCrit) || draft.criteria[0];
    const sumW = draft.criteria.filter((c) => c.type !== 'flag').reduce((s, c) => s + (+c.weight || 0), 0);
    const list = draft.criteria.map((c) => `<div class="list-item ${sel && sel.id === c.id ? 'on' : ''}" data-act="editpick" data-c="${c.id}"><div class="row"><b>${esc(c.title)}</b><div class="spacer"></div><span class="tag">${c.type === 'flag' ? 'флаг' : c.weight}</span></div><div class="small">${esc(c.section)} · ${c.type}${c.na ? ' · N/A' : ''}</div></div>`).join('');
    return `<div class="split"><div class="panel"><h2>Критерии</h2>${list}<button class="btn" data-act="addcrit" style="width:100%">+ Добавить критерий</button>
      <p class="small">Сумма весов: <b style="color:${sumW === 100 ? 'var(--green)' : 'var(--amber)'}">${sumW}</b> (итог нормируется к 100)</p></div>
      <div class="panel">${sel ? critForm(sel) : ''}<hr style="border:0;border-top:1px solid var(--line);margin:16px 0">
        <div class="row"><label style="margin:0">Название чек-листа</label><input data-cl="name" value="${esc(draft.name)}" style="flex:1"></div>
        <div class="row" style="margin-top:12px"><button class="btn primary" data-act="savecl">Сохранить конфигурацию</button><button class="btn" data-act="applycl">Применить к диалогам</button><button class="btn" data-act="resetdraft">Отменить правки</button></div>
        <label>Прокси для аудио (необязательно)</label><input id="audioproxy" placeholder="/api/audio?url={url}" value="${esc(S.audioProxy || '')}">
        <label>Сервис оценки (необязательно)</label><input id="endpoint" placeholder="https://…/api/evaluate — иначе демо-оценщик" value="${esc(S.endpoint)}">
        <p class="small">«Сохранить» создаёт новую версию. «Применить» переоценивает все диалоги по активному чек-листу (решения проверяющего у неизменённых критериев сохраняются).</p></div></div>`;
  }
  function critForm(c) {
    const steps = (c.steps || []).map((s) => `${s.v}|${s.label}`).join('\n');
    return `<h2>Редактирование критерия</h2><div data-crit="${c.id}">
      <label>Формулировка</label><input data-f="title" value="${esc(c.title)}">
      <div class="row" style="gap:12px;align-items:flex-end"><div style="flex:2"><label>Секция</label><input data-f="section" value="${esc(c.section)}"></div>
      <div style="flex:1"><label>Тип ответа</label><select data-f="type" data-re="1"><option value="yesno" ${c.type === 'yesno' ? 'selected' : ''}>Да / Нет</option><option value="scale" ${c.type === 'scale' ? 'selected' : ''}>Числовая шкала</option><option value="flag" ${c.type === 'flag' ? 'selected' : ''}>Флаг (без баллов)</option></select></div>
      <div style="flex:1"><label>Вес</label><input type="number" min="0" data-f="weight" value="${c.weight}" ${c.type === 'flag' ? 'disabled' : ''}></div></div>
      <label><input type="checkbox" data-f="na" style="width:auto" ${c.na ? 'checked' : ''} ${c.type === 'flag' ? 'disabled' : ''}> Разрешить N/A</label>
      <label>Правило оценки</label><textarea rows="2" data-f="rule">${esc(c.rule)}</textarea>
      <label>Условие N/A</label><textarea rows="2" data-f="naRule">${esc(c.naRule || '')}</textarea>
      ${c.type === 'scale' ? `<label>Шкала (по строке: значение|описание, максимум = полный вес)</label><textarea rows="5" data-f="steps">${esc(steps)}</textarea>` : ''}
      <label>Ключевые слова для демо-оценщика (через запятую)</label><input data-f="keywords" value="${esc(c.keywords || '')}">
      <div style="margin-top:12px"><button class="btn danger sm" data-act="delcrit" data-c="${c.id}">Удалить критерий</button></div></div>`;
  }

  /* ---------- Модалка апелляции ---------- */
  function appealModal(convId, critId) {
    const x = S.results[convId], c = x.checklist.criteria.find((q) => q.id === critId), it = x.items[critId];
    $('#modal-host').innerHTML = `<div class="modal-bg" data-act="closemodal"><div class="panel modal" data-stop="1"><h2>Оспорить критерий</h2>
      <p><b>${esc(c.title)}</b> — ${esc(ansLabel(c, Scoring.finalAnswer(it)))}</p><div class="quote">${esc(it.explanation)}</div>
      <label>Комментарий</label><textarea id="ap-text" rows="4" placeholder="Почему вы не согласны с оценкой?"></textarea>
      <div class="row" style="margin-top:12px"><button class="btn primary" data-act="sendappeal" data-id="${esc(convId)}" data-c="${critId}">Сохранить обращение</button><button class="btn" data-act="closemodal">Отмена</button></div></div></div>`;
  }

  /* ---------- рендер ---------- */
  function render() {
    renderNav();
    const v = S.ui.view;
    $('#view').innerHTML = v === 'dialogs' ? viewDialogs() : v === 'card' ? viewCard() : v === 'appeals' ? viewAppeals() : viewChecklist();
    if (v === 'card') setupAudio();
    save();
  }

  /* Аудио: audio_url у организаторов — это адрес Power Automate (не статичный файл), поэтому
   * 1) пробуем играть напрямую, 2) при ошибке забираем через fetch и собираем Blob
   *    (понимает JSON вида {"$content-type","$content"} с base64), 3) иначе — ссылка «Открыть запись».
   * S.audioProxy — шаблон прокси бэкенда, например /api/audio?url={url} (решает CORS). */
  function setupAudio() {
    const r = rec(S.ui.cardId), p = $('#player'), msg = $('#audio-msg');
    if (!r || !r.audio_url || !p) return;
    const src = S.audioProxy ? S.audioProxy.replace('{url}', encodeURIComponent(r.audio_url)) : r.audio_url;
    const link = `<a href="${esc(r.audio_url)}" target="_blank" rel="noopener" style="color:var(--gold)">Открыть запись в новой вкладке</a>`;
    msg.innerHTML = link;
    const sh = $('#shift'); if (sh) sh.value = shiftOf(r.conversation_id);
    let tried = false;
    const fail = (why) => { msg.innerHTML = `Встроенный плеер не смог воспроизвести запись (${esc(why)}). ${link}`; };
    const viaBlob = async () => {
      if (tried) return fail('повторная ошибка'); tried = true; msg.textContent = 'Загружаю запись…';
      try {
        const resp = await fetch(src); if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const ct = (resp.headers.get('content-type') || '').toLowerCase();
        let blob;
        if (/json|text\/|html|xml/.test(ct) || !ct) {
          const txt = await resp.text();
          let b64 = null, mime = '', url = null;
          const sniff = (u8) => { const s = String.fromCharCode(...u8.slice(0, 12)); return s.startsWith('ID3') || (u8[0] === 0xff && (u8[1] & 0xe0) === 0xe0) ? 'audio/mpeg' : s.startsWith('RIFF') ? 'audio/wav' : s.startsWith('OggS') ? 'audio/ogg' : s.slice(4, 8) === 'ftyp' ? 'audio/mp4' : s.startsWith('fLaC') ? 'audio/flac' : ''; };
          const walk = (o) => {
            if (b64 || o === null || o === undefined) return;
            if (typeof o === 'string') {
              const s = o.trim(); let m;
              if ((m = /^data:([^;,]+)?(;base64)?,(.*)$/s.exec(s))) { mime = m[1] || mime; b64 = m[3]; return; }
              if (/^[\[{]/.test(s)) { try { walk(JSON.parse(s)); return; } catch (e) {} }
              if (s.length > 1000 && /^[A-Za-z0-9+/_\-=\s]+$/.test(s)) { b64 = s; return; }
              if (!url && /^https?:\/\//i.test(s)) url = s;
              return;
            }
            if (typeof o === 'object') { ['$content-type', 'contentType', 'content-type', 'mimeType'].forEach((k) => { if (typeof o[k] === 'string') mime = o[k]; }); Object.values(o).forEach(walk); }
          };
          let j = null; try { j = JSON.parse(txt); } catch (e) {}
          if (j !== null) walk(j);
          if (!b64 && !url) { const h = /<(?:audio|source)[^>]+src=["']([^"']+)["']/i.exec(txt) || /href=["']([^"']+\.(?:mp3|wav|ogg|m4a|aac|webm)[^"']*)["']/i.exec(txt); if (h) url = new URL(h[1], src).href; }
          if (b64) {
            const bin = atob(b64.replace(/\s/g, '').replace(/-/g, '+').replace(/_/g, '/')), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
            blob = new Blob([u8], { type: mime || sniff(u8) || 'audio/mpeg' });
          } else if (url) {
            p.addEventListener('error', () => fail('ссылка из ответа не воспроизводится'), { once: true }); p.src = url; msg.innerHTML = link; return;
          } else throw new Error(`в ответе нет аудио. Content-Type: ${ct || '—'}; начало ответа: ${txt.slice(0, 160).replace(/\s+/g, ' ')}`);
        } else blob = await resp.blob();
        p.src = URL.createObjectURL(blob); msg.innerHTML = link;
      } catch (e) { fail(/Failed to fetch/.test(e.message) ? 'CORS: нужен прокси бэкенда' : e.message); }
    };
    p.addEventListener('error', viaBlob, { once: true });
    p.src = src;
  }
  const go = (v) => { S.ui.view = v; if (v === 'checklist') draft = null; render(); window.scrollTo(0, 0); };
  function jump(i) { const el = $('#m-' + i); if (!el) return; el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); }
  function loadRecords(json) {
    const recs = Array.isArray(json) ? json : json && json.data && json.data.records;
    if (!recs || !recs.length) throw new Error('В ответе нет data.records');
    S.records = recs; S.results = {}; S.appeals = []; S.ui.cardId = null; S.audioShift = {}; indexRecords();
  }

  /* ---------- события ---------- */
  document.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-act]'); if (!t || !$('#cqa-root').contains(t)) return;
    if (t.dataset.act === 'closemodal' && e.target.closest('[data-stop]') && !e.target.closest('button')) return;
    const a = t.dataset.act, id = t.dataset.id;
    if (a === 'nav') return go(t.dataset.v);
    if (a === 'open') { S.ui.cardId = id; return go('card'); }
    if (a === 'demo') { loadRecords(window.DEMO_RECORDS); toast('Загружено демо: ' + S.records.length); return render(); }
    if (a === 'loadurl') {
      const url = $('#api-url').value.trim(); S.apiUrl = url; if (!url) return toast('Вставьте URL');
      try { const r = await fetch(url); const j = await r.json(); if (j.isSuccess === false) throw new Error(j.error || 'isSuccess=false'); loadRecords(j); toast('Загружено записей: ' + S.records.length); }
      catch (err) { toast('Не удалось загрузить (CORS?). Используйте файл JSON. ' + err.message); }
      return render();
    }
    if (a === 'evalone') { e.stopPropagation(); await evaluateMany([id]); return; }
    if (a === 'evalall') return evaluateMany(S.records.map((r) => r.conversation_id));
    if (a === 'export-results') return exportResults();
    if (a === 'jump') return jump(+t.dataset.i);
    if (a === 'seek') { const p = $('#player'), r = rec(S.ui.cardId); if (p && r) { S.ui.lastSeek = +t.dataset.i; p.currentTime = Math.max(0, offsetSec(r, +t.dataset.i) + shiftOf(r.conversation_id)); p.play().catch(() => {}); } return jump(+t.dataset.i); }
    if (a === 'syncpos') { const p = $('#player'), r = rec(S.ui.cardId), i = S.ui.lastSeek; if (!p || !r || i === undefined) return toast('Сначала нажмите ▶ у реплики'); S.audioShift = S.audioShift || {}; S.audioShift[r.conversation_id] = Math.round((p.currentTime - offsetSec(r, i)) * 10) / 10; $('#shift').value = S.audioShift[r.conversation_id]; save(); return toast('Сдвиг сохранён: ' + S.audioShift[r.conversation_id] + ' с'); }
    if (a === 'resetshift') { const r = rec(S.ui.cardId); if (S.audioShift) delete S.audioShift[r.conversation_id]; $('#shift').value = SHIFT_DEFAULT; return save(); }
    if (a === 'appeal') return appealModal(id, t.dataset.c);
    if (a === 'closemodal') { $('#modal-host').innerHTML = ''; return; }
    if (a === 'sendappeal') {
      const text = $('#ap-text').value.trim(); if (!text) return toast('Добавьте комментарий');
      const ap = { id: 'ap-' + Date.now(), convId: id, critId: t.dataset.c, comment: text, status: 'open', createdAt: new Date().toISOString() };
      S.appeals.push(ap); S.ui.appealId = ap.id; $('#modal-host').innerHTML = ''; toast('Апелляция сохранена'); return render();
    }
    if (a === 'pick') { S.ui.appealId = id; return render(); }
    if (a === 'decide') {
      const ap = S.appeals.find((q) => q.id === S.ui.appealId), reason = $('#rv-reason').value.trim(); if (!reason) return toast('Укажите причину');
      const it = S.results[ap.convId].items[ap.critId], raw = $('#rv-ans').value;
      let ans = t.dataset.mode === 'keep' ? it.answer : raw === 'yes' || raw === 'no' || raw === 'na' ? raw : Number(raw);
      it.decision = { answer: ans, reason, mode: t.dataset.mode, at: new Date().toISOString() };
      ap.status = 'resolved'; ap.resolution = (t.dataset.mode === 'keep' ? 'Оценка подтверждена. ' : 'Оценка изменена. ') + reason;
      toast('Решение сохранено, итог пересчитан'); return render();
    }
    if (a === 'editpick') { S.ui.editCrit = t.dataset.c; return render(); }
    if (a === 'addcrit') { const c = { id: 'c' + Date.now(), section: 'Новая секция', title: 'Новый критерий', type: 'yesno', weight: 10, na: false, rule: 'Да — …', naRule: '' }; draft.criteria.push(c); S.ui.editCrit = c.id; return render(); }
    if (a === 'delcrit') { draft.criteria = draft.criteria.filter((c) => c.id !== t.dataset.c); S.ui.editCrit = null; return render(); }
    if (a === 'resetdraft') { draft = null; return render(); }
    if (a === 'savecl') {
      const cl = clone(draft); cl.version = activeCl().version + 1; S.checklists = S.checklists.map((c) => (c.id === cl.id ? cl : c)); S.activeCl = cl.id; draft = null; toast('Чек-лист сохранён: v' + cl.version); return render();
    }
    if (a === 'applycl') {
      const cl = clone(draft); cl.version = activeCl().version + 1; S.checklists = S.checklists.map((c) => (c.id === cl.id ? cl : c)); draft = null;
      await evaluateMany(S.records.map((r) => r.conversation_id)); return go('dialogs');
    }
  });

  document.addEventListener('input', (e) => {
    const f = e.target.dataset;
    if (e.target.id === 'endpoint') { S.endpoint = e.target.value.trim(); return save(); }
    if (e.target.id === 'export-team') { S.exportMeta.teamName = e.target.value; return save(); }
    if (e.target.id === 'export-mode') { S.exportMeta.modelMode = e.target.value; return save(); }
    if (e.target.id === 'export-model') { S.exportMeta.modelName = e.target.value; return save(); }
    if (e.target.id === 'shift') { const r = rec(S.ui.cardId); S.audioShift = S.audioShift || {}; S.audioShift[r.conversation_id] = Number(e.target.value) || 0; return save(); }
    if (e.target.id === 'audioproxy') { S.audioProxy = e.target.value.trim(); return save(); }
    if (f.cl === 'name') { draft.name = e.target.value; return; }
    if (!f.f) return;
    const c = draft.criteria.find((q) => q.id === e.target.closest('[data-crit]').dataset.crit);
    let v = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (f.f === 'weight') v = Number(v) || 0;
    if (f.f === 'steps') { c.steps = String(v).split('\n').map((l) => l.trim()).filter(Boolean).map((l) => { const [n, ...r] = l.split('|'); return { v: Number(n), label: r.join('|').trim() }; }).filter((s) => !isNaN(s.v)); return; }
    c[f.f] = v;
    if (f.f === 'type') { if (v === 'scale' && !(c.steps || []).length) c.steps = [{ v: 10, label: 'Полностью' }, { v: 5, label: 'Частично' }, { v: 0, label: 'Нет' }]; if (v === 'flag') { c.weight = 0; c.na = false; } render(); }
  });
  document.addEventListener('change', (e) => {
    if (e.target.id === 'cl-select') { S.activeCl = e.target.value; render(); }
    if (e.target.id === 'export-mode') { S.exportMeta.modelMode = e.target.value; save(); }
    if (e.target.id === 'file-in' && e.target.files[0]) {
      const fr = new FileReader();
      fr.onload = () => { try { loadRecords(JSON.parse(fr.result)); toast('Загружено записей: ' + S.records.length); } catch (err) { toast('Ошибка файла: ' + err.message); } render(); };
      fr.readAsText(e.target.files[0]);
    }
  });

  if (!S.records.length) loadRecords(window.DEMO_RECORDS); else indexRecords();
  render();
})();
