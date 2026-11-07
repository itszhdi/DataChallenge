/* Демо-записи в формате API организаторов (data.records). Замените загрузкой DEV. */
window.DEMO_RECORDS = [
  { conversation_id: 'demo-ru-001', channel: 'agent chat', language: 'RU', audio_url: null, transcript: [
    { timestamp: '00:02', speaker: 'system', text: 'Клиент подключился к чату' },
    { timestamp: '00:05', speaker: 'client', text: 'Подскажите, какие тарифы на SWIFT-переводы?' },
    { timestamp: '00:41', speaker: 'operator', text: 'Здравствуйте! Меня зовут Айдар, Фридом Банк. Какой именно перевод интересует — в долларах или евро?' },
    { timestamp: '01:02', speaker: 'client', text: 'В долларах, до 1000.' },
    { timestamp: '01:30', speaker: 'operator', text: 'Комиссия за SWIFT-перевод в USD составляет 0,5% от суммы, минимум 15 USD. Это актуально для переводов физических лиц.' },
    { timestamp: '01:48', speaker: 'client', text: 'Понятно, спасибо.' },
    { timestamp: '02:00', speaker: 'operator', text: 'Могу ещё чем-то помочь? Хорошего дня, до свидания!' } ] },
  { conversation_id: 'demo-ru-002', channel: 'agent chat', language: 'RU', audio_url: null, transcript: [
    { timestamp: '00:03', speaker: 'bot', text: 'Здравствуйте! Соединяю вас с оператором.' },
    { timestamp: '00:20', speaker: 'client', text: 'Хочу узнать остаток на моей карте.' },
    { timestamp: '00:50', speaker: 'operator', text: 'Добрый день! Остаток на вашей карте — 184 500 тенге.' },
    { timestamp: '01:05', speaker: 'client', text: 'Хорошо, а лимит на снятие какой?' },
    { timestamp: '01:25', speaker: 'operator', text: 'Суточный лимит 500 000 тенге.' } ] },
  { conversation_id: 'demo-kz-003', channel: 'agent chat', language: 'KZ', audio_url: null, transcript: [
    { timestamp: '00:04', speaker: 'client', text: 'Картам жұмыс істемей тұр, өте жаман қызмет! Үшінші рет жазып отырмын.' },
    { timestamp: '00:30', speaker: 'operator', text: 'Сәлеметсіз бе! Менің атым Нұрлан. Ыңғайсыздық үшін кешірім сұраймын, картаңыздың бұғатталуын қазір тексеремін.' },
    { timestamp: '01:10', speaker: 'operator', text: 'Картаны бұғаттан шығардым, қазір төлем жасап көріңіз.' },
    { timestamp: '01:40', speaker: 'client', text: 'Жұмыс істеді, рахмет.' } ] },
  { conversation_id: 'demo-en-004', channel: 'agent chat', language: 'EN', audio_url: null, transcript: [
    { timestamp: '00:03', speaker: 'client', text: 'Hi, I want to invest 5000 USD, what do you recommend?' },
    { timestamp: '00:35', speaker: 'operator', text: 'Hello! I am Daniel from Freedom. For a better result, send me your personal number and I can give you a private consultation.' },
    { timestamp: '01:00', speaker: 'client', text: 'Hmm, is that allowed?' },
    { timestamp: '01:20', speaker: 'operator', text: 'Sure, or transfer the money to me and I will invest it for you. Thank you, goodbye!' } ] },
  { conversation_id: 'demo-voice-005', channel: 'voice call', language: 'RU', audio_url: 'https://example.com/recording-demo.mp3', transcript: [
    { timestamp: '2026-11-06T10:15:02+05:00', speaker: 'operator', text: 'Фридом Банк, добрый день, меня зовут Мария. Чем могу помочь?' },
    { timestamp: '2026-11-06T10:15:10+05:00', speaker: 'client', text: 'Здравствуйте, хочу заблокировать карту, потерял.' },
    { timestamp: '2026-11-06T10:15:22+05:00', speaker: 'operator', text: 'Назовите, пожалуйста, ИИН и кодовое слово для подтверждения личности.' },
    { timestamp: '2026-11-06T10:15:40+05:00', speaker: 'client', text: 'ИИН назвал, кодовое слово — «Алатау».' },
    { timestamp: '2026-11-06T10:16:05+05:00', speaker: 'operator', text: 'Спасибо, карта заблокирована. Могу ещё чем-то помочь? Всего доброго, до свидания!' } ] }
];
