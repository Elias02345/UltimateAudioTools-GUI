import { readFile, writeFile } from 'node:fs/promises';
import { compile } from 'json-schema-to-typescript';
const schema = JSON.parse(await readFile('packages/shared/schema.json', 'utf8'));
await writeFile('packages/shared/types.ts', await compile(schema, 'Contract', { ignoreMinAndMaxItems: true, bannerComment: '/* Generated from Pydantic. Run scripts/generate_schema.py and scripts/generate_types.mjs. */' }));
