/* Suara panggilan: bunyi "ting-tung" + ucapan. Browser dulu (bila ada suara Indonesia), cadangan suara dari server. */
window.Suara = (() => {
  let ctx = null, idVoice = null, rantai = Promise.resolve();
  const adaTTS = 'speechSynthesis' in window;
  function muatVoice() {
    if (!adaTTS) return;
    const v = speechSynthesis.getVoices();
    idVoice = v.find(x => /^id([-_]|$)/i.test(x.lang)) || v.find(x => /indones/i.test(x.name)) || null;
  }
  if (adaTTS) { muatVoice(); speechSynthesis.addEventListener('voiceschanged', muatVoice); }

  /* WAJIB dipanggil langsung dari klik/ketuk pengguna agar browser mengizinkan suara */
  function buka() {
    try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); ctx.resume(); } catch (e) {}
    try { if (adaTTS) { const u = new SpeechSynthesisUtterance(' '); u.volume = 0; speechSynthesis.speak(u); } } catch (e) {}
  }
  /* true bila browser sudah mengizinkan suara tanpa klik (mis. Chrome kiosk --autoplay-policy=no-user-gesture-required) */
  function otomatis() {
    try { const c = new (window.AudioContext || window.webkitAudioContext)(); const ok = c.state === 'running'; if (ok) ctx = c; else c.close(); return ok; } catch (e) { return false; }
  }
  function chime() {
    return new Promise(res => {
      if (!ctx) return res();
      const t = ctx.currentTime;
      [[880, 0], [659, .4]].forEach(([f, d]) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'sine'; o.frequency.value = f;
        g.gain.setValueAtTime(.0001, t + d); g.gain.exponentialRampToValueAtTime(.55, t + d + .03); g.gain.exponentialRampToValueAtTime(.0001, t + d + 1);
        o.connect(g); g.connect(ctx.destination); o.start(t + d); o.stop(t + d + 1.05);
      });
      setTimeout(res, 1150);
    });
  }
  function ucapBrowser(teks) {
    return new Promise(res => {
      const u = new SpeechSynthesisUtterance(teks); u.lang = 'id-ID'; u.rate = .9; if (idVoice) u.voice = idVoice;
      u.onend = res; u.onerror = res; speechSynthesis.cancel(); speechSynthesis.speak(u); setTimeout(res, 15000);
    });
  }
  function ucapServer(nomor, meja) {
    return new Promise(res => {
      const a = new Audio('/api/suara?nomor=' + nomor + '&meja=' + meja);
      a.onended = res; a.onerror = res; a.play().catch(res); setTimeout(res, 20000);
    });
  }
  /* item: {teks, nomor, meja}. Panggilan diantrikan agar tidak saling menimpa. */
  function panggil(item, engine) {
    rantai = rantai.then(async () => {
      await chime();
      if (engine === 'server' || (engine !== 'browser' && !(idVoice && adaTTS))) return ucapServer(item.nomor, item.meja);
      return ucapBrowser(item.teks);
    }).catch(() => {});
    return rantai;
  }
  return {buka, otomatis, panggil, get adaSuaraId() { return !!idVoice; }};
})();
