// Original, deterministic vector fixtures. Not model output or user uploads.
// No remote resources, fonts, scripts, or user text inside the SVG.
const palettes = [
  ['#eed9cb', '#e89775', '#bb5b42', '#ead6b5', '#536f70'],
  ['#dae6e4', '#8bb5ad', '#397b77', '#e9dfc8', '#476275'],
  ['#e7dcf0', '#b79ac6', '#715e91', '#f5d6ac', '#60687d'],
  ['#e9e2cf', '#cfb36a', '#a17241', '#f8e7be', '#6c8b83'],
]
export function artUrl(index = 0): string {
  const [sky, wall, shadow, light, water] = palettes[index % palettes.length]!
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1440" viewBox="0 0 1440 1440"><defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="${sky}"/><stop offset="1" stop-color="${light}"/></linearGradient><linearGradient id="sea" x2="0" y2="1"><stop stop-color="${water}"/><stop offset="1" stop-color="${sky}"/></linearGradient><linearGradient id="wall"><stop stop-color="${wall}"/><stop offset=".8" stop-color="${light}"/></linearGradient><linearGradient id="floor" x2="1" y2="1"><stop stop-color="${light}"/><stop offset="1" stop-color="${wall}"/></linearGradient></defs><path fill="url(#sky)" d="M0 0h1440v1440H0z"/><circle cx="1030" cy="310" r="155" fill="${light}"/><path fill="${water}" opacity=".22" d="M0 720Q330 615 620 715T1440 650V1000H0z"/><path fill="url(#sea)" d="M0 820h1440v620H0z"/><path fill="url(#floor)" d="M0 1170 925 935l515 195v310H0z"/><path fill="${shadow}" opacity=".18" d="m388 1070 475-32 414 278-391 84z"/><path fill="${shadow}" d="M385 1075V535a295 295 0 0 1 590 0v445l-110 40V535a185 185 0 0 0-370 0v508z"/><path fill="url(#wall)" fill-rule="evenodd" d="M275 1110V525a295 295 0 0 1 590 0v495l-95 35V525a200 200 0 0 0-400 0v550z"/><path fill="${shadow}" opacity=".1" d="M770 525h95v495l-95 35z"/><ellipse cx="1110" cy="1088" rx="112" ry="24" fill="${shadow}" opacity=".18"/><circle cx="1110" cy="1000" r="97" fill="url(#wall)"/><g fill="none" stroke="${light}" opacity=".3" stroke-width="2"><path d="M0 885h270m590 0h580M0 910h200m665 0h490M0 945h260m605 0h575M60 980h190m740 0h410M0 1020h270"/></g></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}
