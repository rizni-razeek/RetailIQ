(function () {
  "use strict";

  const W = window.RetailIQWorkspace;
  const form = document.querySelector("[data-forecast-form]");
  const uploadSelect = document.querySelector("[name='upload_id']");
  const list = document.querySelector("[data-forecast-list]");
  const detail = document.querySelector("[data-forecast-detail]");
  const errorBox = document.querySelector("[data-form-error]");
  const submit = document.querySelector("[data-submit]");

  function fillUploads(uploads) {
    const selected = uploadSelect.value;
    uploadSelect.replaceChildren();
    const prompt = W.element("option", "", uploads.length ? "Select an upload" : "No uploads available"); prompt.value = ""; uploadSelect.append(prompt);
    uploads.forEach(function (upload) {
      const option = W.element("option", "", "#" + upload.id + " · " + upload.original_filename + " · " + W.formatNumber(upload.row_count, 0) + " rows");
      option.value = upload.id; uploadSelect.append(option);
    });
    if (Array.from(uploadSelect.options).some(function (option) { return option.value === selected; })) uploadSelect.value = selected;
  }

  function exclusionsSection(exclusions) {
    if (!exclusions || !exclusions.length) return null;
    const section = W.element("section", "exclusion-list"); section.append(W.element("h4", "", "Excluded categories"));
    const listNode = W.element("ul");
    exclusions.forEach(function (item) { const li = W.element("li"); li.append(W.element("strong", "", item.family), document.createTextNode(" — " + item.reason)); listNode.append(li); });
    section.append(listNode); return section;
  }

  function renderForecast(run) {
    const heading = W.element("div", "detail-panel-heading"); const title = W.element("div");
    const runMeta = W.element("p", "quiet-meta");
    runMeta.append(document.createTextNode("Forecast run "), W.element("span", "numeric", "#" + run.id));
    title.append(W.element("h3", "", run.horizon + "-day demand forecast"), runMeta);
    const sourceMeta = W.element("span", "quiet-meta");
    sourceMeta.append(document.createTextNode("Upload "), W.element("span", "numeric", "#" + run.upload_id));
    heading.append(title, sourceMeta);
    const total = (run.families || []).reduce(function (sum, family) { return sum + Number(family.total_predicted_sales || 0); }, 0);
    const metrics = W.element("dl", "metric-strip");
    [["Period", run.forecast_start_date + " – " + run.forecast_end_date], ["Categories", W.formatNumber(run.families_forecast, 0)], ["Total demand", W.formatNumber(total)], ["Generated", W.formatDate(run.generated_at, true)]].forEach(function (item) {
      const group = W.element("div"); group.append(W.element("dt", "", item[0]), W.element("dd", item[0] === "Total demand" || item[0] === "Categories" ? "numeric" : "", item[1])); metrics.append(group);
    });
    const content = document.createDocumentFragment(); content.append(heading, metrics);
    const exclusions = exclusionsSection(run.excluded_families); if (exclusions) content.append(exclusions);
    if (run.families && run.families.length) {
      const families = W.element("div", "family-forecast-list");
      run.families.forEach(function (family, index) {
        const panel = W.element("details", "family-forecast"); if (index === 0) panel.open = true;
        const summary = W.element("summary"); summary.append(W.element("span", "", family.family), W.element("span", "numeric", W.formatNumber(family.total_predicted_sales) + " total")); panel.append(summary);
        const wrapper = W.element("div", "table-scroll"); const table = W.element("table", "data-table compact-table");
        const thead = W.element("thead"); const hr = W.element("tr"); ["Forecast date", "Predicted sales"].forEach(function (label) { hr.append(W.element("th", "", label)); }); thead.append(hr);
        const tbody = W.element("tbody"); (family.predictions || []).forEach(function (prediction) { const row = W.element("tr"); row.append(W.element("td", "", prediction.date), W.element("td", "numeric", W.formatNumber(prediction.predicted_sales))); tbody.append(row); });
        table.append(thead, tbody); W.configureTable(wrapper, table, family.family + " daily forecast"); wrapper.append(table); panel.append(wrapper); families.append(panel);
      });
      content.append(families);
    }
    detail.replaceChildren(content); detail.hidden = false;
  }

  async function showRun(id) {
    detail.hidden = false; W.setState(detail, { kind: "loading", title: "Loading forecast", message: "Retrieving persisted predictions…" });
    try { const response = await window.RetailIQ.api.request("/forecasts/" + id); renderForecast(response.forecast_run); W.scrollToElement(detail, "start"); }
    catch (error) { W.setState(detail, { kind: "error", title: "Forecast unavailable", message: W.errorMessage(error) }); }
  }

  function renderRuns(runs) {
    if (!runs.length) { W.setState(list, { kind: "empty", title: "No forecast runs", message: "Choose an uploaded dataset above to generate your first forecast." }); return; }
    const wrapper = W.element("div", "table-scroll"); const table = W.element("table", "data-table"); const thead = W.element("thead"); const hr = W.element("tr");
    ["Run", "Source", "Horizon", "Forecast period", "Categories", "Generated", ""].forEach(function (label) { hr.append(W.element("th", "", label)); }); thead.append(hr);
    const tbody = W.element("tbody"); runs.forEach(function (run) {
      const row = W.element("tr"); row.append(W.element("td", "table-primary numeric", "#" + run.id), W.element("td", "numeric", "#" + run.upload_id), W.element("td", "numeric", run.horizon + " days"), W.element("td", "", run.forecast_start_date + " – " + run.forecast_end_date), W.element("td", "numeric", W.formatNumber(run.families_forecast, 0)), W.element("td", "", W.formatDate(run.generated_at, true)));
      const action = W.element("td", "table-action"); const button = W.element("button", "text-button", "View forecast"); button.type = "button"; button.addEventListener("click", function () { showRun(run.id); }); action.append(button); row.append(action); tbody.append(row);
    }); table.append(thead, tbody); W.configureTable(wrapper, table, "Forecast run history"); wrapper.append(table); list.replaceChildren(wrapper);
  }

  async function loadData() {
    W.setState(list, { kind: "loading", title: "Loading forecast runs", message: "Retrieving persisted forecast history…" });
    try {
      const responses = await Promise.all([window.RetailIQ.api.request("/uploads"), window.RetailIQ.api.request("/forecasts")]);
      fillUploads(responses[0].uploads || []); renderRuns(responses[1].forecast_runs || []);
    } catch (error) { W.setState(list, { kind: "error", title: "Forecast data unavailable", message: W.errorMessage(error) }); }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault(); window.RetailIQUI.clearInlineError(errorBox);
    const uploadId = Number(uploadSelect.value); const horizon = Number(new FormData(form).get("horizon"));
    if (!Number.isInteger(uploadId) || uploadId < 1) { window.RetailIQUI.showInlineError(errorBox, "Select a source upload."); return; }
    window.RetailIQUI.setButtonLoading(submit, true, "Generating forecast…");
    try {
      const response = await window.RetailIQ.api.request("/forecasts", { method: "POST", body: { upload_id: uploadId, horizon: horizon } });
      renderForecast(response.forecast_run); window.RetailIQUI.showToast("Forecast run generated and saved.", "success"); await loadData();
    } catch (error) {
      window.RetailIQUI.showInlineError(errorBox, W.errorMessage(error));
      if (error.data && error.data.excluded_families) { detail.replaceChildren(exclusionsSection(error.data.excluded_families)); detail.hidden = false; }
    } finally { window.RetailIQUI.setButtonLoading(submit, false, "Generate forecast"); }
  });

  document.querySelector("[data-refresh]").addEventListener("click", loadData);
  W.onSessionReady(loadData);
})();
