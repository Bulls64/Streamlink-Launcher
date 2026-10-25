// make_assets.mjs : icônes PNG et images de partage (Open Graph) pour la version GitHub Pages
import { chromium } from 'playwright';
import fs from 'fs';
const here = process.cwd();
const F = 'node_modules/@fontsource';
const b = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
const svg = fs.readFileSync('gh_assets/icons/icon.svg', 'utf8');
// ONLY=home-es,docs-es… : ne refait que ces images de partage (les icônes sont gardées telles quelles)
const ONLY = process.env.ONLY ? process.env.ONLY.split(',') : null;
for (const [name, size, pad] of ONLY ? [] : [['icon-512', 512, 0], ['icon-192', 192, 0], ['apple-touch-icon', 180, 0], ['icon-32', 32, 0], ['icon-16', 16, 0]]) {
  const p = await b.newPage({ viewport: { width: size, height: size } });
  // l'icône Apple n'a pas de transparence : fond plein, coins arrondis par iOS
  const html = name === 'apple-touch-icon'
    ? `<body style="margin:0;background:#9146FF">${svg.replace('rx="8"', 'rx="0"').replace('<svg ', `<svg width="${size}" height="${size}" `)}</body>`
    : `<body style="margin:0;background:transparent">${svg.replace('<svg ', `<svg width="${size}" height="${size}" `)}</body>`;
  await p.setContent(html);
  await p.screenshot({ path: `gh_assets/icons/${name}.png`, omitBackground: name !== 'apple-touch-icon' });
  await p.close();
}
const font = (fam, file, w, st = 'normal') => `@font-face{font-family:"${fam}";font-weight:${w};font-style:${st};src:url("file://${here}/${F}/${file}")}`;
const css = [
  font('Big Shoulders Display', 'big-shoulders-display/files/big-shoulders-display-latin-900-normal.woff2', 900),
  font('Instrument Sans', 'instrument-sans/files/instrument-sans-latin-500-normal.woff2', 500),
  font('Instrument Sans', 'instrument-sans/files/instrument-sans-latin-700-normal.woff2', 700),
  font('IBM Plex Mono', 'ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff2', 500),
].join('\n');
const T = {
  'home-fr': { tag: 'Deux applis libres · Windows et Linux', h: 'Le live sort<br>du <em>navigateur.</em>', p: 'Twitch, Kick, YouTube et Steam TV dans VLC, mpv ou PotPlayer, et les chats dans une fenêtre à part.' },
  'home-en': { tag: 'Two free apps · Windows and Linux', h: 'Live, minus<br>the <em>browser.</em>', p: 'Twitch, Kick, YouTube and Steam TV in VLC, mpv or PotPlayer, with the chats in a separate window.' },
  'docs-fr': { tag: 'Docs · Launcher 1.5 · Chat 0.2', h: 'La doc<br><em>complète.</em>', p: 'Installer Streamlink, premier stream, chat Twitch et Kick, raccourcis, réglages, dépannage.' },
  'docs-en': { tag: 'Docs · Launcher 1.5 · Chat 0.2', h: 'The full<br><em>guide.</em>', p: 'Install Streamlink, first stream, Twitch and Kick chat, shortcuts, settings, troubleshooting.' },
  'home-es': { tag: 'Dos aplicaciones libres · Windows y Linux', h: 'El directo,<br>fuera del <em>navegador.</em>', p: 'Twitch, Kick, YouTube y Steam TV en VLC, mpv o PotPlayer, con los chats en otra ventana.' },
  'home-de': { tag: 'Zwei freie Apps · Windows und Linux', h: 'Live, aber<br>ohne <em>Browser.</em>', p: 'Twitch, Kick, YouTube und Steam TV in VLC, mpv oder PotPlayer, mit den Chats in einem eigenen Fenster.' },
  'home-it': { tag: 'Due app libere · Windows e Linux', h: 'Il live esce<br>dal <em>browser.</em>', p: 'Twitch, Kick, YouTube e Steam TV in VLC, mpv o PotPlayer, con le chat in una finestra a parte.' },
  'docs-es': { tag: 'Docs · Launcher 1.5 · Chat 0.2', h: 'La guía<br><em>completa.</em>', p: 'Instalar Streamlink, primer stream, chat de Twitch y Kick, atajos, ajustes, solución de problemas.' },
  'docs-de': { tag: 'Docs · Launcher 1.5 · Chat 0.2', h: 'Das ganze<br><em>Handbuch.</em>', p: 'Streamlink installieren, erster Stream, Twitch- und Kick-Chat, Tastenkürzel, Einstellungen, Fehlerbehebung.' },
  'docs-it': { tag: 'Docs · Launcher 1.5 · Chat 0.2', h: 'La guida<br><em>completa.</em>', p: 'Installare Streamlink, primo stream, chat di Twitch e Kick, scorciatoie, impostazioni, risoluzione dei problemi.' },
};
for (const [key, t] of Object.entries(T)) {
  if (ONLY && !ONLY.includes(key)) continue;
  const lang = key.slice(-2);
  const dir = lang === 'fr' ? 'fr' : 'en';   // es, de, it : mêmes captures que l'anglais
  const img = n => `file://${here}/img/site/${dir}/${n}.webp`;
  const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
  fs.writeFileSync('gh_assets/_og.html', `<!doctype html><html><head><style>${css}
    *{box-sizing:border-box} body{margin:0;width:1200px;height:630px;overflow:hidden;background:#0F1116;color:#ECEEF3;font-family:"Instrument Sans";position:relative}
    body::before{content:"";position:absolute;inset:0;background:radial-gradient(700px 420px at 92% 30%,rgba(145,70,255,.32),transparent 70%)}
    .brand{position:absolute;left:64px;top:56px;display:flex;align-items:center;gap:14px;font-weight:700;font-size:26px}
    .brand svg{width:44px;height:44px} .brand span{color:#959CAD;font-weight:500}
    .tag{position:absolute;left:64px;top:150px;font-family:"IBM Plex Mono";font-size:16px;letter-spacing:.12em;text-transform:uppercase;color:#959CAD;display:flex;gap:12px;align-items:center}
    .tag i{width:12px;height:12px;border-radius:50%;background:#EB0400;box-shadow:0 0 0 5px rgba(235,4,0,.22)}
    h1{position:absolute;left:60px;top:186px;margin:0;font-family:"Big Shoulders Display";font-weight:900;font-size:104px;line-height:.9;z-index:2;text-transform:uppercase;letter-spacing:-.005em}
    h1 em{font-style:normal;color:#B794FF}
    p{position:absolute;left:64px;top:440px;width:600px;margin:0;font-size:25px;line-height:1.4;color:#B9BFCC}
    .bar{position:absolute;left:0;right:0;bottom:0;height:8px;background:linear-gradient(90deg,#9146FF,#53FC18,#D91A1A,#66C0F4)}
    .shot{position:absolute;border-radius:14px;box-shadow:0 30px 80px rgba(0,0,0,.55),0 0 0 1px #2A2F3A}
    .s1{left:760px;top:120px;width:580px;transform:rotate(-3deg)}
    .s2{left:968px;top:262px;width:240px;transform:rotate(4deg)}
  </style></head><body>
    <div class="brand">${svg.replace('<svg ', '<svg ')}Streamlink Launcher <span>&amp; Chat</span></div>
    <div class="tag"><i></i>${t.tag}</div>
    <h1>${t.h}</h1><p>${t.p}</p>
    <img class="shot s1" src="${img('l_main')}"><img class="shot s2" src="${img('c_tw')}">
    <div class="bar"></div></body></html>`);
  await p.goto(`file://${here}/gh_assets/_og.html`); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
  await p.screenshot({ path: `gh_assets/og/${key}.jpg`, type: 'jpeg', quality: 88 });
  await p.close();
}
fs.unlinkSync('gh_assets/_og.html');
await b.close();
if (ONLY) process.exit(0);
// favicon.ico (16 et 32 px) à partir des PNG, sans dépendance supplémentaire : on l'assemble à la main
const png = n => fs.readFileSync(`gh_assets/icons/${n}.png`);
const imgs = [[16, png('icon-16')], [32, png('icon-32')]];
const head = Buffer.alloc(6); head.writeUInt16LE(1, 2); head.writeUInt16LE(imgs.length, 4);
let off = 6 + 16 * imgs.length; const dirs = [], datas = [];
for (const [sz, d] of imgs) { const e = Buffer.alloc(16); e[0] = sz; e[1] = sz; e.writeUInt16LE(1, 4); e.writeUInt16LE(32, 6); e.writeUInt32LE(d.length, 8); e.writeUInt32LE(off, 12); off += d.length; dirs.push(e); datas.push(d); }
fs.writeFileSync('gh_assets/favicon.ico', Buffer.concat([head, ...dirs, ...datas]));
for (const n of ['icon-16', 'icon-32']) fs.unlinkSync(`gh_assets/icons/${n}.png`);
