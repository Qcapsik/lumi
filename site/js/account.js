const $ = (id) => document.getElementById(id);
const BASE = window.LUMI_API || "";

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
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

function renderKeys(keys) {
  const list = $("keysList");
  list.innerHTML = "";
  keys.forEach((k) => {
    const el = document.createElement("div");
    el.className = "key";
    const hidden = "•••••" + k.license.slice(-8);
    el.innerHTML =
      '<span class="key-code" data-full="' + k.license + '">' + hidden + "</span>" +
      '<div class="key-meta">' +
        '<span class="badge ' + (k.activated ? "badge--ok" : "badge--wait") + '">' +
          (k.activated ? "активирован" : "ждёт активации") + "</span>" +
        "<span>" + k.months + " мес.</span>" +
        (k.promo ? "<span>промо −" + k.promo + "</span>" : "") +
        "<span>$" + k.amount + "</span>" +
        "<span>" + k.purchased_at.slice(0, 10) + "</span>" +
      "</div>" +
      '<button class="key-toggle" title="Показать">👁</button>';
    const codeEl = el.querySelector(".key-code");
    const toggle = el.querySelector(".key-toggle");
    let shown = false;
    toggle.onclick = () => {
      shown = !shown;
      codeEl.textContent = shown ? k.license : hidden;
      toggle.textContent = shown ? "🙈" : "👁";
    };
    list.appendChild(el);
  });
}

async function init() {
  const me = await api("/api/me");

  if (!me) {
    $("logoutBtn").hidden = true;
    $("whoami").textContent = "Войдите через Discord, чтобы видеть ключи и серверы.";
    $("loginCard").hidden = false;
    $("keysSection").hidden = true;
    return;
  }

  $("logoutBtn").hidden = false;
  $("loginCard").hidden = true;
  $("keysSection").hidden = false;

  $("whoami").textContent = "Вы вошли как @" + me.username;

  const welcome = new URLSearchParams(location.search).get("welcome") === "1";
  if (me.registered_at) {
    $("whoami").textContent += " · зарегистрирован " + me.registered_at.slice(0, 10);
  }
  if (welcome) {
    const banner = document.createElement("div");
    banner.style.cssText =
      "max-width:720px;margin:0 auto 20px;background:var(--card);border:1px solid var(--line);" +
      "border-radius:var(--radius);padding:16px 20px;color:var(--green);font-weight:600";
    banner.textContent = "🎉 Добро пожаловать! Аккаунт создан — это твой личный кабинет.";
    document.querySelector(".acct").insertBefore(banner, document.querySelector(".acct-card, #keysSection"));
  }

  const keys = await api("/api/account/keys") || [];
  if (!keys.length) {
    $("noKeys").hidden = false;
    return;
  }
  $("noKeys").hidden = true;
  renderKeys(keys);
}

init();
