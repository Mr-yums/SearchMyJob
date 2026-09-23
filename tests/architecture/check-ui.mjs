import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('../../ui/src/',import.meta.url));
function files(directory){return fs.readdirSync(directory,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?files(path.join(directory,entry.name)):[path.join(directory,entry.name)]);}
for(const file of files(root).filter(file=>/\.(js|vue)$/.test(file))){
 const relative=path.relative(root,file);
 const source=fs.readFileSync(file,'utf8');
 for(const match of source.matchAll(/from\s*['"](\.[^'"]+)['"]/g)){
  const target=path.resolve(path.dirname(file),match[1]);
  assert.ok(fs.existsSync(target),`${relative}: missing import ${match[1]}`);
  const dependency=path.relative(root,target);
  if(relative.startsWith('shared/'))assert.ok(dependency.startsWith('shared/'),`${relative} depends on ${dependency}`);
  if(relative.startsWith('features/'))assert.ok(!dependency.startsWith('app/'),`${relative} depends on application assembly`);
 }
 if(relative==='app/App.vue')assert.ok(!source.includes('fetch('), 'HTTP behavior belongs in controllers');
}
console.log('PASS: UI imports resolve; shared components and feature controllers respect dependency direction.');
