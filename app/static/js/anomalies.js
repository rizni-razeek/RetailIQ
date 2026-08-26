(function () {
  "use strict";

  const W = window.RetailIQWorkspace;
  const form = document.querySelector("[data-anomaly-form]");
  const select = document.querySelector("[name='upload_id']");
  const results = document.querySelector("[data-anomaly-results]");
  const errorBox = document.querySelector("[data-form-error]");
  const submit = document.querySelector("[data-submit]");

  function fillUploads(uploads) {
    select.replaceChildren(); const prompt = W.element("option", "", uploads.length ? "Select an upload" : "No uploads available"); prompt.value = ""; select.append(prompt);
    uploads.forEach(function (upload) { const option = W.element("option", "", "#" + upload.id + " · " + upload.original_filename + " · " + W.formatNumber(upload.row_count, 0) + " rows"); option.value = upload.id; select.append(option); });
  }

  function table(headers, rows) {
    const wrapper = W.element("div", "table-scroll"); const node = W.element("table", "data-table"); const thead = W.element("thead"); const hr = W.element("tr"); headers.forEach(function (header) { hr.append(W.element("th", "", header)); }); thead.append(hr); const tbody = W.element("tbody"); rows.forEach(function (cells) { const row = W.element("tr"); cells.forEach(function (cell) { row.append(W.element("td", cell.numeric ? "numeric" : cell.primary ? "table-primary" : "", cell.value)); }); tbody.append(row); }); node.append(thead, tbody); W.configureTable(wrapper, node, headers.join(", ")); wrapper.append(node); return wrapper;
  }

  function renderAnalysis(data) {
    const header = W.element("div", "result-summary"); const copy = W.element("div"); const uploadMeta = W.element("p", "quiet-meta"); uploadMeta.append(document.createTextNode("Upload "), W.element("span", "numeric", "#" + data.upload_id)); copy.append(W.element("h3", "", "Residual Z-score analysis"), uploadMeta, W.element("p", "", "Threshold: |z| ≥ " + W.formatNumber(data.z_score_threshold) + " · Historical one-step model residuals")); header.append(copy);
    const metrics = W.element("dl", "metric-strip"); [["Observations", W.formatNumber(data.total_observations_analysed, 0)], ["Anomalies", W.formatNumber(data.total_anomalies, 0)], ["Anomaly rate", W.formatPercent(data.anomaly_rate)], ["Method", String(data.method || "").replaceAll("_", " ")]].forEach(function (item) { const group = W.element("div"); group.append(W.element("dt", "", item[0]), W.element("dd", item[0] === "Method" ? "" : "numeric", item[1])); metrics.append(group); });
    const content = document.createDocumentFragment(); content.append(header, metrics);
    if (data.excluded_families && data.excluded_families.length) {
      const excluded = W.element("section", "exclusion-list"); excluded.append(W.element("h4", "", "Excluded categories")); const ul = W.element("ul"); data.excluded_families.forEach(function (item) { const li = W.element("li"); li.append(W.element("strong", "", item.family), document.createTextNode(" — " + item.reason)); ul.append(li); }); excluded.append(ul); content.append(excluded);
    }
    if (data.family_summaries && data.family_summaries.length) {
      content.append(W.element("h4", "subsection-title", "Per-category summary"));
      content.append(table(["Category", "Analysed", "Anomalies", "Rate", "Residual mean", "Residual std"], data.family_summaries.map(function (family) { return [{ value: family.family, primary: true }, { value: W.formatNumber(family.observations_analysed, 0), numeric: true }, { value: W.formatNumber(family.anomaly_count, 0), numeric: true }, { value: W.formatPercent(family.anomaly_rate), numeric: true }, { value: W.formatNumber(family.residual_mean), numeric: true }, { value: W.formatNumber(family.residual_std), numeric: true }]; })));
      data.family_summaries.filter(function (family) { return family.z_score_note; }).forEach(function (family) {
        const note = W.element("p", "interpretation-note");
        note.append(W.element("strong", "", family.family + ": "), document.createTextNode(family.z_score_note));
        content.append(note);
      });
    }
    content.append(W.element("h4", "subsection-title", "Anomaly records"));
    if (!data.anomalies || !data.anomalies.length) {
      const empty = W.element("div"); W.setState(empty, { kind: "empty", title: "No anomalies found", message: "No analysed observation met the configured residual Z-score threshold." }); content.append(empty);
    } else {
      content.append(table(["Date", "Category", "Actual sales", "Predicted sales", "Residual", "Z-score"], data.anomalies.map(function (item) { return [{ value: item.date }, { value: item.family, primary: true }, { value: W.formatNumber(item.actual_sales), numeric: true }, { value: W.formatNumber(item.predicted_sales), numeric: true }, { value: W.formatNumber(item.residual), numeric: true }, { value: W.formatNumber(item.z_score), numeric: true }]; })));
    }
    results.replaceChildren(content);
  }

  async function loadUploads() {
    W.setState(results, { kind: "empty", title: "Choose a historical upload", message: "Anomaly summaries and records will appear here after analysis." });
    try { const response = await window.RetailIQ.api.request("/uploads"); fillUploads(response.uploads || []); }
    catch (error) { fillUploads([]); W.setState(results, { kind: "error", title: "Uploads unavailable", message: W.errorMessage(error) }); }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault(); window.RetailIQUI.clearInlineError(errorBox); const id = Number(select.value);
    if (!Number.isInteger(id) || id < 1) { window.RetailIQUI.showInlineError(errorBox, "Select a historical upload."); return; }
    window.RetailIQUI.setButtonLoading(submit, true, "Analysing history…"); W.setState(results, { kind: "loading", title: "Running anomaly analysis", message: "Building historical features and evaluating residuals…" });
    try { const response = await window.RetailIQ.api.request("/anomalies", { method: "POST", body: { upload_id: id } }); renderAnalysis(response.anomaly_analysis); window.RetailIQUI.showToast("Anomaly analysis completed.", "success"); }
    catch (error) { window.RetailIQUI.showInlineError(errorBox, W.errorMessage(error)); W.setState(results, { kind: "error", title: "Analysis unavailable", message: W.errorMessage(error) }); }
    finally { window.RetailIQUI.setButtonLoading(submit, false, "Run anomaly analysis"); }
  });

  W.onSessionReady(loadUploads);
})();
