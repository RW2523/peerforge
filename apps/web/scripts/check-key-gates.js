// Every place the UI decides whether generation is possible must consult
// hasKey (which includes the server's key), never apiKey (this browser only).
const fs = require('fs'), path = require('path');

const GEN_PATTERNS = [
  /disabled=\{[^}]*!apiKey[^}]*\}/g,
  /\{!apiKey\s*&&/g,
  /title=\{!apiKey/g,
  /opacity:\s*apiKey\s*\?/g,
  /cursor:\s*apiKey\s*\?/g,
  /if \(!apiKey\)/g,
];
// Settings legitimately asks the narrower "did YOU store a key" question.
const ALLOWED = ['src/app/settings/page.tsx', 'src/components/settings/AccountInfoCard.tsx',
                 'src/components/settings/AccountKeyCard.tsx', 'src/components/settings/ManagementKeyCard.tsx',
                 'src/components/layout/UserMenu.tsx'];

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(e.name)) out.push(p);
  }
  return out;
}

const bad = [];
for (const f of walk('src')) {
  const rel = f.replace(/\\/g, '/');
  if (ALLOWED.some(a => rel.endsWith(a) || rel === a)) continue;
  const s = fs.readFileSync(f, 'utf8');
  for (const p of GEN_PATTERNS) {
    const m = s.match(p);
    if (m) bad.push(`${rel}: ${m[0]}`);
  }
}
if (bad.length) {
  console.error('Gates on browser-only apiKey (should use hasKey):');
  bad.forEach(b => console.error('  ' + b));
  process.exit(1);
}
console.log('OK: no generation gate depends on a browser-held key');
