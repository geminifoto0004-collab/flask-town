/* One language owner for history, native speech and generated actors. */
(() => {
  const cache = new Map(), pending = new Map(), failed = new Map();
  const han = /[\u3400-\u9fff]/;
  let timer = null, busy = false;
  function pair(turn) {
    const raw = String(turn?.text_es || turn?.text || turn?.message || '').trim();
    const zh = String(turn?.text_zh || turn?.textZh || turn?.translation_zh || '').trim();
    return {text: raw, text_zh: zh};
  }
  function usable(value, lang) {
    return !!value && (lang === 'es' ? !han.test(value) : han.test(value));
  }
  function language() { return window.__townUiPrefs?.dialogueLang === 'es' ? 'es' : 'zh'; }
  function text(turn, lang = language()) {
    const original = pair(turn), key = JSON.stringify(original);
    const translated = cache.get(key) || original;
    const candidate = lang === 'es' ? translated.text : translated.text_zh;
    if (usable(candidate, lang)) return candidate;
    // If DeepSeek supplied a line already written in the selected language,
    // keep that source line visible immediately. This is important for idioms
    // and exclamations such as 「造孽啊」: a missing/weak translation must not
    // replace a perfectly valid Chinese source with an empty bubble.
    const sourceInSelectedLanguage = lang === 'es'
      ? (usable(original.text, 'es') ? original.text : (usable(original.text_zh, 'es') ? original.text_zh : ''))
      : (usable(original.text_zh, 'zh') ? original.text_zh : (usable(original.text, 'zh') ? original.text : ''));
    if (sourceInSelectedLanguage) return sourceInSelectedLanguage;
    if (!original.text && !original.text_zh) return '';
    if ((failed.get(key) || 0) < Date.now()) {
      if(pending.size<80)pending.set(key, original);
      if (!timer && !busy) timer = setTimeout(flush, 100);
    }
    // Never present an untranslated source as the selected language.
    return lang === 'es' ? '[Traducción pendiente]' : '［翻譯待補］';
  }
  async function flush() {
    timer = null;
    if (busy || !pending.size) return;
    busy = true;
    const batch = [...pending.entries()].slice(0, 8);
    batch.forEach(([key]) => pending.delete(key));
    try {
      const response = await fetch('/api/town/translate-dialogue', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({turns:batch.map(([,value]) => value)})
      });
      if (!response.ok) throw new Error('translation unavailable');
      const data = await response.json();
      if (!Array.isArray(data.turns) || data.turns.length !== batch.length) throw new Error('incomplete translation');
      data.turns.forEach((turn, i) => {
        const value=pair(turn),key=batch[i][0];
        if(!usable(value.text,'es') || !usable(value.text_zh,'zh'))throw new Error('invalid language');
        cache.set(key,value);failed.delete(key);
      });
      while(cache.size>512)cache.delete(cache.keys().next().value);
      window.dispatchEvent(new Event('town-language-change'));
    } catch (_) {
      batch.forEach(([key]) => failed.set(key, Date.now()+60000));
      while(failed.size>512)failed.delete(failed.keys().next().value);
    } finally {
      busy=false;
      if(pending.size)timer=setTimeout(flush,1500);
    }
  }
  window.TownLanguage={text,language,pair};
})();
