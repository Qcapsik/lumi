const $ = (id) => document.getElementById(id);
const BASE = window.LUMI_API || "";
const PROMO_SESSION = "lumi_promo";
const KEYS_STORAGE = "lumi_keys";

function generateKey() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const seg = () => {
    let s = "";
    for (let i = 0; i < 4; i++) s += chars[Math.floor(Math.random() * chars.length)];
    return s;
  };
  return "LU-" + seg() + "-" + seg();
}

function getLocalKeys() {
  try { return JSON.parse(localStorage.getItem(KEYS_STORAGE) || "[]"); }
  catch { return []; }
}

function saveLocalKey(key) {
  const keys = getLocalKeys();
  keys.unshift(key);
  localStorage.setItem(KEYS_STORAGE, JSON.stringify(keys));
}

async function api(path, opts = {}) {
  let r;
  try {
    r = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
  } catch (e) {
    return null;
  }
  if (r.status === 401) return null;
  if (!r.ok) return null;
  return r.json();
}

async function updatePromo() {
  const code = $("promo").value.trim();
  if (!code) {
    $("promoHint").textContent = "";
    sessionStorage.removeItem(PROMO_SESSION);
    return;
  }
  const p = await api("/api/promo/" + encodeURIComponent(code));
  if (p && p.percent) {
    sessionStorage.setItem(PROMO_SESSION, JSON.stringify(p));
    $("promoHint").textContent = "✓ скидка −" + p.percent + "%";
  } else {
    sessionStorage.removeItem(PROMO_SESSION);
    $("promoHint").textContent = "✕ не подходит";
  }
}

$("promoBtn").onclick = updatePromo;
$("promo").addEventListener("keydown", (e) => { if (e.key === "Enter") updatePromo(); });
$("promo").addEventListener("input", () => $("promoHint").textContent = "");

let pending = null;

document.querySelectorAll(".btn-buy").forEach((btn) => {
  btn.onclick = async () => {
    const months = parseInt(btn.dataset.months, 10);
    let price = months === 1 ? 7.99 : 14.99;
    let discount = 0;
    const plans = await api("/api/premium/plans");
    if (plans) {
      const plan = plans.find((p) => p.months === months);
      if (plan) price = plan.price;
    }
    const promo = JSON.parse(sessionStorage.getItem(PROMO_SESSION) || "null");
    if (promo) discount = (price * promo.percent / 100).toFixed(2);
    const total = (price - discount).toFixed(2);
    $("payTitle").textContent = months === 1 ? "1 месяц — $" + price : "3 месяца — $" + price;
    $("paySummary").innerHTML =
      (discount > 0 ? "Скидка: <b>−$" + discount + "</b> · " : "") + "Итого: <b>$" + total + "</b>";
    pending = { months, promo: promo ? promo.code : null, price, discount, total };
    $("payModal").hidden = false;
  };
});

$("payCancel").onclick = () => { $("payModal").hidden = true; pending = null; };

$("payConfirm").onclick = async () => {
  $("payConfirm").disabled = true;
  $("payConfirm").textContent = "⏳ Генерация ключа...";
  try {
    let res = null;
    if (BASE) {
      res = await api("/api/premium/buy", {
        method: "POST",
        body: JSON.stringify({ months: pending.months, promo: pending.promo }),
      });
    }
    if (!res || !res.license) {
      const key = generateKey();
      res = {
        license: key,
        months: pending.months,
        amount: pending.total || pending.price,
        promo: pending.promo || null,
        activated: false,
        purchased_at: new Date().toISOString(),
      };
      saveLocalKey({
        license: key,
        months: pending.months,
        amount: pending.total || pending.price,
        promo: pending.promo || null,
        activated: false,
        purchased_at: res.purchased_at,
      });
    }
    $("payModal").hidden = true;
    $("okLicense").textContent = res.license;
    $("okModal").hidden = false;
    sessionStorage.removeItem(PROMO_SESSION);
    $("promo").value = "";
    $("promoHint").textContent = "";
  } catch (e) {
    alert("Ошибка: " + e.message);
  } finally {
    $("payConfirm").disabled = false;
    $("payConfirm").textContent = "✅ Оплатить (демо)";
    pending = null;
  }
};

$("okClose").onclick = () => { $("okModal").hidden = true; };

window.addEventListener("click", (e) => {
  if (e.target.classList && e.target.classList.contains("modal")) e.target.hidden = true;
});
