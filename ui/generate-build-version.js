import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const packageJson = JSON.parse(fs.readFileSync(path.join(currentDir, 'package.json'), 'utf8'));

const jsonData = {
  version: packageJson.version,
};

fs.writeFileSync(path.join(currentDir, 'public', 'meta.json'), JSON.stringify(jsonData), 'utf8');
console.log('meta.json file has been saved with latest version number');
