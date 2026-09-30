/* Util bersama: toast dan pemanggil API */
window.toast = function (pesan, jenis) {
  let area = document.querySelector('.toast-area');
  if (!area) { area = document.createElement('div'); area.className = 'toast-area'; document.body.appendChild(area); }
  const t = document.createElement('div');
  t.className = 'toast-item ' + (jenis || ''); t.textContent = pesan; area.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .4s'; setTimeout(() => t.remove(), 400); }, 3800);
};
window.api = async function (url, opsi) {
  const r = await fetch(url, opsi);
  if (r.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); throw new Error('login'); }
  let data = null; try { data = await r.json(); } catch (e) {}
  if (!r.ok) { const e = new Error((data && (data.detail || data.pesan || (data.errors || []).join('; '))) || ('Kesalahan ' + r.status)); e.status = r.status; e.data = data; throw e; }
  return data;
};
window.esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
window.mmss = d => String(Math.floor(d / 60)).padStart(2, '0') + ':' + String(d % 60).padStart(2, '0');
