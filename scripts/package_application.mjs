import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const env = { ...process.env };
if (process.platform === "linux") {
  // linuxdeploy inspects torchvision without Python first loading Torch's libraries.
  const torchLibraries = resolve(
    root,
    "apps/desktop/src-tauri/resources/runtime/python/lib/python3.12/site-packages/torch/lib",
  );
  env.LD_LIBRARY_PATH = [torchLibraries, env.LD_LIBRARY_PATH]
    .filter(Boolean)
    .join(":");
}
// Tauri treats an empty signing certificate as a supplied certificate and attempts import.
for (const key of Object.keys(env)) {
  if (key.startsWith("APPLE_") && !env[key]) delete env[key];
}
const args = [
  "build",
  "--config",
  "apps/desktop/src-tauri/tauri.conf.json",
  "--config",
  "apps/desktop/src-tauri/tauri.runtime.conf.json",
];
if (!env.TAURI_SIGNING_PRIVATE_KEY) {
  args.push(
    "--config",
    JSON.stringify({ bundle: { createUpdaterArtifacts: false } }),
  );
  process.stdout.write(
    "No update signing key: building installers without updater artifacts.\n",
  );
}
if (process.platform === "win32" && env.WINDOWS_CERTIFICATE_THUMBPRINT) {
  args.push(
    "--config",
    JSON.stringify({
      bundle: {
        windows: {
          certificateThumbprint: env.WINDOWS_CERTIFICATE_THUMBPRINT,
          digestAlgorithm: "sha256",
          timestampUrl: "http://timestamp.digicert.com",
        },
      },
    }),
  );
}
args.push(...process.argv.slice(2));
const result = spawnSync(
  process.execPath,
  [resolve(root, "node_modules/@tauri-apps/cli/tauri.js"), ...args],
  {
    cwd: root,
    env,
    stdio: "inherit",
  },
);
if (result.error) throw result.error;
process.exit(result.status ?? 1);
