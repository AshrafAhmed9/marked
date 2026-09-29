// Minimal dependency-free SVG line-chart helper. No charting library --
// this project's entire "Built With" is Python + vanilla JS/HTML/CSS by
// design (see README: cut anything that doesn't serve the core claim).

function lineChartSVG({ series, width = 640, height = 260, padding = { t: 16, r: 16, b: 28, l: 44 }, yFormat = (v) => v, xLabels = [], markers = [] }) {
  const allY = series.flatMap((s) => s.points.map((p) => p.y)).filter((v) => v !== null && v !== undefined && !Number.isNaN(v));
  if (allY.length === 0) return '<svg></svg>';
  let yMin = Math.min(...allY, 0);
  let yMax = Math.max(...allY);
  if (yMin === yMax) { yMin -= 1; yMax += 1; }
  const yPad = (yMax - yMin) * 0.08;
  yMin -= yPad; yMax += yPad;

  const innerW = width - padding.l - padding.r;
  const innerH = height - padding.t - padding.b;
  const n = Math.max(...series.map((s) => s.points.length));

  const xPos = (i) => padding.l + (n <= 1 ? 0 : (i / (n - 1)) * innerW);
  const yPos = (v) => padding.t + innerH - ((v - yMin) / (yMax - yMin)) * innerH;

  const zeroY = yMin <= 0 && yMax >= 0 ? yPos(0) : null;

  const uid = Math.random().toString(36).slice(2, 9);
  let svg = `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Line chart">`;
  svg += `<defs>${series.map((s, si) => `
    <linearGradient id="grad-${uid}-${si}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${s.color}" stop-opacity="0.22" />
      <stop offset="100%" stop-color="${s.color}" stop-opacity="0" />
    </linearGradient>`).join("")}</defs>`;

  // gridlines (3 horizontal)
  for (let g = 0; g <= 2; g++) {
    const v = yMin + ((yMax - yMin) * g) / 2;
    const y = yPos(v);
    svg += `<line x1="${padding.l}" y1="${y}" x2="${width - padding.r}" y2="${y}" stroke="#262e45" stroke-width="1" />`;
    svg += `<text x="${padding.l - 8}" y="${y + 4}" text-anchor="end" font-size="10" fill="#9aa4bf">${yFormat(v)}</text>`;
  }

  if (zeroY !== null) {
    svg += `<line x1="${padding.l}" y1="${zeroY}" x2="${width - padding.r}" y2="${zeroY}" stroke="#f5b942" stroke-width="1" stroke-dasharray="3,3" />`;
  }

  // marker vertical lines (e.g. failure date)
  for (const m of markers) {
    const x = xPos(m.index);
    svg += `<line x1="${x}" y1="${padding.t}" x2="${x}" y2="${height - padding.b}" stroke="${m.color || '#ff5c5c'}" stroke-width="1.5" stroke-dasharray="4,3" />`;
    svg += `<text x="${x}" y="${padding.t - 4}" text-anchor="middle" font-size="10" fill="${m.color || '#ff5c5c'}">${m.label || ''}</text>`;
  }

  series.forEach((s, si) => {
    const coords = s.points
      .map((p, i) => (p.y === null || p.y === undefined || Number.isNaN(p.y) ? null : [xPos(i), yPos(p.y)]))
      .filter(Boolean);
    if (coords.length) {
      const first = coords[0];
      const last = coords[coords.length - 1];
      const floorY = padding.t + innerH;
      const areaPts = `${first[0]},${floorY} ${coords.map((c) => c.join(',')).join(' ')} ${last[0]},${floorY}`;
      svg += `<polygon points="${areaPts}" fill="url(#grad-${uid}-${si})" stroke="none" />`;
    }
    const pts = coords.map((c) => c.join(',')).join(' ');
    const approxLen = coords.reduce((acc, c, i) => i === 0 ? 0 : acc + Math.hypot(c[0] - coords[i - 1][0], c[1] - coords[i - 1][1]), 0);
    svg += `<polyline class="line-path" style="--path-len:${Math.ceil(approxLen) + 10}" points="${pts}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />`;
    s.points.forEach((p, i) => {
      if (p.y === null || p.y === undefined || Number.isNaN(p.y)) return;
      svg += `<circle cx="${xPos(i)}" cy="${yPos(p.y)}" r="2.5" fill="${s.color}" />`;
    });
  });

  // x labels (sparse)
  const step = Math.max(1, Math.ceil(n / 6));
  xLabels.forEach((label, i) => {
    if (i % step !== 0 && i !== xLabels.length - 1) return;
    svg += `<text x="${xPos(i)}" y="${height - 8}" text-anchor="middle" font-size="9" fill="#9aa4bf">${label}</text>`;
  });

  svg += '</svg>';
  return svg;
}
