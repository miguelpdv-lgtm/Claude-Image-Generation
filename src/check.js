#!/usr/bin/env node
// Verifica que la configuracion y la API key funcionen, sin gastar creditos de imagen.
import { ApimartClient, ApimartError, loadEnv } from './apimart.js';

loadEnv();

const key = process.env.APIMART_API_KEY;
const base = process.env.APIMART_BASE_URL || 'https://api.apimart.ai/v1';

console.log('\nComprobacion de configuracion APIMart');
console.log('--------------------------------------');
console.log('Node:      ' + process.version);
console.log('Base URL:  ' + base);

if (!key) {
  console.error('API key:   FALTA -> escribe APIMART_API_KEY en el archivo .env');
  process.exit(1);
}
console.log('API key:   ' + key.slice(0, 6) + '...' + key.slice(-4) + ` (${key.length} chars)`);

try {
  const client = new ApimartClient();
  const res = await client.request('/models');
  const list = Array.isArray(res?.data) ? res.data : [];
  console.log('Conexion:  OK (' + list.length + ' modelos visibles en la cuenta)');

  const wanted = ['seedream-4.5', 'gpt-image-2', 'nano-banana', 'gemini-2.5-flash-image-preview'];
  const ids = new Set(list.map((m) => String(m.id ?? m.model ?? '').toLowerCase()));
  const found = wanted.filter((w) => ids.has(w.toLowerCase()));
  if (list.length) {
    console.log('Imagen:    ' + (found.length ? found.join(', ') : 'ninguno del catalogo local aparece listado (puede seguir funcionando)'));
  }
  console.log('\nTodo listo. Prueba:  npm run gen -- "un panda astronauta" --size 16:9\n');
} catch (err) {
  if (err instanceof ApimartError) {
    console.error('Conexion:  FALLO -> ' + err.message);
    if (err.status === 401) console.error('\nRevisa la API key en https://apimart.ai/keys');
  } else {
    console.error('Conexion:  FALLO -> ' + (err?.message ?? err));
  }
  process.exit(1);
}
