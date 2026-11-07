/* CQA · фронтенд. Все данные, оценки, баллы, апелляции и чек-листы живут на бэкенде (FastAPI, /api).
 * В localStorage хранятся только настройки интерфейса. */
(function () {
  const KEY = 'cqa-state-v2';
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const fmt = (n) => (n === null || n === undefined ? '—' : String(Math.round(n * 100) / 100));
  const mmss = (t) => (t === null || t === undefined ? '—' : String(Math.floor(t / 60)).padStart(2, '0') + ':' + String(Math.floor(t % 60)).padStart(2, '0'));
  const dt = (s) => (s ? new Date(s).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '');
  const cls = (v) => (v === null || v === undefined ? '' : v >= 80 ? 'hi' : v >= 55 ? 'mid' : 'lo');

  const DEFAULTS = { backendUrl: 'http://localhost:8000/api', dataset: '', importGroup: 'DEV', importUrl: '', exportMeta: { teamName: '', modelMode: '', modelName: '' }, audioShift: {}, appealFilter: 'open', ui: { view: 'dialogs' } };
  let S;
  try { S = { ...clone(DEFAULTS), ...(JSON.parse(localStorage.getItem(KEY)) || {}) }; } catch (e) { S = clone(DEFAULTS); }
  S.ui = S.ui || { view: 'dialogs' };
  try { localStorage.removeItem('cqa-state-v1'); } catch (e) {} // старое демо-состояние
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} };

  // Данные с бэкенда (не сохраняются в браузере)
  const R = { online: null, health: null, datasets: [], convs: [], versions: [], active: null, clCache: {}, conv: null, card: null, appeals: [], openAppeals: 0, analytics: null, job: null };
  let draft = null, lastDiff = null, pollTimer = null;

  const SPEAKER = { operator: 'оператор', client: 'клиент', bot: 'бот', system: 'система' };
  const GROSS = { insult: 'оскорбление клиента', bypass_offer: 'предложение услуги в обход компании', confidential_leak: 'раскрытие конфиденциальной информации' };
  const TYPE = { binary: 'Да / Нет', scale: 'шкала', flag: 'флаг' };

  function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 3200); }

  /* ---------- API ---------- */
  async function api(path, options = {}) {
    let response;
    try {
      response = await fetch(`${S.backendUrl.replace(/\/$/, '')}${path}`, { ...options, headers: { ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) } });
    } catch (e) {
      R.online = false; throw new Error('бэкенд недоступен');
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const d = body.detail;
      throw new Error(Array.isArray(d) ? d.map((x) => String(x.msg || '').replace(/^Value error, /, '')).join('; ') : d || `HTTP ${response.status}`);
    }
    return body;
  }
  const post = (path, data) => api(path, { method: 'POST', body: JSON.stringify(data ?? {}) });
  const qs = (o) => { const p = Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined); return p.length ? '?' + p.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&') : ''; };

  async function getChecklist(id) {
    if (!R.clCache[id]) R.clCache[id] = await api(`/checklists/${id}`);
    return R.clCache[id];
  }
  async function loadBase() {
    try {
      R.health = await api('/health'); R.online = true;
      [R.versions, R.active, R.datasets] = await Promise.all([api('/checklists'), api('/checklists/active').catch(() => null), api('/datasets')]);
      if (S.dataset && !R.datasets.some((d) => d.dataset === S.dataset)) S.dataset = '';
      await Promise.all([loadConvs(), loadOpenCount()]);
    } catch (e) { R.online = false; R.health = null; }
  }
  async function loadConvs() { R.convs = await api('/conversations' + qs({ dataset: S.dataset })); }
  async function loadOpenCount() { R.openAppeals = (await api('/appeals?status=open')).length; }
  async function openCard(id, evaluationId) {
    R.conv = await api(`/conversations/${encodeURIComponent(id)}`);
    const eid = evaluationId || (R.conv.evaluations[0] && R.conv.evaluations[0].id);
    R.card = eid ? await api(`/evaluations/${eid}`) : null;
    if (R.card) await getChecklist(R.card.checklist.id);
    S.ui.cardId = id;
  }
  async function refreshCard() { if (R.conv) await openCard(R.conv.id, R.card && R.card.evaluation.id); }

  /* ---------- шапка ---------- */
  function renderNav() {
    const tabs = [['dialogs', 'Диалоги'], ['card', 'Карточка'], ['appeals', 'Апелляции'], ['checklist', 'Чек-лист'], ['analytics', 'Аналитика']];
    $('#nav').innerHTML = tabs.map(([k, l]) => `<button data-act="nav" data-v="${k}" class="${S.ui.view === k ? 'on' : ''}">${l}${k === 'appeals' && R.openAppeals ? `<span class="cnt">${R.openAppeals}</span>` : ''}</button>`).join('');
    $('#cl-pill').textContent = R.active ? `${R.active.name} · v${R.active.version}` : 'Нет данных';
  }
  const offline = () => `<div class="panel empty">Бэкенд недоступен по адресу <b>${esc(S.backendUrl)}</b>.<br>Запустите сервер (<code>make run</code> в папке backend) и нажмите «Подключить» на вкладке «Диалоги».</div>`;

  /* ---------- Диалоги ---------- */
  function statusTag() {
    if (R.online === null) return '<span class="tag">подключение…</span>';
    if (!R.online) return '<span class="tag red">бэкенд недоступен</span>';
    return `<span class="tag green">● ${esc(R.health.provider)} · ${esc(R.health.model)}</span>`;
  }
  function jobBox() {
    const j = R.job; if (!j) return '';
    const pct = j.total ? Math.round((j.processed / j.total) * 100) : 100;
    const kind = j.kind === 'reapply' ? 'Применение чек-листа' : 'Оценка';
    const fails = j.failed.length ? `<details class="small" style="margin-top:6px"><summary>Ошибки (${j.failed.length})</summary>${j.failed.map((f) => `<div>${esc(f.conversation_id)}: ${esc(f.reason)}</div>`).join('')}</details>` : '';
    const skips = j.skipped.length ? `<details class="small" style="margin-top:6px"><summary>Пропущено (${j.skipped.length})</summary>${j.skipped.map((f) => `<div>${esc(f.conversation_id)}: ${esc(f.reason)}</div>`).join('')}</details>` : '';
    return `<div class="jobbox"><div class="row small"><b style="color:var(--text)">${kind}</b><span>${j.status === 'running' ? 'идёт…' : 'завершено'}</span><div class="spacer"></div>
      <span>обработано ${j.processed} из ${j.total} · готово ${j.done.length} · пропущено ${j.skipped.length} · ошибок ${j.failed.length}</span>
      ${j.status !== 'running' ? '<button class="btn sm" data-act="closejob">Скрыть</button>' : ''}</div>
      <div class="bar" style="margin-top:6px"><i style="width:${pct}%"></i></div>${fails}${skips}</div>`;
  }
  function viewDialogs() {
    const ds = R.datasets.map((d) => `<option value="${esc(d.dataset)}" ${d.dataset === S.dataset ? 'selected' : ''}>${esc(d.dataset)} · ${d.total}</option>`).join('');
    const vers = R.versions.map((c) => `<option value="${c.id}" ${R.active && c.id === R.active.id ? 'selected' : ''}>${esc(c.name)} v${c.version}${c.is_active ? ' (активна)' : ''}</option>`).join('');
    const rows = R.convs.map((r) => `<tr class="click" data-act="open" data-id="${esc(r.id)}"><td><b>${esc(r.id)}</b></td>
      <td><span class="tag ${r.channel === 'voice call' ? 'blue' : ''}">${r.channel === 'voice call' ? '☎ звонок' : '✉ чат'}</span></td><td>${esc(r.language)}</td><td>${r.messages ?? '—'}</td>
      <td>${r.total !== null && r.total !== undefined ? `<span class="score ${cls(r.total)}">${fmt(r.total)}</span>${r.preliminary ? ' <span class="tag amber" title="По части критериев нет ответа модели">предв.</span>' : ''}` : `<span class="small">${r.last_evaluation_id ? 'не рассчитывается' : 'не оценён'}</span>`}</td>
      <td>${r.gross_error ? '<span class="tag red">грубая ошибка</span>' : ''}</td>
      <td>${r.open_appeals ? `<span class="tag gold">${r.open_appeals}</span>` : ''}</td>
      <td>${r.excluded ? '<span class="tag" title="Канал исключён из отправки в модель (EXCLUDE_CHANNELS)">не в модель</span>' : `<button class="btn sm" data-act="evalone" data-id="${esc(r.id)}">${r.last_evaluation_id ? 'Переоценить' : 'Оценить'}</button>`}</td></tr>`).join('');
    const running = R.job && R.job.status === 'running';
    const m = S.exportMeta;
    const list = !R.online ? offline()
      : `<div class="panel" style="margin-top:18px"><div class="row"><h2 style="margin:0">Диалоги · ${R.convs.length}</h2><div class="spacer"></div>
        <span class="small">Набор:</span><select id="ds-select" style="width:auto"><option value="">Все наборы</option>${ds}</select>
        <span class="small">Чек-лист:</span><select id="cl-select" style="width:auto">${vers || '<option>Нет данных</option>'}</select></div>
        <div class="row" style="margin-top:10px">
          <button class="btn primary" data-act="batch" data-mode="evaluate" data-missing="1" ${R.convs.length && !running ? '' : 'disabled'}>Оценить неоценённые</button>
          <button class="btn" data-act="batch" data-mode="evaluate" ${R.convs.length && !running ? '' : 'disabled'}>Переоценить все</button>
          <button class="btn" data-act="batch" data-mode="reapply" ${R.convs.length && !running ? '' : 'disabled'} title="Перенести оценки на активный чек-лист: модель вызывается только по изменённым критериям">Применить активный чек-лист</button>
          <div class="spacer"></div><span class="small">Действия применяются к выбранному набору</span></div>
        ${jobBox()}
        <div class="row" style="margin-top:12px;align-items:flex-end">
          <div style="flex:2;min-width:180px"><label>Команда</label><input id="export-team" value="${esc(m.teamName)}" placeholder="Название команды"></div>
          <div style="flex:1;min-width:140px"><label>Режим модели</label><select id="export-mode"><option value="" ${!m.modelMode ? 'selected' : ''}>авто${R.health ? ` (${R.health.provider === 'gemini' ? 'remote' : 'local'})` : ''}</option><option value="remote" ${m.modelMode === 'remote' ? 'selected' : ''}>remote</option><option value="local" ${m.modelMode === 'local' ? 'selected' : ''}>local</option></select></div>
          <div style="flex:2;min-width:180px"><label>Модель</label><input id="export-model" value="${esc(m.modelName)}" placeholder="${esc(R.health ? R.health.model : 'Название модели')}"></div>
          <button class="btn" data-act="export">Скачать оценки JSON</button></div>
        ${R.convs.length ? `<table style="margin-top:12px"><thead><tr><th>ID</th><th>Канал</th><th>Язык</th><th>Реплик</th><th>Итог</th><th>Флаг</th><th>Апелляций</th><th></th></tr></thead><tbody>${rows}</tbody></table>`
          : '<div class="empty">Нет данных. Импортируйте набор: по group_id, по ссылке или файлом JSON.</div>'}</div>`;
    return `<div class="panel"><h2>Источник данных</h2>
      <div class="row"><input id="backend-url" style="width:260px" value="${esc(S.backendUrl)}" placeholder="http://localhost:8000/api"><button class="btn" data-act="connect">Подключить</button>${statusTag()}</div>
      <div class="row" style="margin-top:10px"><input id="import-group" style="width:200px" value="${esc(S.importGroup)}" placeholder="group_id, например DEV"><button class="btn primary" data-act="import-group" ${R.online ? '' : 'disabled'}>Импорт из API организаторов</button>
        <span class="small">Ссылка берётся из DATASET_API_URL бэкенда, group_id дописывается автоматически.</span></div>
      <div class="row" style="margin-top:10px"><input id="import-url" style="flex:1;min-width:260px" value="${esc(S.importUrl)}" placeholder="Полная ссылка на набор (если выдали другой URL)">
        <button class="btn" data-act="import-url" ${R.online ? '' : 'disabled'}>Загрузить по URL</button>
        <label class="btn" style="margin:0;text-transform:none;letter-spacing:0;color:inherit">Файл JSON<input type="file" id="file-in" accept=".json" hidden ${R.online ? '' : 'disabled'}></label></div>
      <p class="small" style="margin:8px 0 0">Ссылку скачивает бэкенд, поэтому CORS не мешает, а подпись не сохраняется в браузере.</p></div>${list}`;
  }

  /* ---------- Карточка ---------- */
  const critOf = (clId, id) => { const c = R.clCache[clId]; return c && c.data.criteria.find((q) => q.id === id); };
  const maxStep = (c) => (c && c.scale && c.scale.length ? Math.max(...c.scale.map((s) => s.value)) : null);
  function ansLabel(item, c) {
    if (!item || item.status === 'error') return 'нет ответа';
    if (item.na || item.answer === 'na') return 'N/A';
    if (item.type === 'scale') return `${item.value} / ${maxStep(c) ?? '?'}`;
    if (item.type === 'flag') return item.value === 1 ? 'Выявлено' : 'Не выявлено';
    return item.value === 1 ? 'Да' : 'Нет';
  }
  function ansTag(item, c) {
    if (!item || item.status === 'error') return 'tag amber';
    if (item.na) return 'tag';
    if (item.type === 'flag') return item.value === 1 ? 'tag red' : 'tag green';
    if (item.type === 'scale') return item.value === maxStep(c) ? 'tag green' : item.value === 0 ? 'tag red' : 'tag amber';
    return item.value === 1 ? 'tag green' : 'tag red';
  }
  function viewCard() {
    if (!R.online) return offline();
    const conv = R.conv;
    if (!conv) return '<div class="panel empty">Выберите диалог в списке «Диалоги».</div>';
    const card = R.card;
    const excluded = (R.convs.find((x) => x.id === conv.id) || {}).excluded;
    const ev = new Set(); if (card) card.final.criteria.forEach((i) => (i.evidence_ids || []).forEach((n) => ev.add(n)));
    const msgs = conv.transcript.map((m) => `<div class="msg ${esc(m.speaker)} ${ev.has(m.index) ? 'hl' : ''}" id="m-${m.index}"><span class="ts" title="${esc(m.timestamp)}">#${m.index} ${mmss(m.offset_sec)}</span><span class="who">${esc(SPEAKER[m.speaker] || m.speaker)}</span><span>${esc(m.text)}</span>${conv.audio_url ? `<button class="seek" data-act="seek" data-i="${m.index}" title="Перейти к фрагменту записи">▶</button>` : ''}</div>`).join('');
    const audio = conv.audio_url ? `<audio id="player" controls preload="metadata" src="${esc(S.backendUrl.replace(/\/$/, ''))}/audio/${encodeURIComponent(conv.id)}"></audio><div class="small" id="audio-msg" style="margin:-4px 0 6px"></div>
      <div class="row small" style="margin-bottom:10px;gap:8px">Сдвиг, с <input id="shift" type="number" step="0.5" style="width:84px;padding:4px 8px" value="${shiftOf(conv.id)}"><button class="btn sm" data-act="syncpos" title="Нажмите ▶ у реплики, найдите её место в записи и нажмите здесь">Привязать к позиции плеера</button><button class="btn sm" data-act="resetshift">Сброс</button></div>` : '';
    const hist = conv.evaluations.length > 1 ? `<select id="eval-select" style="width:auto">${conv.evaluations.map((e) => `<option value="${e.id}" ${card && card.evaluation.id === e.id ? 'selected' : ''}>Оценка #${e.id} · ${dt(e.created_at)}${e.parent_id ? ' · перенос' : ''}</option>`).join('')}</select>` : '';
    const stale = card && R.active && card.checklist.id !== R.active.id;
    const actions = excluded ? '<span class="tag" title="EXCLUDE_CHANNELS">канал не отправляется в модель</span>'
      : `${stale ? `<button class="btn" data-act="reapply" title="Модель переоценит только изменённые критерии">Применить чек-лист v${R.active.version}</button>` : ''}<button class="btn primary" data-act="evalone" data-id="${esc(conv.id)}">${card ? 'Оценить заново' : 'Запустить оценку'}</button>`;
    const right = card ? resultPanel(card)
      : `<div class="panel empty">${excluded ? 'Этот канал исключён из отправки в модель (реальные звонки не передаются в бесплатный API). Нет данных для оценки.' : 'Нет данных: оценка не запускалась. Нажмите «Запустить оценку».'}</div>`;
    return `<div class="row" style="margin-bottom:14px"><button class="btn" data-act="nav" data-v="dialogs">← К списку</button><h2 style="color:var(--text)">${esc(conv.id)}</h2>
      <span class="tag">${esc(conv.channel)}</span><span class="tag">${esc(conv.language)}</span>${hist}<div class="spacer"></div>${actions}</div>
    <div class="grid2"><div class="panel sticky"><h2>Транскрипт</h2>${audio}<div class="transcript">${msgs || '<div class="empty">Нет данных</div>'}</div></div><div>${right}</div></div>`;
  }
  function resultPanel(card) {
    const f = card.final, o = card.original, meta = card.meta || {};
    const col = f.total === null ? '' : f.total >= 80 ? 'var(--green)' : f.total >= 55 ? 'var(--amber)' : 'var(--red)';
    const secs = f.sections.filter((s) => s.max > 0).map((s) => `<div class="sec"><span>${esc(s.title)}</span><span>${fmt(s.points)} / ${fmt(s.max)}</span></div><div class="bar"><i style="width:${s.max ? (s.points / s.max) * 100 : 0}%"></i></div>`).join('');
    const g = f.gross_errors;
    const tokens = meta.tokens && meta.tokens.total_tokens ? ` · токены ${meta.tokens.prompt_tokens}/${meta.tokens.completion_tokens}` : '';
    const criterionVersions = [...new Set(Object.values(meta.criteria_prompt_versions || {}).filter(Boolean))];
    const promptLabel = meta.prompt_version ? `промпт ${esc(meta.prompt_version)}` : 'версия промпта не сохранена';
    const mixedPromptLabel = criterionVersions.length > 1 ? ` · версии критериев ${criterionVersions.map(esc).join(', ')}` : '';
    const metaLine = `${esc(meta.model || '')} · ${promptLabel}${mixedPromptLabel}${meta.seconds ? ` · ${meta.seconds} с` : ''}${tokens}${meta.reapplied_from ? ` · перенесено из оценки #${meta.reapplied_from}` : ''}`;
    const warns = f.warnings.length ? `<details class="small" style="margin-top:10px"><summary>Предупреждения (${f.warnings.length})</summary>${f.warnings.map((w) => `<div>• ${esc(w)}</div>`).join('')}</details>` : '';
    const crits = f.criteria.map((i) => critHtml(card, i)).join('');
    return `<div class="panel"><div class="row" style="align-items:flex-start;gap:22px"><div class="ring" style="--p:${f.total || 0};--c:${col}"><div><div><b>${fmt(f.total)}</b><small>из 100</small></div></div></div>
      <div style="flex:1;min-width:220px"><h2>Итог${f.preliminary ? ' <span class="tag amber">предварительный</span>' : ''}</h2>${secs || '<div class="small">Нет данных</div>'}
      <p class="small" style="margin:8px 0 0">${o.total !== f.total ? `Исходный итог: <b>${fmt(o.total)}</b> → после апелляций: <b>${fmt(f.total)}</b>. ` : ''}Чек-лист v${card.checklist.version}${card.checklist.is_active ? '' : ' (не активный)'} · ${metaLine}</p></div></div>
      <div class="flagbox ${g.detected ? 'bad' : 'ok'}">${g.detected ? `⚠ Грубая ошибка: ${esc(g.types.map((t) => GROSS[t] || t).join(', ') || 'тип не указан')}. Отмечено отдельно, на баллы не влияет` : '✓ Грубых ошибок не выявлено'}</div>${warns}</div>
      ${operatorSummaryPanel(card.operator_summary)}
      <div class="panel" style="margin-top:18px"><h2>Критерии</h2>${crits}</div>`;
  }
  function operatorSummaryPanel(summary) {
    if (!summary) return '';
    const evidence = (ids) => (ids || []).map((n) => `<span class="chip" data-act="jump" data-i="${esc(n)}">#${esc(n)}</span>`).join(' ');
    const strengths = (summary.strengths || []).map((x) => `<div class="crit"><span class="tag green">Хорошо</span> <b>${esc(x.title)}</b> ${evidence(x.evidence_ids)}</div>`).join('');
    const improvements = (summary.improvements || []).map((x) => `<div class="${x.priority === 'critical' ? 'flagbox bad' : 'crit'}" style="margin-top:10px"><b>${x.priority === 'critical' ? 'Важно · ' : ''}${esc(x.title)}</b>${x.priority === 'critical' && x.feedback ? `<p>${esc(x.feedback)}</p>` : ''}<p class="small"><b>В следующий раз:</b> ${esc(x.action)}</p>${evidence(x.evidence_ids)}</div>`).join('');
    const review = summary.review && summary.review.length ? `<p class="small">Не удалось оценить: ${summary.review.map((x) => esc(x.title)).join(', ')}. Эти пункты требуют проверки.</p>` : '';
    const empty = !strengths && !improvements && !review;
    return `<div class="panel" style="margin-top:18px"><div class="row"><h2 style="margin:0">Краткая сводка для оператора</h2><div class="spacer"></div><button class="btn sm" data-act="download-summary">Скачать .txt</button></div>
      ${strengths ? `<h3>Хорошо получилось</h3>${strengths}` : ''}
      ${improvements ? `<h3>Что улучшить</h3>${improvements}` : ''}
      ${review}${empty ? '<p class="small">Нет достаточно данных для сводки.</p>' : ''}</div>`;
  }
  function critHtml(card, it) {
    const clId = card.checklist.id, c = critOf(clId, it.id) || {}, conv = R.conv;
    const orig = card.original.criteria.find((q) => q.id === it.id);
    const msg = (n) => conv.transcript[n - 1];
    const evid = (it.evidence_ids || []).filter((n) => msg(n));
    const chips = evid.map((n) => `<span class="chip" data-act="jump" data-i="${n}">#${n} · ${mmss(msg(n).offset_sec)}</span>`).join(' ');
    const quotes = evid.slice(0, 2).map((n) => `<div class="quote">${esc(SPEAKER[msg(n).speaker] || msg(n).speaker)}: ${esc(msg(n).text)}</div>`).join('');
    const pts = it.type === 'flag' ? '' : `<span class="small">${it.status === 'error' ? 'исключён из расчёта' : it.na ? 'вес перераспределён' : `${fmt(it.final_points)} из ${fmt(it.effective_weight)}`} · вес ${fmt(it.weight)}</span>`;
    const aps = card.appeals.filter((a) => a.criterion_id === it.id);
    const open = aps.some((a) => a.status === 'open');
    const hist = aps.length ? `<div class="hist">${aps.map((a) => `Апелляция #${a.id} (${a.status === 'open' ? 'на рассмотрении' : 'решена'}): «${esc(a.comment)}»${a.status === 'resolved' ? `<br>${a.decision === 'changed' ? `Исходная оценка: <b>${esc(ansLabel(orig, c))}</b> → решение: <b>${esc(ansLabel({ ...it, ...a.new_answer, type: it.type }, c))}</b>` : 'Оценка подтверждена'} — ${esc(a.reason)}` : ''}`).join('<br>')}</div>` : '';
    return `<div class="crit ${it.na ? 'na' : ''}"><div class="crit-h"><h3>${esc(it.title)}</h3><span class="${ansTag(it, c)}">${esc(ansLabel(it, c))}</span>${pts}
      ${open ? '<span class="tag gold">апелляция открыта</span>' : `<button class="btn sm" data-act="appeal" data-c="${esc(it.id)}">Оспорить</button>`}</div>
      <p>${esc(it.explanation || 'Нет данных')}</p>${it.checked_range ? `<p class="small">Проверенный участок: ${esc(it.checked_range)}</p>` : ''}
      ${it.na && c.na_condition ? `<p class="small">Условие N/A: ${esc(c.na_condition)}</p>` : ''}${quotes}${chips ? `<div class="row" style="gap:6px">${chips}</div>` : ''}${hist}</div>`;
  }
  function appealModal(critId) {
    const it = R.card.final.criteria.find((q) => q.id === critId), c = critOf(R.card.checklist.id, critId) || {};
    $('#modal-host').innerHTML = `<div class="modal-bg" data-act="closemodal"><div class="panel modal" data-stop="1"><h2>Оспорить критерий</h2>
      <p><b>${esc(it.title)}</b> — ${esc(ansLabel(it, c))}</p><div class="quote">${esc(it.explanation)}</div>
      <label>Комментарий</label><textarea id="ap-text" rows="4" placeholder="Почему вы не согласны с оценкой?"></textarea>
      <div class="row" style="margin-top:12px"><button class="btn primary" data-act="sendappeal" data-c="${esc(critId)}">Подать апелляцию</button><button class="btn" data-act="closemodal">Отмена</button></div></div></div>`;
    $('#ap-text').focus();
  }

  /* ---------- Апелляции ---------- */
  function viewAppeals() {
    if (!R.online) return offline();
    const sel = R.appeals.find((a) => a.id === S.ui.appealId);
    const filters = [['open', 'Открытые'], ['resolved', 'Решённые'], ['', 'Все']].map(([k, l]) => `<button class="btn sm ${S.appealFilter === k ? 'primary' : ''}" data-act="appfilter" data-v="${k}">${l}</button>`).join('');
    const l = R.appeals.slice().reverse().map((a) => `<div class="list-item ${sel && sel.id === a.id ? 'on' : ''}" data-act="pick" data-id="${a.id}"><div class="row"><b>${esc(a.conversation_id)}</b><div class="spacer"></div><span class="tag ${a.status === 'open' ? 'amber' : 'green'}">${a.status === 'open' ? 'открыта' : a.decision === 'changed' ? 'изменена' : 'подтверждена'}</span></div><div class="small">${esc(a.criterion.title)} · ${esc(a.comment.slice(0, 70))}</div></div>`).join('');
    return `<div class="split"><div class="panel"><h2>Обращения · ${R.appeals.length}</h2><div class="row" style="gap:6px;margin-bottom:12px">${filters}</div>${l || '<div class="empty">Нет данных. Откройте карточку диалога и нажмите «Оспорить».</div>'}</div>
      <div>${sel ? reviewPanel(sel) : '<div class="panel empty">Выберите обращение слева.</div>'}</div></div>`;
  }
  function reviewPanel(a) {
    const c = a.criterion, it = a.disputed, ev = new Set(it.evidence_ids || []);
    const frag = a.fragment.map((m) => `<div class="msg ${esc(m.speaker)} ${ev.has(m.index) ? 'hl' : ''}"><span class="ts" title="${esc(m.timestamp)}">#${m.index} ${mmss(m.offset_sec)}</span><span class="who">${esc(SPEAKER[m.speaker] || m.speaker)}</span><span>${esc(m.text)}</span></div>`).join('');
    const opts = (c.type === 'scale' ? c.scale.slice().sort((x, y) => y.value - x.value).map((s) => `<option value="${s.value}">${s.value} — ${esc(s.description)}</option>`).join('')
      : c.type === 'flag' ? '<option value="1">Выявлено</option><option value="0">Не выявлено</option>' : '<option value="1">Да</option><option value="0">Нет</option>') + (c.na_allowed ? '<option value="na">N/A</option>' : '');
    const resolved = a.status === 'resolved'
      ? `<div class="hist">${a.decision === 'changed' ? `Оценка изменена: <b>${esc(ansLabel(it, c))}</b> → <b>${esc(ansLabel({ ...it, ...a.new_answer, type: c.type }, c))}</b>` : `Оценка подтверждена: <b>${esc(ansLabel(it, c))}</b>`}<br>Причина: ${esc(a.reason)}<br>${dt(a.resolved_at)}</div>`
      : `<label>Решение</label><select id="rv-ans">${opts}</select>
        <label>Причина</label><textarea id="rv-reason" rows="3" placeholder="Почему оценка подтверждена или изменена"></textarea>
        <div class="row" style="margin-top:12px"><button class="btn" data-act="decide" data-mode="upheld">Подтвердить оценку</button><button class="btn primary" data-act="decide" data-mode="changed">Изменить оценку</button></div>`;
    return `<div class="panel"><div class="row"><h2 style="margin:0">${esc(c.title)}</h2><div class="spacer"></div><button class="btn sm" data-act="open" data-id="${esc(a.conversation_id)}" data-eval="${a.evaluation_id}">Открыть карточку</button></div>
      <p class="small">Диалог ${esc(a.conversation_id)} · ${esc(a.language)} · оценка #${a.evaluation_id} · сейчас: <b>${esc(ansLabel(it, c))}</b> · итог ${fmt(a.total)}</p>
      <label>Комментарий</label><div class="quote">${esc(a.comment)}</div>
      <label>Обоснование системы</label><div class="quote">${esc(it.explanation || 'Нет данных')}</div>${it.checked_range ? `<p class="small">Проверенный участок: ${esc(it.checked_range)}</p>` : ''}
      <label>Фрагмент диалога</label>${frag || '<div class="small">Нет данных</div>'}${resolved}</div>`;
  }

  /* ---------- Чек-лист ---------- */
  function newCriterion() {
    const n = draft.criteria.length + 1;
    let id = `c${String(n).padStart(2, '0')}_new`; while (draft.criteria.some((c) => c.id === id)) id += '_';
    return { id, _new: true, section: (draft.sections[0] || {}).id || 'main', title: 'Новый критерий', type: 'binary', weight: 10, na_allowed: false, na_condition: '', rule: 'Да — …', scale: [], guidance: '', examples_pass: [], examples_fail: [], flag_types: [] };
  }
  function viewChecklist() {
    if (!R.online) return offline();
    if (!R.active) return '<div class="panel empty">Нет данных: на бэкенде нет активного чек-листа.</div>';
    if (!draft) draft = clone(R.active.data);
    const sel = (S.ui.editCrit && draft.criteria.find((c) => c.id === S.ui.editCrit)) || draft.criteria[0];
    const secTitle = (id) => (draft.sections.find((s) => s.id === id) || {}).title || id;
    const sumW = draft.criteria.filter((c) => c.type !== 'flag').reduce((s, c) => s + (+c.weight || 0), 0);
    const list = draft.criteria.map((c) => `<div class="list-item ${sel && sel.id === c.id ? 'on' : ''}" data-act="editpick" data-c="${esc(c.id)}"><div class="row"><b>${esc(c.title)}</b><div class="spacer"></div><span class="tag">${c.type === 'flag' ? 'флаг' : fmt(c.weight)}</span></div><div class="small">${esc(secTitle(c.section))} · ${TYPE[c.type] || c.type}${c.na_allowed ? ' · N/A' : ''}${c._new ? ' · новый' : ''}</div></div>`).join('');
    const versions = R.versions.map((v) => `<div class="row small" style="margin-top:6px"><span>v${v.version} · ${dt(v.created_at)}</span><div class="spacer"></div>${v.is_active ? '<span class="tag green">активна</span>' : `<button class="btn sm" data-act="activate" data-id="${v.id}">Сделать активной</button>`}</div>${v.comment ? `<div class="small" style="opacity:.8">${esc(v.comment)}</div>` : ''}`).join('');
    return `<div class="split"><div><div class="panel"><h2>Критерии</h2>${list}<button class="btn" data-act="addcrit" style="width:100%">+ Добавить критерий</button>
      <p class="small">Сумма весов: <b style="color:${sumW === 100 ? 'var(--green)' : 'var(--amber)'}">${fmt(sumW)}</b> (итог всегда нормируется к 100)</p></div>
      <div class="panel" style="margin-top:18px"><h2>Версии</h2>${versions || '<div class="small">Нет данных</div>'}</div></div>
      <div>${lastDiff ? diffPanel(lastDiff) : ''}<div class="panel">${sel ? critForm(sel) : ''}<hr style="border:0;border-top:1px solid var(--line);margin:16px 0">
        <div class="row"><label style="margin:0">Название чек-листа</label><input data-cl="name" value="${esc(draft.name)}" style="flex:1"></div>
        <label>Комментарий к версии</label><input id="cl-comment" placeholder="Что изменено и зачем">
        <div class="row" style="margin-top:12px"><button class="btn primary" data-act="savecl">Сохранить новую версию</button><button class="btn" data-act="saveweights" title="Новая версия только с изменёнными весами — пересчёт всех оценок сразу, без вызова модели">Сохранить только веса</button><button class="btn" data-act="resetdraft">Отменить правки</button></div>
        <p class="small">«Сохранить» создаёт новую активную версию и показывает, какие критерии придётся переоценить моделью. «Только веса» пересчитывает все оценки мгновенно, без модели. Чтобы перенести оценки на новую версию, нажмите «Применить к диалогам».</p></div></div></div>`;
  }
  function diffPanel(d) {
    const line = (label, ids, tag) => (ids.length ? `<div class="row small" style="margin-top:4px"><span style="min-width:150px">${label}</span>${ids.map((i) => `<span class="tag ${tag}">${esc(i)}</span>`).join(' ')}</div>` : '');
    return `<div class="panel" style="margin-bottom:18px"><div class="row"><h2 style="margin:0">Сохранено: изменения версии</h2><div class="spacer"></div><button class="btn sm" data-act="closediff">Скрыть</button></div>
      ${line('Изменены', d.changed, 'amber')}${line('Новые', d.new, 'green')}${line('Только вес/название', d.weight_only, '')}${line('Удалены', d.removed, 'red')}
      <p class="small" style="margin:10px 0">${d.needs_llm.length ? `Модель переоценит только: <b>${d.needs_llm.map(esc).join(', ')}</b>. Остальные ответы будут скопированы.` : 'Модель вызываться не будет: изменились только веса или названия.'}</p>
      <button class="btn primary" data-act="batch" data-mode="reapply" ${R.job && R.job.status === 'running' ? 'disabled' : ''}>Применить к диалогам${S.dataset ? ` (${esc(S.dataset)})` : ''}</button></div>`;
  }
  function critForm(c) {
    const lines = (a) => esc((a || []).join('\n'));
    const scale = (c.scale || []).map((s) => `${s.value}|${s.description || ''}`).join('\n');
    const secs = draft.sections.map((s) => `<option value="${esc(s.id)}">${esc(s.title)}</option>`).join('');
    return `<h2>Редактирование критерия</h2><div data-crit="${esc(c.id)}">
      <div class="row" style="gap:12px;align-items:flex-end"><div style="flex:1"><label>ID</label><input data-f="id" value="${esc(c.id)}" ${c._new ? '' : 'disabled title="ID существующего критерия не меняется — иначе оценки не сопоставятся"'}></div>
        <div style="flex:3"><label>Название</label><input data-f="title" value="${esc(c.title)}"></div></div>
      <div class="row" style="gap:12px;align-items:flex-end"><div style="flex:2"><label>Секция</label><input data-f="section" list="sec-list" value="${esc(c.section)}"><datalist id="sec-list">${secs}</datalist></div>
      <div style="flex:1"><label>Тип ответа</label><select data-f="type"><option value="binary" ${c.type === 'binary' ? 'selected' : ''}>Да / Нет</option><option value="scale" ${c.type === 'scale' ? 'selected' : ''}>Числовая шкала</option><option value="flag" ${c.type === 'flag' ? 'selected' : ''}>Флаг (без баллов)</option></select></div>
      <div style="flex:1"><label>Вес</label><input type="number" min="0" step="0.5" data-f="weight" value="${c.weight}" ${c.type === 'flag' ? 'disabled' : ''}></div></div>
      <label><input type="checkbox" data-f="na_allowed" style="width:auto" ${c.na_allowed ? 'checked' : ''} ${c.type === 'flag' ? 'disabled' : ''}> Разрешить N/A</label>
      <label>Правило оценки</label><textarea rows="2" data-f="rule">${esc(c.rule)}</textarea>
      ${c.na_allowed ? `<label>Условие N/A</label><textarea rows="2" data-f="na_condition">${esc(c.na_condition)}</textarea>` : ''}
      ${c.type === 'scale' ? `<label>Шкала (по строке: значение|описание, верхняя ступень = полный вес)</label><textarea rows="5" data-f="scale">${esc(scale)}</textarea>` : ''}
      ${c.type === 'flag' ? `<label>Типы нарушений (через запятую)</label><input data-f="flag_types" value="${esc((c.flag_types || []).join(', '))}">` : ''}
      <label>Пояснение для модели</label><textarea rows="3" data-f="guidance" placeholder="Как применять правило в спорных случаях">${esc(c.guidance)}</textarea>
      <div class="row" style="gap:12px;align-items:flex-start"><div style="flex:1"><label>Примеры «Да» (по строке)</label><textarea rows="2" data-f="examples_pass">${lines(c.examples_pass)}</textarea></div>
        <div style="flex:1"><label>Примеры «Нет» (по строке)</label><textarea rows="2" data-f="examples_fail">${lines(c.examples_fail)}</textarea></div></div>
      <div style="margin-top:12px"><button class="btn danger sm" data-act="delcrit" data-c="${esc(c.id)}">Удалить критерий</button></div></div>`;
  }
  const cleanDraft = () => { const d = clone(draft); d.criteria.forEach((c) => delete c._new); return d; };

  /* ---------- Аналитика ---------- */
  function viewAnalytics() {
    if (!R.online) return offline();
    const a = R.analytics;
    if (!a) return '<div class="panel empty">Загрузка…</div>';
    const head = `<div class="row" style="margin-bottom:14px"><h2 style="color:var(--text)">Аналитика${S.dataset ? ` · ${esc(S.dataset)}` : ' · все наборы'}</h2><div class="spacer"></div><button class="btn" data-act="reload-analytics">Обновить</button></div>`;
    if (!a.evaluated) return head + '<div class="panel empty">Нет данных: оцените диалоги на вкладке «Диалоги».</div>';
    const kpi = (label, value, extra = '') => `<div class="panel kpi"><div class="small">${label}</div><b class="${extra}">${value}</b></div>`;
    const group = (title, obj) => `<div class="panel"><h2>${title}</h2><table><thead><tr><th></th><th>Диалогов</th><th>Средний итог</th></tr></thead><tbody>${Object.entries(obj).map(([k, v]) => `<tr><td><b>${esc(k)}</b></td><td>${v.count}</td><td><span class="score ${cls(v.avg_total)}" style="font-size:15px">${fmt(v.avg_total)}</span><div class="bar"><i style="width:${v.avg_total || 0}%"></i></div></td></tr>`).join('')}</tbody></table></div>`;
    const crit = a.criteria.map((c) => `<tr><td><b>${esc(c.title)}</b><div class="small">${esc(c.id)} · ${TYPE[c.type] || c.type}</div></td><td>${c.evaluated}</td><td>${c.na_share === null ? '—' : fmt(c.na_share) + '%'}</td>
      <td>${c.type === 'flag' ? `<span class="tag ${c.flags ? 'red' : 'green'}">флагов: ${c.flags}</span>` : c.avg_fulfillment_pct === null ? '—' : `${fmt(c.avg_fulfillment_pct)}%<div class="bar"><i style="width:${c.avg_fulfillment_pct}%"></i></div>`}</td><td>${c.errors || ''}</td></tr>`).join('');
    const worst = a.worst.map((w) => `<tr class="click" data-act="open" data-id="${esc(w.conversation_id)}" data-eval="${w.evaluation_id}"><td><b>${esc(w.conversation_id)}</b></td><td><span class="score ${cls(w.total)}">${fmt(w.total)}</span></td></tr>`).join('');
    return `${head}<div class="kpis">${kpi('Оценено диалогов', a.evaluated)}${kpi('Средний итог', fmt(a.avg_total), 'score ' + cls(a.avg_total))}${kpi('Грубые ошибки', a.gross_errors, a.gross_errors ? 'score lo' : '')}</div>
      <div class="grid2" style="margin-top:18px">${group('По языкам', a.by_language)}${group('По каналам', a.by_channel)}</div>
      <div class="grid2" style="margin-top:18px"><div class="panel"><h2>По критериям</h2><table><thead><tr><th>Критерий</th><th>Оценено</th><th>N/A</th><th>Выполнение</th><th>Ошибок</th></tr></thead><tbody>${crit}</tbody></table></div>
      <div class="panel"><h2>5 худших диалогов</h2><table><tbody>${worst || '<tr><td class="small">Нет данных</td></tr>'}</tbody></table></div></div>`;
  }

  /* ---------- рендер ---------- */
  function render() {
    renderNav();
    const v = S.ui.view;
    $('#view').innerHTML = v === 'dialogs' ? viewDialogs() : v === 'card' ? viewCard() : v === 'appeals' ? viewAppeals() : v === 'checklist' ? viewChecklist() : viewAnalytics();
    if (v === 'card') setupAudio();
    save();
  }
  function renderJob() { const box = $('.jobbox'); if (box && S.ui.view === 'dialogs') box.outerHTML = jobBox(); }

  /* Аудио идёт через прокси бэкенда /api/audio/{id}: он достаёт mp3 со страницы организаторов и поддерживает перемотку */
  const SHIFT_DEFAULT = -3; // метка реплики — момент распознанной фразы, сама фраза звучала раньше
  const shiftOf = (id) => ((S.audioShift || {})[id] ?? SHIFT_DEFAULT);
  const offsetOf = (i) => { const m = R.conv && R.conv.transcript[i - 1]; return (m && m.offset_sec) || 0; };
  function setupAudio() {
    const p = $('#player'), msg = $('#audio-msg'); if (!p || !R.conv) return;
    p.addEventListener('error', () => { msg.innerHTML = `Не удалось загрузить запись через бэкенд. <a href="${esc(R.conv.audio_url)}" target="_blank" rel="noopener" style="color:var(--gold)">Открыть запись в новой вкладке</a>`; }, { once: true });
  }

  const go = async (v) => {
    S.ui.view = v; if (v === 'checklist') { draft = null; }
    render(); window.scrollTo(0, 0);
    try {
      if (v === 'appeals') { await loadAppeals(); render(); }
      if (v === 'analytics') { R.analytics = null; render(); R.analytics = await api('/analytics' + qs({ dataset: S.dataset })); render(); }
      if (v === 'checklist' && R.online) { [R.versions, R.active] = await Promise.all([api('/checklists'), api('/checklists/active')]); draft = null; render(); }
      if (v === 'dialogs' && R.online) { await loadConvs(); render(); }
    } catch (e) { toast('Ошибка: ' + e.message); render(); }
  };
  async function loadAppeals() { R.appeals = await api('/appeals' + qs({ status: S.appealFilter })); R.openAppeals = S.appealFilter === 'open' ? R.appeals.length : R.openAppeals; }
  function jump(i) { const el = $('#m-' + i); if (!el) return; el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); }

  async function runBatch(mode, onlyMissing) {
    if (mode === 'evaluate' && !onlyMissing && !confirm('Переоценить все диалоги набора заново? Это расходует лимит запросов к модели.')) return;
    try {
      R.job = await post('/evaluate/batch', { dataset: S.dataset || null, mode, only_missing: !!onlyMissing });
      lastDiff = null; S.ui.view = 'dialogs'; render(); toast(mode === 'reapply' ? 'Применение чек-листа запущено' : 'Пакетная оценка запущена'); pollJob();
    } catch (e) { toast('Ошибка: ' + e.message); }
  }
  async function pollJob() {
    clearTimeout(pollTimer);
    if (!R.job) return;
    try {
      R.job = await api(`/jobs/${R.job.id}`); renderJob();
      if (R.job.status === 'running') { pollTimer = setTimeout(pollJob, 2500); return; }
      await loadConvs(); render();
      toast(`Готово: ${R.job.done.length}, пропущено: ${R.job.skipped.length}, ошибок: ${R.job.failed.length}`);
    } catch (e) { toast('Потеряна связь с задачей: ' + e.message); }
  }
  function download(name, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function downloadText(name, text) {
    const blob = new Blob(['\ufeff', text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function operatorSummaryText() {
    const summary = R.card && R.card.operator_summary;
    if (!summary || !R.conv) return '';
    const lines = [`Сводка для оператора · диалог ${R.conv.id}`, '', 'Хорошо получилось:'];
    if (summary.strengths.length) summary.strengths.forEach((x) => lines.push(`• ${x.title}`));
    else lines.push('• Отмеченных сильных сторон нет.');
    lines.push('', 'Что улучшить:');
    if (summary.improvements.length) {
      summary.improvements.forEach((x) => {
        lines.push(`• ${x.priority === 'critical' ? 'Важно: ' : ''}${x.title}`);
        if (x.feedback) lines.push(`  Причина: ${x.feedback}`);
        lines.push(`  В следующий раз: ${x.action}`);
        (x.evidence_ids || []).forEach((n) => {
          const m = R.conv.transcript[n - 1];
          lines.push(`  Реплика из диалога: ${m ? `#${n} ${SPEAKER[m.speaker] || m.speaker}: ${m.text}` : `#${n}`}`);
        });
      });
    } else lines.push('• Зон для улучшения не выявлено.');
    if (summary.review.length) {
      lines.push('', 'Требует проверки:');
      summary.review.forEach((x) => lines.push(`• ${x.title} — модель не смогла оценить критерий.`));
    }
    return lines.join('\r\n');
  }
  async function afterImport(res) {
    S.dataset = res.dataset; await loadBase(); render();
    toast(`Импортировано: ${res.imported}${res.skipped ? `, пропущено: ${res.skipped}` : ''} (набор ${res.dataset})`);
  }

  /* ---------- события ---------- */
  document.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-act]'); if (!t || !$('#cqa-root').contains(t)) return;
    if (t.dataset.act === 'closemodal' && e.target.closest('[data-stop]') && !e.target.closest('button')) return;
    const a = t.dataset.act, id = t.dataset.id;
    try {
      if (a === 'nav') return go(t.dataset.v);
      if (a === 'connect') { S.backendUrl = $('#backend-url').value.trim().replace(/\/$/, ''); R.online = null; render(); await loadBase(); render(); return toast(R.online ? 'Бэкенд подключён' : 'Бэкенд недоступен'); }
      if (a === 'open') { await openCard(id, t.dataset.eval ? +t.dataset.eval : null); return go('card'); }
      if (a === 'import-group') {
        const g = $('#import-group').value.trim(); if (!g) return toast('Укажите group_id'); S.importGroup = g;
        t.disabled = true; t.textContent = 'Импорт…';
        return afterImport(await post('/datasets/import', { group_id: g }));
      }
      if (a === 'import-url') {
        const url = $('#import-url').value.trim(); if (!/^https:\/\//.test(url)) return toast('Нужна ссылка https://…');
        t.disabled = true; t.textContent = 'Загрузка…';
        const g = $('#import-group').value.trim();
        return afterImport(await post('/datasets/import', { url, group_id: /group_id=/.test(url) ? null : g || null }));
      }
      if (a === 'evalone') {
        e.stopPropagation(); t.disabled = true; t.textContent = 'Оценка…'; toast('Модель анализирует диалог…');
        const card = await post('/evaluate', { conversation_id: id });
        await openCard(id, card.evaluation.id); await loadConvs();
        toast(`Итог: ${fmt(card.final.total)}`); return go('card');
      }
      if (a === 'reapply') {
        t.disabled = true; t.textContent = 'Применение…';
        const card = await post(`/evaluations/${R.card.evaluation.id}/reapply`);
        await openCard(R.conv.id, card.evaluation.id); await loadConvs(); render();
        return toast(card.reapply.llm_called ? `Переоценены: ${card.reapply.diff.needs_llm.join(', ') || 'критерии без ответа'}` : 'Пересчитано без вызова модели');
      }
      if (a === 'batch') return runBatch(t.dataset.mode, t.dataset.missing === '1');
      if (a === 'closejob') { R.job = null; return render(); }
      if (a === 'export') {
        const m = S.exportMeta; if (!m.teamName.trim()) { toast('Укажите название команды'); return $('#export-team').focus(); }
        const data = await api('/export' + qs({ dataset: S.dataset, team_name: m.teamName.trim(), model_mode: m.modelMode, model_name: m.modelName.trim() }));
        if (!data.results.length) return toast('Нет данных: сначала оцените диалоги');
        download(`cqa-results-${S.dataset || 'all'}-${new Date().toISOString().slice(0, 10)}.json`, data);
        return toast(`Скачан JSON: ${data.results.length} оценок`);
      }
      if (a === 'download-summary') {
        const text = operatorSummaryText(); if (!text) return toast('Нет сводки для скачивания');
        const safeId = R.conv.id.replace(/[^a-zA-Z0-9_-]/g, '_');
        downloadText(`cqa-summary-${safeId}.txt`, text);
        return toast('Сводка скачана');
      }
      if (a === 'jump') return jump(+t.dataset.i);
      if (a === 'seek') { const p = $('#player'); if (p && R.conv) { S.ui.lastSeek = +t.dataset.i; p.currentTime = Math.max(0, offsetOf(+t.dataset.i) + shiftOf(R.conv.id)); p.play().catch(() => {}); } return jump(+t.dataset.i); }
      if (a === 'syncpos') { const p = $('#player'), i = S.ui.lastSeek; if (!p || !R.conv || i === undefined) return toast('Сначала нажмите ▶ у реплики'); S.audioShift[R.conv.id] = Math.round((p.currentTime - offsetOf(i)) * 10) / 10; $('#shift').value = S.audioShift[R.conv.id]; save(); return toast('Сдвиг сохранён: ' + S.audioShift[R.conv.id] + ' с'); }
      if (a === 'resetshift') { delete S.audioShift[R.conv.id]; $('#shift').value = SHIFT_DEFAULT; return save(); }
      if (a === 'appeal') return appealModal(t.dataset.c);
      if (a === 'closemodal') { $('#modal-host').innerHTML = ''; return; }
      if (a === 'sendappeal') {
        const text = $('#ap-text').value.trim(); if (!text) return toast('Добавьте комментарий');
        const ap = await post(`/evaluations/${R.card.evaluation.id}/appeals`, { criterion_id: t.dataset.c, comment: text });
        $('#modal-host').innerHTML = ''; S.ui.appealId = ap.id; await Promise.all([refreshCard(), loadOpenCount(), loadConvs()]); render();
        return toast('Апелляция подана — она в очереди проверяющего');
      }
      if (a === 'appfilter') { S.appealFilter = t.dataset.v; await loadAppeals(); return render(); }
      if (a === 'pick') { S.ui.appealId = +id; return render(); }
      if (a === 'decide') {
        const reason = $('#rv-reason').value.trim(); if (!reason) return toast('Укажите причину');
        const body = { decision: t.dataset.mode, reason };
        if (t.dataset.mode === 'changed') { const v = $('#rv-ans').value; if (v === 'na') body.na = true; else body.value = Number(v); }
        const res = await post(`/appeals/${S.ui.appealId}/resolve`, body);
        await Promise.all([loadAppeals(), loadOpenCount(), loadConvs()]); if (!R.appeals.some((x) => x.id === S.ui.appealId)) { S.appealFilter = ''; await loadAppeals(); }
        render(); return toast(`Решение сохранено. Итог: ${fmt(res.original_total)} → ${fmt(res.final_total)}`);
      }
      if (a === 'editpick') { S.ui.editCrit = t.dataset.c; return render(); }
      if (a === 'addcrit') { const c = newCriterion(); draft.criteria.push(c); S.ui.editCrit = c.id; return render(); }
      if (a === 'delcrit') { if (!confirm('Удалить критерий из чек-листа? Изменение вступит в силу после сохранения.')) return; draft.criteria = draft.criteria.filter((c) => c.id !== t.dataset.c); S.ui.editCrit = null; return render(); }
      if (a === 'resetdraft') { draft = null; return render(); }
      if (a === 'closediff') { lastDiff = null; return render(); }
      if (a === 'savecl') {
        const res = await post('/checklists', { data: cleanDraft(), comment: $('#cl-comment').value.trim() });
        lastDiff = res.diff; R.clCache[res.checklist.id] = res.checklist; draft = null;
        [R.versions, R.active] = await Promise.all([api('/checklists'), api('/checklists/active')]);
        render(); window.scrollTo(0, 0); return toast(`Сохранена версия v${res.checklist.version}`);
      }
      if (a === 'saveweights') {
        const base = Object.fromEntries(R.active.data.criteria.map((c) => [c.id, c.weight]));
        const weights = Object.fromEntries(draft.criteria.filter((c) => c.id in base && +c.weight !== base[c.id]).map((c) => [c.id, +c.weight]));
        if (!Object.keys(weights).length) return toast('Веса не изменены');
        const res = await api('/checklists/active/weights', { method: 'PATCH', body: JSON.stringify({ weights, reapply_all: true, comment: $('#cl-comment').value.trim() }) });
        draft = null; [R.versions, R.active] = await Promise.all([api('/checklists'), api('/checklists/active')]); await loadConvs(); render();
        return toast(`Сохранена v${res.checklist.version}. Пересчитано оценок: ${res.reapplied.done} — без вызова модели`);
      }
      if (a === 'activate') {
        await post(`/checklists/${id}/activate`); [R.versions, R.active] = await Promise.all([api('/checklists'), api('/checklists/active')]); draft = null; render();
        return toast(`Активна версия v${R.active.version}. Чтобы пересчитать оценки, нажмите «Применить активный чек-лист»`);
      }
      if (a === 'reload-analytics') return go('analytics');
    } catch (err) { toast('Ошибка: ' + err.message); render(); }
  });

  document.addEventListener('input', (e) => {
    const el = e.target, f = el.dataset;
    const setters = { 'backend-url': (v) => { S.backendUrl = v.trim(); }, 'import-group': (v) => { S.importGroup = v; }, 'import-url': (v) => { S.importUrl = v; }, 'export-team': (v) => { S.exportMeta.teamName = v; }, 'export-model': (v) => { S.exportMeta.modelName = v; } };
    if (setters[el.id]) { setters[el.id](el.value); return save(); }
    if (el.id === 'shift' && R.conv) { S.audioShift[R.conv.id] = Number(el.value) || 0; return save(); }
    if (f.cl === 'name') { draft.name = el.value; return; }
    if (!f.f || !draft) return;
    const c = draft.criteria.find((q) => q.id === el.closest('[data-crit]').dataset.crit); if (!c) return;
    const v = el.type === 'checkbox' ? el.checked : el.value;
    if (f.f === 'weight') c.weight = Number(v) || 0;
    else if (f.f === 'scale') c.scale = String(v).split('\n').map((l) => l.trim()).filter(Boolean).map((l) => { const [n, ...r] = l.split('|'); return { value: Number(n), description: r.join('|').trim() }; }).filter((s) => !isNaN(s.value));
    else if (f.f === 'examples_pass' || f.f === 'examples_fail') c[f.f] = String(v).split('\n').map((l) => l.trim()).filter(Boolean);
    else if (f.f === 'flag_types') c.flag_types = String(v).split(',').map((s) => s.trim()).filter(Boolean);
    else if (f.f === 'id') { c.id = v.trim(); S.ui.editCrit = c.id; el.closest('[data-crit]').dataset.crit = c.id; }
    else c[f.f] = v;
    if (f.f === 'title' || f.f === 'weight') { const item = $(`.list-item.on`); if (item) { item.querySelector('b').textContent = c.title; } }
  });
  document.addEventListener('change', async (e) => {
    const el = e.target, f = el.dataset;
    try {
      if (el.id === 'export-mode') { S.exportMeta.modelMode = el.value; return save(); }
      if (el.id === 'ds-select') { S.dataset = el.value; await loadConvs(); return render(); }
      if (el.id === 'cl-select') { const v = R.versions.find((x) => String(x.id) === el.value); if (v && !v.is_active) { await post(`/checklists/${v.id}/activate`); [R.versions, R.active] = await Promise.all([api('/checklists'), api('/checklists/active')]); render(); toast(`Активна v${v.version}. Нажмите «Применить активный чек-лист», чтобы перенести оценки`); } return; }
      if (el.id === 'eval-select') { await openCard(R.conv.id, +el.value); return render(); }
      if (f.f === 'type' || f.f === 'na_allowed' || f.f === 'weight') {
        const c = draft.criteria.find((q) => q.id === el.closest('[data-crit]').dataset.crit);
        if (f.f === 'type') {
          if (c.type === 'scale' && !(c.scale || []).length) c.scale = [{ value: 10, description: 'Полностью' }, { value: 5, description: 'Частично' }, { value: 0, description: 'Нет' }];
          if (c.type === 'flag') { c.weight = 0; c.na_allowed = false; if (!(c.flag_types || []).length) c.flag_types = []; }
        }
        return render();
      }
      if (el.id === 'file-in' && el.files[0]) {
        const fd = new FormData(); fd.append('file', el.files[0]);
        toast('Загружаю файл…'); el.value = '';
        return afterImport(await api('/datasets/upload', { method: 'POST', body: fd }));
      }
    } catch (err) { toast('Ошибка: ' + err.message); render(); }
  });

  render();
  loadBase().then(async () => {
    if (S.ui.view === 'card' && S.ui.cardId) { try { await openCard(S.ui.cardId); } catch (e) { S.ui.cardId = null; } }
    if (S.ui.view === 'appeals' || S.ui.view === 'analytics') return go(S.ui.view);
    render();
  });
})();
