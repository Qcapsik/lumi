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
    throw new Error("backend-offline");
  }
  if (r.status === 401) {
    sessionStorage.setItem("lumi_redirect", location.pathname);
    window.location.href = (BASE || "") + "/auth/login";
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

let pending = null;

document.querySelectorAll(".btn-buy").forEach((btn) => {
  btn.onclick = async () => {
    const months = parseInt(btn.dataset.months, 10);
    let price = 7.99;
    let discount = 0;
    try {
      const plans = await api("/api/premium/plans");
      const plan = plans.find((p) => p.months === months);
      price = plan ? plan.price : price;
      const promo = JSON.parse(sessionStorage.getItem(PROMO_SESSION) || "null");
      if (promo) discount = (price * promo.percent / 100).toFixed(2);
    } catch (e) { /* показываем как есть */ }
    const total = (price - discount).toFixed(2);
    $("payTitle").textContent = months === 1 ? "1 месяц — $" + price : "3 месяца — $" + price;
    $("paySummary").innerHTML =
      (discount > 0 ? "Скидка: <b>−$" + discount + "</b> · " : "") + "Итого: <b>$" + total + "</b>";
    pending = { months, promo: (JSON.parse(sessionStorage.getItem(PROMO_SESSION) || "null") || {}).code || null };
    $("payModal").hidden = false;
  };
});

$("payCancel").onclick = () => { $("payModal").hidden = true; pending = null; };

$("payConfirm").onclick = async () => {
  $("payConfirm").disabled = true;
  const btn = $("payConfirm");
  btn.textContent = "⏳ Платёж...";
  try {
    const res = await api("/api/premium/buy", {
      method: "POST",
      body: JSON.stringify(pending),
    });
    $("payModal").hidden = true;
    $("okLicense").textContent = res.license;
    $("okModal").hidden = false;
    sessionStorage.removeItem(PROMO_SESSION);
    $("promo").value = "";
    $("promoHint").textContent = "";
  } catch (e) {
    alert("Ошибка: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "✅ Оплатить (демо)";
    pending = null;
  }
};

$("okClose").onclick = () => { $("okModal").hidden = true; };

window.addEventListener("click", (e) => {
  if (e.target.classList && e.target.classList.contains("modal")) e.target.hidden = true;
});
