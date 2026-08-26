(function () {
  "use strict";

  const W = window.RetailIQWorkspace;
  const metricsContainer = document.querySelector("[data-dashboard-metrics]");
  const salesContainer = document.querySelector("[data-dashboard-sales]");
  const forecastContainer = document.querySelector("[data-dashboard-forecast]");
  const stockContainer = document.querySelector("[data-dashboard-stock]");
  const anomalyContainer = document.querySelector("[data-dashboard-anomalies]");
  const activityContainer = document.querySelector("[data-dashboard-activity]");

  function clearCharts(container) {
    container.querySelectorAll("canvas").forEach(function (canvas) {
      window.RetailIQCharts.destroy(canvas);
    });
  }

  function link(path, label) {
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

  function renderMetrics(overview) {
    const list = W.element("dl", "overview-metrics-list");
    [
      ["Historical uploads", overview.total_uploads],
      ["Sales records", overview.total_historical_sales_records],
      ["Categories", overview.distinct_families],
      ["Forecast runs", overview.total_forecast_runs],
    ].forEach(function (item) {
      const metric = W.element("div", "overview-metric");
      metric.append(W.element("dt", "", item[0]), W.element("dd", "numeric", W.formatNumber(item[1], 0)));
      list.append(metric);
    });
    metricsContainer.replaceChildren(list);
  }

  function renderSales(trends) {
    clearCharts(salesContainer);
    if (!trends.data.length) {
      W.setState(salesContainer, { kind: "empty", title: "No sales history", message: "Upload a compatible historical CSV to establish the sales trend.", action: link("/uploads", "Go to uploads") });
      return;
    }
    const summary = "Recorded sales total " + W.formatNumber(trends.total_sales) + " from " + W.formatDateOnly(trends.date_from) + " to " + W.formatDateOnly(trends.date_to) + ".";
    const chart = chartFrame("Daily historical sales line chart", summary);
    salesContainer.replaceChildren(chart.frame);
    if (!window.RetailIQCharts.create(chart.canvas, {
      type: "line",
      labels: trends.data.map(function (item) { return item.date; }),
      datasets: [{ label: "Recorded sales", data: trends.data.map(function (item) { return item.sales; }), tone: "primary", fill: false }],
      yTitle: "Sales volume",
      maxTicks: 7,
    })) {
      showChartUnavailable(chart);
    }
  }

  function renderForecast(summary) {
    clearCharts(forecastContainer);
    if (!summary.forecast_run_id || !summary.families.length) {
      W.setState(forecastContainer, { kind: "empty", title: "No forecast runs", message: "Generate a forecast from an eligible upload to compare predicted category demand.", action: link("/forecasts", "Generate a forecast") });
      return;
    }
    document.querySelector("[data-forecast-scope]").textContent = "Run #" + summary.forecast_run_id + " · " + summary.horizon + " days · " + summary.forecast_start_date + " – " + summary.forecast_end_date;
    const accessible = summary.families.map(function (family) { return family.family + ": " + W.formatNumber(family.total_predicted_sales); }).join("; ");
    const chart = chartFrame("Predicted demand totals by category bar chart", "Total predicted demand " + W.formatNumber(summary.total_predicted_demand) + ". " + accessible + ".");
    if (summary.families.length > 8) chart.canvas.parentElement.classList.add("chart-canvas-wrap-long");
    forecastContainer.replaceChildren(chart.frame);
    if (!window.RetailIQCharts.create(chart.canvas, {
      type: "bar",
      indexAxis: "y",
      labels: summary.families.map(function (family) { return family.family; }),
      datasets: [{ label: "Predicted demand", data: summary.families.map(function (family) { return family.total_predicted_sales; }), tone: "primaryMid" }],
      xTitle: "Predicted demand",
      interactionMode: "nearest",
    })) {
      showChartUnavailable(chart);
    }
  }

  function renderStock(overview) {
    if (!overview.latest_forecast_run_id) {
      W.setState(stockContainer, { kind: "empty", title: "No stock comparison", message: "A persisted forecast run is required before stock status can be classified.", action: link("/forecasts", "View forecasts") });
      return;
    }
    const list = W.element("div", "status-summary-list");
    ["UNDERSTOCK", "SUFFICIENT", "OVERSTOCK", "INVENTORY_REQUIRED"].forEach(function (status) {
      const row = W.element("div");
      row.append(W.statusBadge(status), W.element("strong", "numeric", W.formatNumber(overview.stock_status_counts[status] || 0, 0)));
      list.append(row);
    });
    const context = W.element("p", "chart-summary", "Classifications from forecast run #" + overview.latest_forecast_run_id + ".");
    const action = link("/stock-intelligence", "Review stock details"); action.className = "text-link";
    stockContainer.replaceChildren(list, context, action);
  }

  function renderAnomalies(overview) {
    const anomaly = overview.anomaly_summary;
    if (!anomaly.upload_id) {
      W.setState(anomalyContainer, { kind: "empty", title: "No eligible anomaly analysis", message: "An eligible historical upload with sufficient supported-category history is required.", action: link("/anomalies", "Review anomalies") });
      return;
    }
    const metrics = W.element("dl", "compact-metrics");
    [["Analysed", W.formatNumber(anomaly.total_observations_analysed, 0)], ["Anomalies", W.formatNumber(anomaly.total_anomalies, 0)], ["Rate", W.formatPercent(anomaly.anomaly_rate)]].forEach(function (item) {
      const group = W.element("div"); group.append(W.element("dt", "", item[0]), W.element("dd", "numeric", item[1])); metrics.append(group);
    });
    const note = W.element("p", "chart-summary", "Residual summary from upload #" + anomaly.upload_id + ". Unusual residuals do not establish a cause.");
    const action = link("/anomalies", "Open anomaly analysis"); action.className = "text-link";
    anomalyContainer.replaceChildren(metrics, note, action);
  }

  function renderActivity(uploads, runs) {
    const events = uploads.map(function (upload) {
      return { kind: "Upload", id: upload.id, detail: upload.original_filename + " · " + W.formatNumber(upload.row_count, 0) + " rows", at: upload.uploaded_at };
    }).concat(runs.map(function (run) {
      return { kind: "Forecast", id: run.id, detail: run.horizon + " days · " + W.formatNumber(run.families_forecast, 0) + " categories", at: run.generated_at };
    })).sort(function (a, b) { return new Date(b.at) - new Date(a.at); }).slice(0, 6);
    if (!events.length) {
      W.setState(activityContainer, { kind: "empty", title: "No operational activity", message: "Uploads and generated forecast runs will appear here." });
      return;
    }
    const wrapper = W.element("div", "table-scroll"); const table = W.element("table", "data-table"); const thead = W.element("thead"); const hr = W.element("tr");
    ["Activity", "Record", "Details", "Time"].forEach(function (heading) { hr.append(W.element("th", "", heading)); }); thead.append(hr);
    const tbody = W.element("tbody"); events.forEach(function (item) { const row = W.element("tr"); row.append(W.element("td", "table-primary", item.kind), W.element("td", "numeric", "#" + item.id), W.element("td", "", item.detail), W.element("td", "numeric", W.formatDate(item.at, true))); tbody.append(row); });
    table.append(thead, tbody); W.configureTable(wrapper, table, "Recent uploads and forecast runs"); wrapper.append(table); activityContainer.replaceChildren(wrapper);
  }

  function showLoading() {
    clearCharts(salesContainer);
    clearCharts(forecastContainer);
    [[metricsContainer, "Loading workspace overview"], [salesContainer, "Loading recent sales"], [forecastContainer, "Loading latest forecast"], [stockContainer, "Loading stock position"], [anomalyContainer, "Loading anomaly summary"], [activityContainer, "Loading recent activity"]].forEach(function (item) {
      W.setState(item[0], { kind: "loading", title: item[1], message: "Retrieving tenant-owned data…" });
    });
  }

  async function loadDashboard() {
    showLoading();
    const requests = await Promise.allSettled([
      window.RetailIQ.api.request("/analytics/overview"),
      window.RetailIQ.api.request("/analytics/sales-trends"),
      window.RetailIQ.api.request("/analytics/forecast-summary"),
      window.RetailIQ.api.request("/uploads"),
      window.RetailIQ.api.request("/forecasts"),
    ]);
    const overviewResult = requests[0];
    if (overviewResult.status === "fulfilled") {
      renderMetrics(overviewResult.value.overview); renderStock(overviewResult.value.overview); renderAnomalies(overviewResult.value.overview);
    } else {
      [metricsContainer, stockContainer, anomalyContainer].forEach(function (container) { W.setState(container, { kind: "error", title: "Overview unavailable", message: W.errorMessage(overviewResult.reason) }); });
    }
    if (requests[1].status === "fulfilled") renderSales(requests[1].value.sales_trends);
    else W.setState(salesContainer, { kind: "error", title: "Sales trend unavailable", message: W.errorMessage(requests[1].reason) });
    if (requests[2].status === "fulfilled") renderForecast(requests[2].value.forecast_summary);
    else W.setState(forecastContainer, { kind: "error", title: "Forecast summary unavailable", message: W.errorMessage(requests[2].reason) });
    if (requests[3].status === "fulfilled" && requests[4].status === "fulfilled") renderActivity(requests[3].value.uploads || [], requests[4].value.forecast_runs || []);
    else W.setState(activityContainer, { kind: "error", title: "Activity unavailable", message: "Recent uploads or forecast runs could not be retrieved." });
  }

  W.onSessionReady(loadDashboard);
})();
