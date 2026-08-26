const $ = (id) => document.getElementById(id);
const BASE = window.LUMI_API || "";
const PROMO_SESSION = "lumi_promo";

async function api(path, opts = {}) {
  let r;
  try {
    r = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
  } catch (e) {
    throw new Error("Бэкенд недоступен. Попробуйте позже.");
  }
  if (r.status === 401) {
    window.location.href = "https://lumi-panel.onrender.com/auth/login";
    throw new Error("unauthorized");
  }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

async function updatePromo() {
  const code = $("promo").value.trim();
  if (!code) {
    $("promoHint").textContent = "";
    sessionStorage.removeItem(PROMO_SESSION);
    return;
  }
  try {
    const p = await api("/api/promo/" + encodeURIComponent(code));
    sessionStorage.setItem(PROMO_SESSION, JSON.stringify(p));
    $("promoHint").textContent = "✓ скидка −" + p.percent + "%";
  } catch (e) {
    sessionStorage.removeItem(PROMO_SESSION);
    $("promoHint").textContent = "✕ не подходит";
  }
}

$("promoBtn").onclick = updatePromo;
$("promo").addEventListener("keydown", (e) => { if (e.key === "Enter") updatePromo(); });
$("promo").addEventListener("input", () => $("promoHint").textContent = "");

document.querySelectorAll(".btn-buy").forEach((btn) => {
  btn.onclick = async () => {
    const months = parseInt(btn.dataset.months, 10);
    const promo = JSON.parse(sessionStorage.getItem(PROMO_SESSION) || "null");
    btn.disabled = true;
    btn.textContent = "⏳ Переход к оплате...";
    try {
      const res = await api("/api/premium/buy", {
        method: "POST",
        body: JSON.stringify({ months, promo: promo ? promo.code : null }),
      });
      if (res.url) {
        window.location.href = res.url;
      }
    } catch (e) {
      alert("Ошибка: " + e.message);
      btn.disabled = false;
      btn.textContent = "Купить";
    }
  };
});
