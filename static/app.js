const FIELDS = ["first", "last", "title", "org", "phone", "phone_home", "email",
  "website", "note", "street", "city", "region", "postal", "country", "photo_url"];

const state = {
  theme: "indigo",
  logo: null,
  tab: "styled",
  images: {},
  payload: "",
  platforms: [],
};

const $ = (id) => document.getElementById(id);

function collectContact() {
  const data = {};
  for (const f of FIELDS) data[f] = $(f) ? $(f).value.trim() : "";
  const social = {};
  document.querySelectorAll(".social-row").forEach((row) => {
    const platform = row.querySelector("select").value;
    const handle = row.querySelector("input").value.trim();
    if (!handle) return;
    if (platform === "custom") {
      const m = handle.match(/^(?:([\w-]+):)?(.*$)/);
      social[m[1] || "custom"] = m[2] || handle;
    } else {
      social[platform] = handle;
    }
  });
  data.social = social;
  data.theme = state.theme;
  data.social_note = $("social_note").checked;
  data.center_badge = $("center_badge").checked;
  if (state.logo) data.logo = state.logo;
  return data;
}

function addSocialRow(platform = "twitter", handle = "") {
  const row = document.createElement("div");
  row.className = "social-row";
  const sel = document.createElement("select");
  for (const p of state.platforms) {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    sel.appendChild(opt);
  }
  sel.value = platform;
  const inp = document.createElement("input");
  inp.placeholder = "handle or full URL";
  inp.value = handle;
  const btn = document.createElement("button");
  btn.className = "remove";
  btn.type = "button";
  btn.textContent = "×";
  btn.addEventListener("click", () => { row.remove(); schedule(); });
  row.append(sel, inp, btn);
  $("socials").appendChild(row);
}

function renderThemes(themes) {
  const wrap = $("themes");
  wrap.innerHTML = "";
  for (const [name, t] of Object.entries(themes)) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "theme-swatch" + (name === state.theme ? " active" : "");
    b.style.background = `linear-gradient(135deg, ${t.fg[0]}, ${t.fg[1]})`;
    const tag = document.createElement("span");
    tag.textContent = name;
    b.appendChild(tag);
    b.addEventListener("click", () => {
      state.theme = name;
      renderThemes(themes);
      schedule();
    });
    wrap.appendChild(b);
  }
}

let timer = null;
function schedule() {
  $("spinner").hidden = false;
  $("preview").classList.add("dim");
  clearTimeout(timer);
  timer = setTimeout(generate, 400);
}

async function generate() {
  const data = collectContact();
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const json = await res.json();
    if (!res.ok) { flashError(json.error || "generation failed"); return; }
    state.images = json.images;
    state.payload = json.payload;
    $("preview").src = json.images[state.tab];
    $("preview").classList.remove("dim");
    $("spinner").hidden = true;
    $("chip-bytes").textContent = `${json.bytes} B`;
    $("chip-version").textContent = `QR v${json.version} · ${json.modules}×${json.modules}`;
    $("chip-verify").hidden = !json.verified[state.tab];
    $("chip-dense").hidden = json.version <= 20;
    $("payload").textContent = json.payload.replace(/\r\n/g, "\n");
  } catch (err) {
    flashError(String(err));
  }
}

function flashError(msg) {
  $("spinner").hidden = true;
  $("preview").classList.remove("dim");
  $("chip-verify").hidden = false;
  $("chip-verify").textContent = "error";
  console.error(msg);
}

function download(name, href) {
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  a.click();
}

async function init() {
  const meta = await fetch("/api/meta").then((r) => r.json());
  state.platforms = meta.platforms;
  renderThemes(meta.themes);
  addSocialRow("twitter", "alexmorgan");
  addSocialRow("instagram", "alex.builds");
  addSocialRow("linkedin", "alexmorgan");

  for (const f of FIELDS) {
    const el = $(f);
    if (el) el.addEventListener("input", schedule);
  }
  for (const id of ["social_note", "center_badge"]) $(id).addEventListener("input", schedule);
  $("add-social").addEventListener("click", () => { addSocialRow(); schedule(); });
  $("socials").addEventListener("input", schedule);

  $("logo").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) { state.logo = null; schedule(); return; }
    const reader = new FileReader();
    reader.onload = () => { state.logo = reader.result; schedule(); };
    reader.readAsDataURL(file);
  });

  $("tabs").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    state.tab = btn.dataset.tab;
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === btn));
    if (state.images[state.tab]) $("preview").src = state.images[state.tab];
  });

  $("dl-png").addEventListener("click", () =>
    download(`vcard_qr_${state.tab}.png`, state.images[state.tab]));
  $("dl-vcf").addEventListener("click", () =>
    download("vcard.vcf", URL.createObjectURL(new Blob([state.payload], { type: "text/vcard" }))));
  $("dl-txt").addEventListener("click", () =>
    download("vcard.txt", URL.createObjectURL(new Blob([state.payload], { type: "text/plain" }))));

  schedule();
}

init();
