import fs from 'node:fs';
const buf = fs.readFileSync(process.argv[2]);
const len = buf.readUInt32LE(12); const json = JSON.parse(buf.slice(20, 20 + len).toString());
console.log('nodes', json.nodes.length, 'meshes', json.meshes.length, 'materials', json.materials.length, 'anims', (json.animations || []).length);
for (const a of json.animations || []) {
  const paths = {}; for (const c of a.channels) paths[c.target.path] = (paths[c.target.path] || 0) + 1;
  const interp = {}; for (const s of a.samplers) interp[s.interpolation] = (interp[s.interpolation] || 0) + 1;
  const acc = json.accessors[a.samplers[0].input];
  console.log(a.name, a.channels.length, JSON.stringify(paths), JSON.stringify(interp), 'time', acc.min, acc.max);
}
