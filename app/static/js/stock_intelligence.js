(function () {
  "use strict";

  const W = window.RetailIQWorkspace;
  const form = document.querySelector("[data-stock-form]");
  const select = document.querySelector("[name='forecast_run_id']");
  const results = document.querySelector("[data-stock-results]");
  const errorBox = document.querySelector("[data-form-error]");
  const submit = document.querySelector("[data-submit]");

  function fillRuns(runs) {
    select.replaceChildren(); const prompt = W.element("option", "", runs.length ? "Select a forecast run" : "No forecast runs available"); prompt.value = ""; select.append(prompt);
    runs.forEach(function (run) { const option = W.element("option", "", "Run #" + run.id + " · " + run.horizon + " days · " + run.forecast_start_date + " – " + run.forecast_end_date); option.value = run.id; select.append(option); });
  }

  function renderResult(data) {
    const header = W.element("div", "result-summary"); const copy = W.element("div");
    const runMeta = W.element("p", "quiet-meta");
    runMeta.append(document.createTextNode("Forecast run "), W.element("span", "numeric", "#" + data.forecast_run_id));
    copy.append(W.element("h3", "", data.horizon + "-day stock position"), runMeta, W.element("p", "", "Overstock multiplier: " + W.formatNumber(data.overstock_multiplier) + " · Configurable prototype rule, not an industry standard.")); header.append(copy);
    const counts = { UNDERSTOCK: 0, SUFFICIENT: 0, OVERSTOCK: 0, INVENTORY_REQUIRED: 0 };
    (data.families || []).forEach(function (family) { if (counts[family.status] !== undefined) counts[family.status] += 1; });
    const strip = W.element("div", "status-counts"); Object.keys(counts).forEach(function (status) { const item = W.element("div"); item.append(W.statusBadge(status), W.element("strong", "numeric", counts[status])); strip.append(item); });
    const wrapper = W.element("div", "table-scroll"); const table = W.element("table", "data-table"); const thead = W.element("thead"); const hr = W.element("tr");
    ["Category", "Current stock", "Forecast demand", "Difference", "Coverage", "Status"].forEach(function (label) { hr.append(W.element("th", "", label)); }); thead.append(hr);
    const tbody = W.element("tbody"); (data.families || []).forEach(function (family) {
      const row = W.element("tr"); row.append(W.element("td", "table-primary", family.family), W.element("td", "numeric", W.formatNumber(family.current_stock)), W.element("td", "numeric", W.formatNumber(family.forecasted_demand)), W.element("td", "numeric", W.formatNumber(family.stock_difference)), W.element("td", "numeric", family.coverage_ratio === null ? "—" : W.formatNumber(family.coverage_ratio) + "×")); const status = W.element("td"); status.append(W.statusBadge(family.status)); row.append(status); tbody.append(row);
    }); table.append(thead, tbody); W.configureTable(wrapper, table, "Stock intelligence classifications"); wrapper.append(table); results.replaceChildren(header, strip, wrapper);
  }

  async function loadRuns() {
    W.setState(results, { kind: "empty", title: "Choose a forecast run", message: "Classification results will appear here after the assessment." });
    try { const response = await window.RetailIQ.api.request("/forecasts"); fillRuns(response.forecast_runs || []); }
    catch (error) { fillRuns([]); W.setState(results, { kind: "error", title: "Forecast runs unavailable", message: W.errorMessage(error) }); }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault(); window.RetailIQUI.clearInlineError(errorBox); const id = Number(select.value);
    if (!Number.isInteger(id) || id < 1) { window.RetailIQUI.showInlineError(errorBox, "Select a forecast run."); return; }
    window.RetailIQUI.setButtonLoading(submit, true, "Assessing stock…"); W.setState(results, { kind: "loading", title: "Running stock intelligence", message: "Comparing current inventory with forecast demand…" });
    try { const response = await window.RetailIQ.api.request("/stock-intelligence", { method: "POST", body: { forecast_run_id: id } }); renderResult(response.stock_intelligence); window.RetailIQUI.showToast("Stock intelligence completed.", "success"); }
    catch (error) { window.RetailIQUI.showInlineError(errorBox, W.errorMessage(error)); W.setState(results, { kind: "error", title: "Assessment unavailable", message: W.errorMessage(error) }); }
    finally { window.RetailIQUI.setButtonLoading(submit, false, "Run stock intelligence"); }
  });

  W.onSessionReady(loadRuns);
})();
