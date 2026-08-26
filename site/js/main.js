const INVITE_URL = "https://discord.com/oauth2/authorize?client_id=1477472028414967858&permissions=8&scope=bot%20applications.commands";

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

function initParticles() {
  const container = document.getElementById("particles");
  if (!container) return;
  for (let i = 0; i < 40; i++) {
    const dot = document.createElement("div");
    const size = Math.random() * 3 + 1;
    dot.style.cssText =
      "position:absolute;border-radius:50%;pointer-events:none;" +
      "width:" + size + "px;height:" + size + "px;" +
      "left:" + (Math.random() * 100) + "%;" +
      "top:" + (Math.random() * 100) + "%;" +
      "background:" + (Math.random() > 0.5 ? "rgba(255,215,0,0.4)" : "rgba(139,92,246,0.4)") + ";" +
      "animation:float " + (Math.random() * 6 + 4) + "s ease-in-out infinite;" +
      "animation-delay:" + (Math.random() * 4) + "s;";
    container.appendChild(dot);
  }
  const style = document.createElement("style");
  style.textContent = "@keyframes float{0%,100%{transform:translateY(0) scale(1);opacity:.4}50%{transform:translateY(-20px) scale(1.3);opacity:.8}}";
  document.head.appendChild(style);
}

document.addEventListener("DOMContentLoaded", () => {
  bindInvite();
  initParticles();
});
