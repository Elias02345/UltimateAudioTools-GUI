import { readFile, writeFile } from 'node:fs/promises';
import { compile } from 'json-schema-to-typescript';
import Ajv from 'ajv';
import standalone from 'ajv/dist/standalone/index.js';
import helper from 'ajv/dist/runtime/ucs2length.js';
const schema = JSON.parse(await readFile('packages/shared/schema.json', 'utf8'));
await writeFile('packages/shared/types.ts', await compile(schema, 'Contract', { ignoreMinAndMaxItems: true, bannerComment: '/* Generated from Pydantic. Run scripts/generate_schema.py and scripts/generate_types.mjs. */' }));
// Compile at build time: the production webview deliberately forbids dynamic evaluation.
const ajv = new Ajv({ strict: false, allErrors: true, code: { source: true, esm: true } });
ajv.addSchema(schema, 'separator-contract');
const names = Object.keys(schema.$defs);
let source = standalone(ajv, Object.fromEntries(names.map(name => [name, `separator-contract#/$defs/${name}`])));
// AJV standalone emits this one CommonJS helper even with ESM output.
source = source.replaceAll('require("ajv/dist/runtime/ucs2length").default', 'ucs2length');
if (/\brequire\s*\(/.test(source)) throw new Error('An unexpected standalone helper needs a static ESM import.');
// Preserve AJV's unchanged Unicode helper without a browser-time CommonJS loader.
source = '/* Generated contract validators. Do not edit. AJV is MIT licensed. */\nconst ucs2length = ' + (helper.default ?? helper).toString() + ';\n' + source;
await writeFile('packages/shared/validators.js', source + '\n');
await writeFile('packages/shared/validators.d.ts', '/* Generated contract validators. Do not edit. */\nimport type { ValidateFunction } from "ajv";\n' + names.map(name => `export declare const ${name}: ValidateFunction;`).join('\n') + '\n');
