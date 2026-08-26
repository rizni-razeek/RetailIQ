(function () {
  "use strict";

  const W = window.RetailIQWorkspace;
  const uploadSelect = document.querySelector("[data-analytics-upload]");
  const familySelect = document.querySelector("[data-analytics-family]");
  const forecastSelect = document.querySelector("[data-analytics-forecast-select]");
  const salesContainer = document.querySelector("[data-analytics-sales]");
  const categoriesContainer = document.querySelector("[data-analytics-categories]");
  const forecastContainer = document.querySelector("[data-analytics-forecast]");
  const stockContainer = document.querySelector("[data-analytics-stock]");
  const anomalyContainer = document.querySelector("[data-analytics-anomalies]");
  let uploadVersion = 0;
  let forecastVersion = 0;
  let salesVersion = 0;

  function clearCharts(container) {
    container.querySelectorAll("canvas").forEach(function (canvas) {
      window.RetailIQCharts.destroy(canvas);
    });
  }

  function actionLink(path, label) {
    const action = W.element("a", "btn btn-secondary", label);
    action.href = path;
    return action;
  }

  function chartFrame(label, summary) {
    const frame = W.element("div", "chart-block");
    const canvasWrap = W.element("div", "chart-canvas-wrap");
    const canvas = W.element("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", label);
    canvas.append(document.createTextNode(summary));
    canvasWrap.append(canvas);
    frame.append(canvasWrap, W.element("p", "chart-summary", summary));
    return { frame: frame, canvas: canvas };
  }

  function showChartUnavailable(chart) {
    W.setState(chart.canvas.parentElement, { kind: "error", title: "Chart unavailable", message: "The chart library could not be loaded. The textual summary remains available below." });
  }

  function dataTable(label, headers, rows) {
    const wrapper = W.element("div", "table-scroll");
    const table = W.element("table", "data-table");
    const thead = W.element("thead"); const headRow = W.element("tr");
    headers.forEach(function (heading) { headRow.append(W.element("th", "", heading)); }); thead.append(headRow);
    const tbody = W.element("tbody");
    rows.forEach(function (cells) {
      const row = W.element("tr");
      cells.forEach(function (cell) {
        const tableCell = W.element("td", cell.className || "");
        if (cell.node) tableCell.append(cell.node); else tableCell.textContent = cell.value;
        row.append(tableCell);
      });
      tbody.append(row);
    });
    table.append(thead, tbody); W.configureTable(wrapper, table, label); wrapper.append(table); return wrapper;
  }

  function metricStrip(items) {
    const metrics = W.element("dl", "metric-strip analytics-metrics");
    items.forEach(function (item) {
      const group = W.element("div"); group.append(W.element("dt", "", item[0]), W.element("dd", item[2] || "numeric", item[1])); metrics.append(group);
    });
    return metrics;
  }

  function fillUploads(uploads) {
    uploadSelect.replaceChildren();
    const prompt = W.element("option", "", uploads.length ? "Select an upload" : "No uploads available"); prompt.value = ""; uploadSelect.append(prompt);
    uploads.forEach(function (upload) { const option = W.element("option", "", "#" + upload.id + " · " + upload.original_filename); option.value = upload.id; uploadSelect.append(option); });
    uploadSelect.disabled = !uploads.length;
    if (uploads.length) uploadSelect.value = String(uploads[0].id);
  }

  function fillForecastRuns(runs) {
    forecastSelect.replaceChildren();
    const prompt = W.element("option", "", runs.length ? "Select a forecast run" : "No forecast runs available"); prompt.value = ""; forecastSelect.append(prompt);
    runs.forEach(function (run) { const option = W.element("option", "", "Run #" + run.id + " · " + run.horizon + " days · " + run.forecast_start_date + " – " + run.forecast_end_date); option.value = run.id; forecastSelect.append(option); });
    forecastSelect.disabled = !runs.length;
    if (runs.length) forecastSelect.value = String(runs[0].id);
  }

  function fillFamilies(categories) {
    familySelect.replaceChildren();
    const all = W.element("option", "", "All categories"); all.value = ""; familySelect.append(all);
    categories.forEach(function (category) { const option = W.element("option", "", category.family); option.value = category.family; familySelect.append(option); });
    familySelect.disabled = !categories.length;
  }

  function renderSales(trends) {
    clearCharts(salesContainer);
    if (!trends.data.length) {
      W.setState(salesContainer, { kind: "empty", title: trends.family ? "No sales for this category" : "No historical sales", message: trends.family ? "The selected category has no daily observations in this upload." : "Choose an upload with historical sales records.", action: actionLink("/uploads", "Go to uploads") });
      return;
    }
    const familyScope = trends.family ? " for " + trends.family : " across all categories";
    const summary = W.formatNumber(trends.total_sales) + " recorded sales" + familyScope + " from " + W.formatDateOnly(trends.date_from) + " to " + W.formatDateOnly(trends.date_to) + ".";
    const chart = chartFrame("Daily historical sales line chart" + familyScope, summary);
    salesContainer.replaceChildren(chart.frame);
    if (!window.RetailIQCharts.create(chart.canvas, {
      type: "line",
      labels: trends.data.map(function (item) { return item.date; }),
      datasets: [{ label: "Recorded sales", data: trends.data.map(function (item) { return item.sales; }), tone: "primary", fill: false }],
      yTitle: "Sales volume",
      maxTicks: 10,
    })) showChartUnavailable(chart);
  }

  function renderCategories(summary) {
    clearCharts(categoriesContainer);
    fillFamilies(summary.categories);
    if (!summary.categories.length) {
      W.setState(categoriesContainer, { kind: "empty", title: "No category data", message: "The selected upload does not contain usable category sales summaries." });
      return;
    }
    const text = summary.categories.map(function (category) { return category.family + ": " + W.formatNumber(category.total_sales); }).join("; ");
    const chart = chartFrame("Historical sales totals by category bar chart", "Recorded sales by category. " + text + ".");
    if (summary.categories.length > 8) chart.canvas.parentElement.classList.add("chart-canvas-wrap-long");
    const meta = metricStrip([["Upload", "#" + summary.upload_id], ["Categories", W.formatNumber(summary.categories.length, 0)]]);
    meta.classList.add("metric-strip-two");
    categoriesContainer.replaceChildren(meta, chart.frame);
    if (!window.RetailIQCharts.create(chart.canvas, {
      type: "bar",
      indexAxis: "y",
      labels: summary.categories.map(function (category) { return category.family; }),
      datasets: [{ label: "Recorded sales", data: summary.categories.map(function (category) { return category.total_sales; }), tone: "primaryMid" }],
      xTitle: "Recorded sales",
      interactionMode: "nearest",
    })) showChartUnavailable(chart);
  }

  function renderForecast(summary) {
    clearCharts(forecastContainer);
    if (!summary.forecast_run_id || !summary.families.length) {
      W.setState(forecastContainer, { kind: "empty", title: "No forecast summary", message: "Select or generate a forecast run to view category demand totals.", action: actionLink("/forecasts", "Go to forecasts") });
      return;
    }
    const metrics = metricStrip([
      ["Run", "#" + summary.forecast_run_id],
      ["Horizon", summary.horizon + " days"],
      ["Categories", W.formatNumber(summary.families_forecast, 0)],
      ["Total predicted demand", W.formatNumber(summary.total_predicted_demand)],
    ]);
    const text = summary.families.map(function (family) { return family.family + ": " + W.formatNumber(family.total_predicted_sales); }).join("; ");
    const chart = chartFrame("Predicted demand totals by category bar chart", "Forecast from " + W.formatDateOnly(summary.forecast_start_date) + " to " + W.formatDateOnly(summary.forecast_end_date) + ". " + text + ".");
    if (summary.families.length > 8) chart.canvas.parentElement.classList.add("chart-canvas-wrap-long");
    const rows = summary.families.map(function (family) { return [
      { value: family.family, className: "table-primary" },
      { value: W.formatNumber(family.total_predicted_sales), className: "numeric" },
      { value: W.formatNumber(family.average_daily_predicted_sales), className: "numeric" },
      { value: W.formatNumber(family.minimum_daily_prediction), className: "numeric" },
      { value: W.formatNumber(family.maximum_daily_prediction), className: "numeric" },
    ]; });
    const table = dataTable("Forecast summary by category", ["Category", "Total demand", "Daily average", "Daily minimum", "Daily maximum"], rows);
    forecastContainer.replaceChildren(metrics, chart.frame, table);
    if (!window.RetailIQCharts.create(chart.canvas, {
      type: "bar", indexAxis: "y",
      labels: summary.families.map(function (family) { return family.family; }),
      datasets: [{ label: "Predicted demand", data: summary.families.map(function (family) { return family.total_predicted_sales; }), tone: "primaryDeep" }],
      xTitle: "Predicted demand", interactionMode: "nearest",
    })) showChartUnavailable(chart);
  }

  function renderStock(summary) {
    if (!summary.forecast_run_id) {
      W.setState(stockContainer, { kind: "empty", title: "No stock summary", message: "A forecast run is required before inventory can be classified.", action: actionLink("/stock-intelligence", "Go to stock intelligence") });
      return;
    }
    const counts = W.element("div", "status-counts analytics-status-counts");
    ["UNDERSTOCK", "SUFFICIENT", "OVERSTOCK", "INVENTORY_REQUIRED"].forEach(function (status) { const item = W.element("div"); item.append(W.statusBadge(status), W.element("strong", "numeric", W.formatNumber(summary.status_counts[status] || 0, 0))); counts.append(item); });
    const context = W.element("p", "chart-summary", "Forecast run #" + summary.forecast_run_id + " · " + summary.horizon + " days · overstock multiplier " + W.formatNumber(summary.overstock_multiplier) + ". This is a configurable prototype rule.");
    const rows = summary.families.map(function (family) { return [
      { value: family.family, className: "table-primary" },
      { value: W.formatNumber(family.current_stock), className: "numeric" },
      { value: W.formatNumber(family.forecasted_demand), className: "numeric" },
      { value: W.formatNumber(family.stock_difference), className: "numeric" },
      { value: family.coverage_ratio === null ? "—" : W.formatNumber(family.coverage_ratio) + "×", className: "numeric" },
      { node: W.statusBadge(family.status) },
    ]; });
    stockContainer.replaceChildren(counts, context, dataTable("Stock classifications by category", ["Category", "Current stock", "Forecast demand", "Difference", "Coverage", "Status"], rows));
  }

  function renderAnomalies(summary) {
    if (!summary.upload_id) {
      W.setState(anomalyContainer, { kind: "empty", title: "No eligible anomaly summary", message: "The selected upload needs sufficient supported-category history for residual analysis.", action: actionLink("/anomalies", "Go to anomalies") });
      return;
    }
    const metrics = metricStrip([
      ["Upload", "#" + summary.upload_id],
      ["Observations analysed", W.formatNumber(summary.total_observations_analysed, 0)],
      ["Anomalies", W.formatNumber(summary.total_anomalies, 0)],
      ["Anomaly rate", W.formatPercent(summary.anomaly_rate)],
    ]);
    const context = W.element("p", "chart-summary", "Method: " + summary.method.replaceAll("_", " ") + " · |z| threshold " + W.formatNumber(summary.z_score_threshold) + ". Unusual residuals do not establish a cause.");
    const rows = summary.family_summaries.map(function (family) { return [
      { value: family.family, className: "table-primary" },
      { value: W.formatNumber(family.observations_analysed, 0), className: "numeric" },
      { value: W.formatNumber(family.anomaly_count, 0), className: "numeric" },
      { value: W.formatPercent(family.anomaly_rate), className: "numeric" },
    ]; });
    anomalyContainer.replaceChildren(metrics, context, dataTable("Anomaly summary by category", ["Category", "Observations analysed", "Anomalies", "Rate"], rows));
  }

  function anomalyError(error) {
    if (error.status === 422) {
      const reasons = error.data && error.data.excluded_families ? error.data.excluded_families.map(function (item) { return item.family + ": " + item.reason; }).join(" ") : W.errorMessage(error);
      W.setState(anomalyContainer, { kind: "empty", title: "No eligible categories", message: reasons });
      return;
    }
    W.setState(anomalyContainer, { kind: "error", title: "Anomaly summary unavailable", message: W.errorMessage(error) });
  }

  async function loadSales(uploadId, family) {
    const version = ++salesVersion;
    clearCharts(salesContainer);
    W.setState(salesContainer, { kind: "loading", title: "Loading sales trend", message: "Aggregating daily historical sales…" });
    let path = "/analytics/sales-trends?upload_id=" + encodeURIComponent(uploadId);
    if (family) path += "&family=" + encodeURIComponent(family);
    try { const response = await window.RetailIQ.api.request(path); if (version === salesVersion) renderSales(response.sales_trends); }
    catch (error) { if (version === salesVersion) W.setState(salesContainer, { kind: "error", title: "Sales trend unavailable", message: W.errorMessage(error) }); }
  }

  async function loadUploadAnalytics() {
    const uploadId = uploadSelect.value;
    const version = ++uploadVersion;
    salesVersion += 1;
    if (!uploadId) {
      fillFamilies([]);
      [salesContainer, categoriesContainer, anomalyContainer].forEach(function (container) { W.setState(container, { kind: "empty", title: "No upload selected", message: "Upload historical sales data to enable this analysis.", action: actionLink("/uploads", "Go to uploads") }); });
      return;
    }
    familySelect.disabled = true;
    familySelect.replaceChildren(W.element("option", "", "Loading categories…"));
    clearCharts(salesContainer);
    clearCharts(categoriesContainer);
    W.setState(salesContainer, { kind: "loading", title: "Loading sales trend", message: "Aggregating daily historical sales…" });
    W.setState(categoriesContainer, { kind: "loading", title: "Loading category breakdown", message: "Aggregating sales by category…" });
    W.setState(anomalyContainer, { kind: "loading", title: "Loading anomaly summary", message: "Analysing historical residuals…" });
    const responses = await Promise.allSettled([
      window.RetailIQ.api.request("/analytics/sales-trends?upload_id=" + encodeURIComponent(uploadId)),
      window.RetailIQ.api.request("/analytics/categories?upload_id=" + encodeURIComponent(uploadId)),
      window.RetailIQ.api.request("/analytics/anomaly-summary?upload_id=" + encodeURIComponent(uploadId)),
    ]);
    if (version !== uploadVersion) return;
    if (responses[0].status === "fulfilled") renderSales(responses[0].value.sales_trends); else W.setState(salesContainer, { kind: "error", title: "Sales trend unavailable", message: W.errorMessage(responses[0].reason) });
    if (responses[1].status === "fulfilled") renderCategories(responses[1].value.category_summary); else { fillFamilies([]); W.setState(categoriesContainer, { kind: "error", title: "Category breakdown unavailable", message: W.errorMessage(responses[1].reason) }); }
    if (responses[2].status === "fulfilled") renderAnomalies(responses[2].value.anomaly_summary); else anomalyError(responses[2].reason);
  }

  async function loadForecastAnalytics() {
    const runId = forecastSelect.value;
    const version = ++forecastVersion;
    if (!runId) {
      clearCharts(forecastContainer);
      W.setState(forecastContainer, { kind: "empty", title: "No forecast selected", message: "Generate a forecast run to enable forecast analytics.", action: actionLink("/forecasts", "Go to forecasts") });
      W.setState(stockContainer, { kind: "empty", title: "No stock summary", message: "Stock classifications require a forecast run." });
      return;
    }
    clearCharts(forecastContainer);
    W.setState(forecastContainer, { kind: "loading", title: "Loading forecast summary", message: "Retrieving category demand statistics…" });
    W.setState(stockContainer, { kind: "loading", title: "Loading stock summary", message: "Comparing current inventory with predicted demand…" });
    const responses = await Promise.allSettled([
      window.RetailIQ.api.request("/analytics/forecast-summary?forecast_run_id=" + encodeURIComponent(runId)),
      window.RetailIQ.api.request("/analytics/stock-summary?forecast_run_id=" + encodeURIComponent(runId)),
    ]);
    if (version !== forecastVersion) return;
    if (responses[0].status === "fulfilled") renderForecast(responses[0].value.forecast_summary); else W.setState(forecastContainer, { kind: "error", title: "Forecast summary unavailable", message: W.errorMessage(responses[0].reason) });
    if (responses[1].status === "fulfilled") renderStock(responses[1].value.stock_summary); else W.setState(stockContainer, { kind: "error", title: "Stock summary unavailable", message: W.errorMessage(responses[1].reason) });
  }

  async function initialise() {
    [salesContainer, categoriesContainer, forecastContainer, stockContainer, anomalyContainer].forEach(function (container) { W.setState(container, { kind: "loading", title: "Loading analytics", message: "Retrieving tenant-owned data…" }); });
    try {
      const responses = await Promise.all([window.RetailIQ.api.request("/uploads"), window.RetailIQ.api.request("/forecasts")]);
      fillUploads(responses[0].uploads || []); fillForecastRuns(responses[1].forecast_runs || []);
      await Promise.all([loadUploadAnalytics(), loadForecastAnalytics()]);
    } catch (error) {
      fillUploads([]); fillForecastRuns([]); fillFamilies([]);
      [salesContainer, categoriesContainer, forecastContainer, stockContainer, anomalyContainer].forEach(function (container) { W.setState(container, { kind: "error", title: "Analytics unavailable", message: W.errorMessage(error) }); });
    }
  }

  uploadSelect.addEventListener("change", loadUploadAnalytics);
  familySelect.addEventListener("change", function () { if (uploadSelect.value) loadSales(uploadSelect.value, familySelect.value); });
  forecastSelect.addEventListener("change", loadForecastAnalytics);
  W.onSessionReady(initialise);
})();
