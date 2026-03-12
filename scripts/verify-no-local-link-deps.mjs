import fs from 'node:fs';
import path from 'node:path';

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const packageJsonPath = path.join(repoRoot, 'package.json');
const lockfilePath = path.join(repoRoot, 'pnpm-lock.yaml');

const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
const lockfile = fs.existsSync(lockfilePath) ? fs.readFileSync(lockfilePath, 'utf8') : '';

const problems = [];

function scanDeps(sectionName, deps) {
  if (!deps) return;
  for (const [name, spec] of Object.entries(deps)) {
    if (typeof spec === 'string' && spec.startsWith('link:/')) {
      problems.push(`${sectionName}.${name}=${spec}`);
    }
  }
}

scanDeps('dependencies', packageJson.dependencies);
scanDeps('devDependencies', packageJson.devDependencies);
scanDeps('optionalDependencies', packageJson.optionalDependencies);

if (/link:\/Users\//.test(lockfile)) {
  problems.push('pnpm-lock.yaml contains macOS absolute local link');
}

if (/link:[A-Za-z]:\\/.test(lockfile)) {
  problems.push('pnpm-lock.yaml contains Windows absolute local link');
}

if (problems.length > 0) {
  console.error('Local absolute link dependencies are not allowed in committed files.');
  for (const problem of problems) {
    console.error(`- ${problem}`);
  }
  process.exit(1);
}

console.log('No local absolute link dependencies found.');
