// Parses CSV input, profiles every column and builds a Gemini request body.
// Used verbatim as the "Profile Data & Build Prompt" Code node (see generate_workflow.py).
const SAMPLE_CSV = `date,region,product,units,revenue
2026-01-05,EU,Widget,120,2400
2026-01-12,US,Widget,200,4000
2026-02-03,EU,Gadget,75,3750
2026-02-18,APAC,Gadget,60,3000
2026-03-07,US,Widget,310,6200
2026-03-21,EU,Widget,95,1900
2026-04-02,APAC,Gizmo,40,2800
2026-04-15,US,Gizmo,55,3850`;

function parseCsv(text) {
  const rows = [];
  let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); cell = '';
      if (row.some(v => v.trim() !== '')) rows.push(row);
      row = [];
    } else cell += c;
  }
  row.push(cell);
  if (row.some(v => v.trim() !== '')) rows.push(row);
  return rows;
}

function profileColumns(headers, records) {
  return headers.map((name, idx) => {
    const vals = records.map(r => (r[idx] ?? '').trim());
    const filled = vals.filter(v => v !== '');
    const nums = filled.map(Number).filter(n => Number.isFinite(n));
    const col = { name, missing: vals.length - filled.length, unique: new Set(filled).size };
    if (filled.length && nums.length === filled.length) {
      const s = [...nums].sort((a, b) => a - b);
      const sum = nums.reduce((a, b) => a + b, 0);
      const mid = Math.floor(s.length / 2);
      col.type = 'numeric';
      col.min = s[0];
      col.max = s[s.length - 1];
      col.sum = +sum.toFixed(4);
      col.mean = +(sum / nums.length).toFixed(4);
      col.median = s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
    } else {
      const counts = {};
      filled.forEach(v => { counts[v] = (counts[v] || 0) + 1; });
      col.type = 'text';
      col.topValues = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5)
        .map(([value, count]) => ({ value, count }));
    }
    return col;
  });
}

function buildProfile(csvText, maxSampleRows = 10) {
  const rows = parseCsv(csvText);
  if (rows.length < 2) throw new Error('CSV needs a header row and at least one data row.');
  const headers = rows[0].map(h => h.trim());
  const records = rows.slice(1);
  return {
    rowCount: records.length,
    columnCount: headers.length,
    columns: profileColumns(headers, records),
    sampleRows: records.slice(0, maxSampleRows).map(r =>
      Object.fromEntries(headers.map((h, i) => [h, (r[i] ?? '').trim()])))
  };
}

function buildPrompt(profile, question) {
  return 'You are a careful data analyst. Use ONLY the dataset profile below. ' +
    'Answer the question with concrete numbers, list key insights, and mention any data-quality issues. ' +
    'If the profile is insufficient, say so.\n\nQUESTION: ' + question +
    '\n\nDATASET PROFILE (JSON):\n' + JSON.stringify(profile, null, 2);
}

// ---- n8n entry point ----
const input = $input.first()?.json || {};
const body = input.body || input.query || input;
const csv = String(body.csv || SAMPLE_CSV);
const question = String(body.question || 'Summarize this dataset and highlight the most important trends.');
const profile = buildProfile(csv);

return [{
  json: {
    question,
    profile,
    requestBody: {
      contents: [{ role: 'user', parts: [{ text: buildPrompt(profile, question) }] }],
      generationConfig: { temperature: 0.2 }
    }
  }
}];
