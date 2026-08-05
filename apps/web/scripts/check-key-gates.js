// Every place the UI decides whether generation is POSSIBLE must consult
// hasKey (which includes the server's key), never the browser-held key.
//
// Passing the browser key on to api.ts is fine and intended — it is an
// override, and api.ts omits the header when it is null so the server falls
// back to its own. The bug is only ever using it as a CONDITION.
//
// An earlier version enumerated syntactic shapes of the literal identifier
// `apiKey`, and passed while three real gates existed, because a gate can
// hide behind any name:
//   const key = keyStore.getKey(); if (!key) …            ParticipantsStep
//   const { apiKey: openrouterKey } = useOpenRouterKey()  room/page.tsx
//   {!openrouterKey && <ApiKeyRequired/>}                 MockDefenseRoom, via a prop
//
// So: find every identifier bound to the browser key in a file, then flag any
// boolean use of it. Name-independent, and it still allows the override.
const fs = require('fs'), path = require('path');

// Settings legitimately asks the narrower "did YOU store a key" question, and
// the hook and store must read the key to expose it.
const ALLOWED = [
  'src/app/settings/page.tsx',
  'src/components/settings/AccountInfoCard.tsx',
  'src/components/settings/AccountKeyCard.tsx',
  'src/components/settings/ManagementKeyCard.tsx',
  'src/components/layout/UserMenu.tsx',
  'src/hooks/useOpenRouterKey.ts',
  'src/lib/openrouterKeyStore.ts',
  // The transport layer is where the override belongs: attach the header when
  // a browser key exists, omit it otherwise so the server uses its own.
  'src/lib/api.ts',
  'src/lib/organizations.ts',
];

// Names that hold the BROWSER key after one of these bindings.
const BINDINGS = [
  // const key = keyStore.getKey()
  /(?:const|let|var)\s+(\w+)\s*=\s*keyStore\.getKey\(\)/g,
  // const { apiKey } = useOpenRouterKey()  /  { apiKey: alias }
  /\{[^}]*\bapiKey\b\s*(?::\s*(\w+))?[^}]*\}\s*=\s*useOpenRouterKey\(\)/g,
];

// A component receiving the key as a prop holds it under that name too.
const KEY_PROP_NAMES = ['openrouterKey', 'openRouterKey'];

function booleanUses(src, name) {
  // `(?<![.\w])` so a property that happens to share the name — `d.key`,
  // `expanded === d.key` — is not mistaken for the key variable itself.
  const n = '(?<![.\\w])' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return [
    new RegExp(`!\\s*${n}\\b`, 'g'),                        // !key
    // `key ? a : b`, but NOT the TypeScript optional marker `key?: string`.
    new RegExp(`\\b${n}\\s*\\?(?!\\s*:)`, 'g'),
    new RegExp(`\\b${n}\\s*&&`, 'g'),                       // key && …
    // …and the mirror image. `x === 'running' && apiKey` disabled the only
    // Next Turn button in the app and this checker could not see it.
    new RegExp(`&&\\s*${n}\\b`, 'g'),
    new RegExp(`\\|\\|\\s*${n}\\b`, 'g'),
    new RegExp(`if\\s*\\(\\s*${n}\\s*\\)`, 'g'),            // if (key)
    new RegExp(`disabled=\\{[^}]*\\b${n}\\b[^}]*\\}`, 'g'), // disabled={…key…}
  ]
    .flatMap(re => src.match(re) || [])
    // A console.log that prints !!key is diagnostics, not a gate.
    .filter(m => {
      const around = src.slice(
        Math.max(0, src.indexOf(m) - 140),
        src.indexOf(m) + m.length + 140
      );
      // A console.log printing !!key is diagnostics, not a gate.
      if (new RegExp(`console\\.\\w+\\([^)]*${name}`).test(around)) return false;
      // "browser key OR server capability" is the correct override pattern:
      //   !openrouterKey.trim() && !keyStore.hasKey()
      if (/hasKey\s*\(\s*\)/.test(around)) return false;
      return true;
    });
}

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
  if (ALLOWED.some(a => rel.endsWith(a))) continue;
  const s = fs.readFileSync(f, 'utf8');

  const names = new Set();
  for (const re of BINDINGS) {
    for (const m of s.matchAll(re)) names.add(m[1] || 'apiKey');
  }
  for (const n of KEY_PROP_NAMES) {
    if (new RegExp(`\\b${n}\\b`).test(s)) names.add(n);
  }

  for (const name of names) {
    for (const use of booleanUses(s, name)) {
      bad.push(`${rel}: ${use.trim().replace(/\s+/g, ' ')}   [browser key "${name}" as a condition]`);
    }
  }
}

if (bad.length) {
  console.error('Generation gated on a BROWSER-held key. Use hasKey() for the');
  console.error('capability question; pass the key itself only as an override:');
  [...new Set(bad)].forEach(b => console.error('  ' + b));
  process.exit(1);
}
console.log('OK: no generation gate depends on a browser-held key');
