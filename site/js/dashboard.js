const $ = (id) => document.getElementById(id);
const BASE = window.LUMI_API || "";
let currentGuild = null;
let assets = { channels: [], roles: [] };

const iconUrl = (gid, hash) =>
  hash ? `https://cdn.discordapp.com/icons/${gid}/${hash}.png?size=64` : null;

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
    window.location.href = "https://lumi-panel.onrender.com/auth/login";
    throw new Error("unauthorized");
  }
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function init() {
  const params = new URLSearchParams(location.search);
  if (params.get("error") === "oauth") {
    $("loginError").hidden = false;
      $("loginError").textContent =
      "Не удалось войти. Проверьте Redirect URL в Discord Developer Portal.";
  }
  try {
    const me = await api("/api/me");
    $("logoutBtn").hidden = false;
    $("loginScreen").hidden = true;
    $("panelScreen").hidden = false;
    const servers = await api("/api/servers");
    renderServers(servers);
    if (servers.length) selectGuild(servers[0].id);
    else $("serverName").textContent = "Бот не добавлен ни на один ваш сервер";
  } catch (e) {
    if (e.message === "unauthorized") return;
    if (e.message === "backend-offline") {
      $("loginError").hidden = false;
      $("loginError").textContent =
        "Бэкенд сайта недоступен. Попробуйте позже или подключите сервер вручную через Discord.";
      return;
    }
    $("loginScreen").hidden = false;
    $("loginError").hidden = false;
    $("loginError").textContent = "Ошибка загрузки: " + e.message;
  }
}

function renderServers(servers) {
  const list = $("serversList");
  list.innerHTML = "";
  servers.forEach((s) => {
    const btn = document.createElement("button");
    btn.className = "server";
    btn.dataset.gid = s.id;
    const img = iconUrl(s.id, s.icon);
    btn.innerHTML =
      (img ? `<img src="${img}" alt="">` : `<span class="server__ph">${s.name[0]}</span>`) +
      `<span class="server__name">${esc(s.name)}</span>`;
    btn.onclick = () => selectGuild(s.id);
    list.appendChild(btn);
  });
}

function markActive(gid) {
  document.querySelectorAll(".server").forEach((b) =>
    b.classList.toggle("active", b.dataset.gid == gid)
  );
}

async function selectGuild(gid) {
  currentGuild = gid;
  markActive(gid);
  $("serverName").textContent = "";
  $("serverId").textContent = "ID: " + gid;
  $("saveBtn").hidden = true;
  const [cfg, as] = await Promise.all([
    api(`/api/server/${gid}`),
    api(`/api/server/${gid}/assets`),
  ]);
  assets = as;
  const g = document.querySelector(".server[data-gid='" + gid + "']");
  if (g) $("serverName").textContent = g.querySelector(".server__name").textContent;

  $("wWelcome").checked = cfg.welcome.enabled;
  $("wCard").checked = cfg.welcome.card_enabled;
  $("wRules").value = cfg.welcome.rules_text || "";
  fillSelect($("wChannel"), as.channels, cfg.welcome.channel_id, "— канал не выбран —");
  fillSelect($("wGuestRole"), as.roles, cfg.welcome.guest_role_id, "— без роли —");

  $("levelRoleRows").innerHTML = "";
  cfg.level_roles.forEach((r) => addLevelRoleRow(r.level, r.role_id));
  $("saveBtn").hidden = false;
}

function fillSelect(sel, items, selected, placeholder) {
  sel.innerHTML = "";
  if (placeholder) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    sel.appendChild(opt);
  }
  items.forEach((i) => {
    const opt = document.createElement("option");
    opt.value = i.id;
    opt.textContent = "#" + i.name + " — " + i.id;
    opt.selected = i.id == selected;
    sel.appendChild(opt);
  });
}

function addLevelRoleRow(level = "", roleId = "") {
  const wrap = document.createElement("div");
  wrap.className = "row";
  const lvl = document.createElement("input");
  lvl.type = "number";
  lvl.className = "col col--lvl";
  lvl.min = 1;
  lvl.max = 100;
  lvl.value = level;
  lvl.placeholder = "5";
  const role = document.createElement("select");
  role.className = "col col--role";
  const ph = document.createElement("option");
  ph.value = "";
  ph.textContent = "— выбрать роль —";
  role.appendChild(ph);
  assets.roles.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = "@" + r.name;
    opt.selected = r.id == roleId;
    role.appendChild(opt);
  });
  const del = document.createElement("button");
  del.className = "col col--del btn btn--ghost";
  del.textContent = "✕";
  del.onclick = () => wrap.remove();
  wrap.append(lvl, role, del);
  $("levelRoleRows").appendChild(wrap);
}

document.addEventListener("click", (e) => {
  if (e.target.closest(".tab")) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    e.target.closest(".tab").classList.add("active");
    document.querySelectorAll(".tabpage").forEach((p) => p.classList.remove("active"));
    $("tab-" + e.target.closest(".tab").dataset.tab).classList.add("active");
  }
});
$("addRoleRow").onclick = () => addLevelRoleRow();

$("saveBtn").onclick = async () => {
  const roles = [];
  document.querySelectorAll("#levelRoleRows .row").forEach((row) => {
    const lvl = parseInt(row.querySelector("input").value, 10);
    const rid = parseInt(row.querySelector("select").value, 10);
    if (lvl >= 1 && lvl <= 100 && rid > 0) roles.push({ level: lvl, role_id: rid });
  });
  const body = {
    welcome: {
      enabled: $("wWelcome").checked,
      card_enabled: $("wCard").checked,
      channel_id: $("wChannel").value || null,
      guest_role_id: $("wGuestRole").value || null,
      rules_text: $("wRules").value.trim() || null,
    },
    level_roles: roles,
  };
  try {
    await api(`/api/server/${currentGuild}/save`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    toast("✅ Сохранено");
  } catch (e) {
    toast("❌ Ошибка: " + e.message);
  }
};

let toastTimer = null;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3000);
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

init();
