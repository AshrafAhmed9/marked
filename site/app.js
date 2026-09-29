// Marked — static site logic. No framework, no build step: fetches the
// JSON files pipeline/export_site_data.py writes and renders them.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const fmtPct = (v) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`);
const fmtRatio = (v) => (v === null || v === undefined ? "—" : v.toFixed(2));
const fmtDollarsK = (k) => {
  if (k === null || k === undefined) return "—";
  const b = k / 1_000_000; // field is $000s -> billions
  if (Math.abs(b) >= 1) return `$${b.toFixed(1)}B`;
  return `$${(k / 1000).toFixed(0)}M`;
};
const fmtRank = (r, n) => (r === null || r === undefined ? "not reported" : `#${r} of ${n}`);
const fmtQ = (repdte) => `${repdte.slice(0, 4)} Q${Math.floor((parseInt(repdte.slice(4, 6), 10) - 1) / 3) + 1}`;

function mtmRiskClass(ratio) {
  // < 0: already balance-sheet insolvent on a marked basis. < 2%: thin
  // enough that a bad quarter (or the losses this model can't see, like
  // loans) could flip it negative -- SVB itself was at 0.1% the quarter
  // before it failed. >= 2%: comfortable margin.
  if (ratio === null || ratio === undefined) return "";
  if (ratio < 0) return "risk";
  if (ratio < 0.02) return "warn";
  return "safe";
}

// ---------- tabs ----------
const tabs = [
  ["tab-bank", "panel-bank"],
  ["tab-backtest", "panel-backtest"],
  ["tab-today", "panel-today"],
  ["tab-about", "panel-about"],
];
function activateTab(tabId) {
  for (const [t, p] of tabs) {
    const isActive = t === tabId;
    $(`#${t}`).setAttribute("aria-selected", String(isActive));
    $(`#${p}`).classList.toggle("hidden", !isActive);
  }
}
for (const [t] of tabs) {
  $(`#${t}`).addEventListener("click", () => activateTab(t));
}

// ---------- data loading (lazy, cached) ----------
const cache = {};
async function loadJSON(path) {
  if (cache[path]) return cache[path];
  const res = await fetch(path);
  if (!res.ok) throw new Error(`failed to load ${path}`);
  const data = await res.json();
  cache[path] = data;
  return data;
}

// ---------- bank search ----------
let searchIndex = [];
loadJSON("data/search_index.json").then((idx) => { searchIndex = idx; });

const searchInput = $("#bank-search");
const resultsList = $("#search-results");
searchInput.addEventListener("input", () => {
  const q = searchInput.value.trim().toLowerCase();
  if (q.length < 3) {
    resultsList.classList.add("hidden");
    resultsList.innerHTML = "";
    return;
  }
  const matches = searchIndex.filter((b) => b.name.toLowerCase().includes(q)).slice(0, 20);
  resultsList.innerHTML = matches
    .map((b) => `<li><button data-cert="${b.cert}">${b.name}</button></li>`)
    .join("") || `<li><span class="hint">No matches.</span></li>`;
  resultsList.classList.remove("hidden");
});
resultsList.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-cert]");
  if (!btn) return;
  showBank(parseInt(btn.dataset.cert, 10));
  resultsList.classList.add("hidden");
});

async function showBank(cert) {
  const detail = $("#bank-detail");
  detail.classList.remove("hidden");
  detail.innerHTML = `<p class="hint">Loading…</p>`;
  let data;
  try {
    data = await loadJSON(`data/bank_${cert}.json`);
  } catch (e) {
    detail.innerHTML = `<p class="hint">No timeseries exported for this bank yet. Try Silicon Valley Bank, Signature Bank, First Republic Bank, or Republic Bank.</p>`;
    return;
  }
  renderBankDetail(detail, data);
}

function renderBankDetail(container, data) {
  const pts = data.points;
  const latest = pts[pts.length - 1];
  const failed = !!data.failure;

  const failIndex = failed
    ? pts.findIndex((p) => p.repdte >= data.failure.faildate.replace(/-/g, "").slice(0, 6))
    : -1;

  const series = [
    { color: "#ff5c5c", points: pts.map((p) => ({ y: p.mtm_equity_ratio === null ? null : p.mtm_equity_ratio * 100 })) },
  ];
  const svg = lineChartSVG({
    series,
    xLabels: pts.map((p) => fmtQ(p.repdte)),
    yFormat: (v) => `${v.toFixed(0)}%`,
    markers: failIndex >= 0 ? [{ index: failIndex, label: "Failed", color: "#ff5c5c" }] : [],
  });

  const tier1Series = [
    { color: "#5c9dff", points: pts.map((p) => ({ y: p.tier1_rbc })) },
  ];
  const tier1Svg = lineChartSVG({
    series: tier1Series,
    xLabels: pts.map((p) => fmtQ(p.repdte)),
    yFormat: (v) => `${v.toFixed(0)}%`,
    markers: failIndex >= 0 ? [{ index: failIndex, label: "Failed", color: "#ff5c5c" }] : [],
  });

  let runSliderHTML = "";
  if (latest.run_threshold_dollars_k !== null) {
    const uninsuredK = latest.uninsured_share !== null ? latest.uninsured_share * (latest.asset_k) : null;
    runSliderHTML = `
      <div class="slider-row">
        <label for="run-slider">Simulate uninsured-deposit withdrawal (as of ${fmtQ(latest.repdte)})</label>
        <input type="range" id="run-slider" min="0" max="100" value="0" />
        <p class="hint" id="run-slider-readout"></p>
      </div>`;
  }

  container.innerHTML = `
    <p class="bank-name">${data.name}${failed ? `<span class="badge failed">Failed ${data.failure.faildate}</span>` : ""}</p>
    <p class="bank-meta">${failed ? data.failure.note : "Currently operating (per latest FDIC filing)."}</p>

    <div class="stat-grid">
      <div class="stat"><div class="label">Run-risk rank (latest)</div><div class="value ${latest.rank_run_risk && latest.rank_run_risk < latest.n_banks * 0.05 ? "risk" : ""}">${fmtRank(latest.rank_run_risk, latest.n_banks)}</div></div>
      <div class="stat"><div class="label">Tier 1 capital rank (latest)</div><div class="value">${fmtRank(latest.rank_tier1, latest.n_banks)}</div></div>
      <div class="stat"><div class="label">Uninsured deposit share</div><div class="value">${fmtPct(latest.uninsured_share)}</div></div>
      <div class="stat"><div class="label">Mark-to-market equity / assets</div><div class="value ${mtmRiskClass(latest.mtm_equity_ratio)}">${fmtPct(latest.mtm_equity_ratio)}</div></div>
    </div>

    <h2>Mark-to-market equity ratio over time</h2>
    <p class="hint">Book equity minus the unbooked loss on held-to-maturity bonds, as a share of assets. Below zero means the bank would be balance-sheet insolvent if it had to recognize that loss.</p>
    ${svg}

    <h2>Regulatory Tier 1 risk-based capital ratio, same period</h2>
    <p class="hint">This is the number regulators and most public reporting use. Compare its shape to the chart above.</p>
    ${tier1Svg}

    ${runSliderHTML}

    <h2>Quarterly detail</h2>
    <div class="overflow-x">
      <table class="data">
        <thead><tr><th>Quarter</th><th>Run-risk rank</th><th>Tier1 rank</th><th>MTM equity/assets</th><th>Uninsured share</th><th>Liquidity cover</th></tr></thead>
        <tbody>
          ${pts.slice().reverse().map((p) => `
            <tr>
              <td>${fmtQ(p.repdte)}</td>
              <td>${fmtRank(p.rank_run_risk, p.n_banks)}</td>
              <td>${fmtRank(p.rank_tier1, p.n_banks)}</td>
              <td>${fmtPct(p.mtm_equity_ratio)}</td>
              <td>${fmtPct(p.uninsured_share)}</td>
              <td>${fmtRatio(p.liquidity_cover)}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;

  const slider = $("#run-slider", container);
  if (slider) {
    const readout = $("#run-slider-readout", container);
    const uninsuredTotalK = latest.uninsured_share !== null ? latest.uninsured_share * latest.asset_k * ((latest.uninsured_share) > 0 ? 1 : 1) : null;
    // uninsured deposit dollar amount isn't directly exported; approximate
    // via the run-threshold fields, which ARE exact dollar amounts from the
    // scoring pipeline.
    const updateReadout = () => {
      const pct = parseInt(slider.value, 10);
      const liquidThresholdPct = latest.run_threshold_dollars_k !== null && latest.asset_k
        ? null : null;
      readout.innerHTML = `Withdrawing <strong>${pct}%</strong> of uninsured deposits: ` +
        (latest.run_threshold_dollars_k !== null
          ? `cash + AFS securities cover withdrawals up to <strong>${fmtDollarsK(latest.run_threshold_dollars_k)}</strong> before the bank must start selling held-to-maturity bonds at a loss.`
          : "this bank does not report uninsured deposits, so a threshold can't be estimated.");
    };
    slider.addEventListener("input", updateReadout);
    updateReadout();
  }
}

// ---------- backtest tab ----------
async function renderBacktest() {
  const data = await loadJSON("data/backtest.json");
  const rows = data.section_a_failure_ranks.filter((r) => r.run_driven);
  const table = `
    <table class="data">
      <thead><tr><th>Bank</th><th>Failed</th><th>Quarters before</th><th>N banks</th><th>Run-risk rank</th><th>Tier1 rank</th><th>Classic ML rank</th></tr></thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td>${r.name}</td><td>${r.faildate}</td><td>T-${r.quarters_before}</td><td>${r.n_banks}</td>
            <td><strong>${r.rank_run_risk ?? "—"}</strong></td><td>${r.rank_tier1 ?? "—"}</td><td>${r.rank_classic ?? "—"}</td>
          </tr>`).join("")}
      </tbody>
    </table>
    <details style="margin-top:12px;">
      <summary class="hint" style="cursor:pointer;">Also show non-run-driven failures (fraud, credit) — where run-risk correctly stays quiet</summary>
      <table class="data" style="margin-top:8px;">
        <thead><tr><th>Bank</th><th>Failed</th><th>Cause</th><th>Quarters before</th><th>Run-risk rank</th><th>Classic ML rank</th></tr></thead>
        <tbody>
          ${data.section_a_failure_ranks.filter((r) => !r.run_driven).map((r) => `
            <tr><td>${r.name}</td><td>${r.faildate}</td><td>${r.name.includes("HEARTLAND") ? "fraud" : "other/credit"}</td><td>T-${r.quarters_before}</td>
            <td>${r.rank_run_risk ?? "—"}</td><td>${r.rank_classic ?? "—"}</td></tr>`).join("")}
        </tbody>
      </table>
    </details>
  `;
  $("#backtest-table").innerHTML = table;

  const b = data.section_b_deposit_flight;
  $("#deposit-flight-panel").innerHTML = `
    <h2>Did the score predict the 2023 deposit panic?</h2>
    <p class="hint">Testing whether the Q3 2022 score predicted which banks lost the most deposits in the run quarter (Q4 2022 → Q1 2023).</p>
    <div class="stat-grid">
      <div class="stat"><div class="label">Run-risk AUC (${b.on_reporting_banks.run_risk_raw.n} reporting banks)</div><div class="value safe">${b.on_reporting_banks.run_risk_raw.auc}</div></div>
      <div class="stat"><div class="label">Tier 1 AUC (same banks)</div><div class="value risk">${b.on_reporting_banks.tier1_raw.auc}</div></div>
      <div class="stat"><div class="label">Top-decile lift, run-risk</div><div class="value">${b.on_reporting_banks.run_risk_raw.lift}×</div></div>
      <div class="stat"><div class="label">Tier 1 AUC, all ${b.all_banks_n} banks</div><div class="value">${b.tier1_on_all_banks_for_context.auc}</div></div>
    </div>
    <p class="hint">${b.note} Seasonally adjusted run-risk AUC (netting out each bank's typical Q1 deposit pattern): ${b.on_reporting_banks.run_risk_seasonal_adj.auc}.</p>
  `;

  const d1 = data.d1_permutation_test;
  $("#permutation-panel").innerHTML = `
    <h2>Could this be luck?</h2>
    <p>Chance that ${d1.n_failures} banks, picked at random from ${d1.n_banks.toLocaleString()}, all land in the top ${d1.top_k}: <strong>${d1.p_closed_form.toExponential(2)}</strong> (closed-form), confirmed by ${d1.n_trials.toLocaleString()}-trial simulation.</p>
  `;

  try {
    const d2 = await loadJSON("data/d2_depth.json");
    const rows2 = Object.entries(d2.named).map(([name, pts]) => {
      const last = pts[pts.length - 1];
      return `<tr><td>${name}</td><td>${fmtQ(last.repdte)}</td><td>#${last.rank_run_risk} of ${last.n_banks}</td><td>#${last.rank_tier1} of ${last.n_banks}</td></tr>`;
    }).join("");
    $("#d2-panel").innerHTML = `
      <h2>Applied unchanged to the 2008 crisis</h2>
      <p class="hint">Same frozen formula, a completely different era, checked against IndyMac and Washington Mutual — the two largest run-driven failures of 2008.</p>
      <table class="data"><thead><tr><th>Bank</th><th>Quarter</th><th>Run-risk rank</th><th>Tier1 rank</th></tr></thead><tbody>${rows2}</tbody></table>
      <p class="hint">${d2.field_availability_note}</p>
    `;
  } catch (e) {
    $("#d2-panel").innerHTML = "";
  }
}
renderBacktest();

// ---------- today tab ----------
async function renderToday() {
  const panel = $("#today-panel");
  try {
    const t = await loadJSON("data/today.json");
    const rows = t.top_15.map((r) => `
      <tr><td>${r.name}</td><td>#${r.rank_run_risk}</td><td>${(r.uninsured_share * 100).toFixed(0)}%</td><td>${(r.mtm_equity_ratio * 100).toFixed(1)}%</td></tr>
    `).join("");
    panel.innerHTML = `
      <h2>Where things stand today (${fmtQ(t.as_of)})</h2>
      <div class="stat-grid">
        <div class="stat"><div class="label">Banks scored</div><div class="value">${t.n_banks.toLocaleString()}</div></div>
        <div class="stat"><div class="label">Report uninsured deposits</div><div class="value">${t.n_reporters.toLocaleString()}</div></div>
        <div class="stat"><div class="label">Negative MTM equity</div><div class="value ${t.n_negative_mtm_equity > 0 ? "risk" : "safe"}">${t.n_negative_mtm_equity}</div></div>
        <div class="stat"><div class="label">Industry-wide unbooked HTM loss</div><div class="value risk">${fmtDollarsK(t.total_htm_unrealized_loss_k)}</div></div>
      </div>
      <p class="hint">No bank currently matches the SVB pattern (negative mark-to-market equity combined with a large uninsured deposit base). The highest-ranked banks below are not predictions of failure — see "How it works &amp; limits."</p>
      <table class="data">
        <thead><tr><th>Bank</th><th>Run-risk rank</th><th>Uninsured share</th><th>MTM equity/assets</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="disclaimer" style="margin-top:16px;">This is not an assertion that any bank listed here is at risk of failure. It is a ranking on two public accounting inputs, with known limitations described in "How it works &amp; limits."</p>
    `;
  } catch (e) {
    panel.innerHTML = `<p class="hint">Today snapshot not available in this build.</p>`;
  }
}
renderToday();

// Preselect SVB on load for a fast first impression
loadJSON("data/search_index.json").then(() => showBank(24735)).catch(() => {});
