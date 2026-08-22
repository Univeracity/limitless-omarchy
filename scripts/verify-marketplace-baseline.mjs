import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

function argument(name) {
  const prefix = `--${name}=`;
  const value = process.argv.find((candidate) => candidate.startsWith(prefix))?.slice(prefix.length);
  if (!value) throw new Error(`${prefix}<path> is required`);
  return path.resolve(value);
}

function trackedFiles(repository) {
  return execFileSync("git", ["-C", repository, "ls-files", "-s", "-z"], {
    encoding: "utf8",
  })
    .split("\0")
    .filter(Boolean)
    .map((record) => {
      const match = record.match(/^(\d+) [0-9a-f]+ \d+\t([\s\S]+)$/);
      if (!match) throw new Error("tracked source inventory is invalid");
      return { mode: match[1], path: match[2] };
    });
}

const marketplace = argument("marketplace");
const repository = argument("repository");
const manifest = JSON.parse(fs.readFileSync(path.join(repository, "manifest.json"), "utf8"));
const requiredPaths = new Set(Object.values(manifest.entryPoints || {}));
if (!requiredPaths.size || [...requiredPaths].some((value) => typeof value !== "string" || !value)) {
  throw new Error("plugin manifest entry points are invalid");
}

const scope = await import(
  pathToFileURL(path.join(marketplace, "scripts", "security-baseline-scope.mjs")).href
);
const analysis = await import(
  pathToFileURL(path.join(marketplace, "scripts", "security-baseline-analysis.mjs")).href
);

const files = trackedFiles(repository)
  .filter((entry) => scope.isSecurityScanPath(entry.path) || requiredPaths.has(entry.path))
  .map((entry) => {
    const absolute = path.join(repository, entry.path);
    const bytes = fs.readFileSync(absolute);
    if (bytes.length > scope.securityFileByteLimit || bytes.includes(0)) {
      throw new Error(`unsupported marketplace scan file: ${entry.path}`);
    }
    return { ...entry, content: bytes.toString("utf8") };
  });

if (files.length > scope.securitySnapshotFileLimit) {
  throw new Error("marketplace scan file limit exceeded");
}
if (files.reduce((total, entry) => total + Buffer.byteLength(entry.content), 0) > scope.securitySnapshotByteLimit) {
  throw new Error("marketplace scan byte limit exceeded");
}

const commitSha = execFileSync("git", ["-C", repository, "rev-parse", "HEAD"], {
  encoding: "utf8",
}).trim();
const result = analysis.buildSecurityBaseline({
  repository: "Univeracity/limitless-omarchy",
  repoUrl: "https://github.com/Univeracity/limitless-omarchy",
  commitSha,
  files,
});
const capabilities = result.capabilities.map((capability) => capability.id).sort();
const findings = result.findings.map((finding) => finding.ruleId).sort();

if (
  result.outcome !== "review-required"
  || result.blocksApproval
  || findings.length !== 0
  || JSON.stringify(capabilities) !== JSON.stringify(["package-manager"])
) {
  throw new Error(
    `unexpected marketplace baseline: ${JSON.stringify({
      outcome: result.outcome,
      blocksApproval: result.blocksApproval,
      findings,
      capabilities,
    })}`,
  );
}

process.stdout.write(`${JSON.stringify({
  schemaVersion: "limitless.omarchy-marketplace-readiness/1.0",
  repository: result.repository,
  commitSha,
  baselineVersion: result.baselineVersion,
  enforcementMode: result.enforcementMode,
  outcome: result.outcome,
  findings,
  capabilities,
  scannedFiles: files.map((entry) => entry.path),
}, null, 2)}\n`);
