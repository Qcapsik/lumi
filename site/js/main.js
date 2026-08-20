// Lumi — статический сайт бота
// Вставь сюда ссылку приглашения бота из Discord Developer Portal (OAuth2 URL Generator):
const INVITE_URL = "https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot";

const $ = (s) => document.querySelector(s);

function bindInvite() {
  document.querySelectorAll("#inviteBtn, #inviteBtn2").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      if (INVITE_URL.includes("YOUR_CLIENT_ID")) {
        alert("Ссылка ещё не настроена: замени client_id в site/js/main.js");
        return;
      }
      window.open(INVITE_URL, "_blank");
    });
  });
}

function bindActivate() {
  const btn = $("#activateBtn");
  const input = $("#code");
  const hint = $("#hint");
  if (!btn || !input || !hint) return;
  btn.addEventListener("click", handle);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") handle(); });
  function handle() {
    const code = input.value.trim().toUpperCase();
    if (!code) {
      hint.className = "hint err";
      hint.textContent = "Введи код лицензии.";
      return;
    }
    if (!/^LU-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code)) {
      hint.className = "hint err";
      hint.textContent = "Формат кода: LU-XXXX-XXXX";
      return;
    }
    hint.className = "hint ok";
    hint.textContent = "Код принят! Теперь активируй его в Discord:  !активировать " + code;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindInvite();
  bindActivate();
});