(function () {
  "use strict";

  const W = window.RetailIQWorkspace;
  const form = document.querySelector("[data-upload-form]");
  const fileInput = document.querySelector("[data-file-input]");
  const fileLabel = document.querySelector("[data-file-label]");
  const zone = document.querySelector("[data-upload-zone]");
  const list = document.querySelector("[data-upload-list]");
  const detail = document.querySelector("[data-upload-detail]");
  const result = document.querySelector("[data-upload-result]");
  const errorBox = document.querySelector("[data-form-error]");
  const submit = document.querySelector("[data-submit]");

  function addCell(row, value, className) {
    const cell = W.element("td", className, value);
    row.append(cell);
  }

  function renderSummary(target, upload) {
    const summary = upload.summary || {};
    const heading = W.element("div", "detail-panel-heading");
    const titleWrap = W.element("div");
    const uploadMeta = W.element("p", "quiet-meta");
    uploadMeta.append(document.createTextNode("Upload "), W.element("span", "numeric", "#" + upload.id));
    titleWrap.append(W.element("h3", "", upload.original_filename), uploadMeta);
    heading.append(titleWrap, W.statusBadge(upload.status));
    const values = W.element("dl", "metric-strip");
    [
      ["Rows", W.formatNumber(upload.row_count, 0)],
      ["Date range", summary.date_from && summary.date_to ? summary.date_from + " – " + summary.date_to : "—"],
      ["Categories", W.formatNumber(summary.family_count, 0)],
      ["Total sales", W.formatNumber(summary.total_sales)],
    ].forEach(function (item) {
      const group = W.element("div");
      group.append(W.element("dt", "", item[0]), W.element("dd", "numeric", item[1]));
      values.append(group);
    });
    target.replaceChildren(heading, values);
    target.hidden = false;
  }

  async function showDetail(id) {
    detail.hidden = false;
    W.setState(detail, { kind: "loading", title: "Loading upload", message: "Retrieving the validated dataset summary…" });
    try {
      const response = await window.RetailIQ.api.request("/uploads/" + id);
      renderSummary(detail, response.upload);
      W.scrollToElement(detail, "nearest");
    } catch (error) {
      W.setState(detail, { kind: "error", title: "Upload details unavailable", message: W.errorMessage(error) });
    }
  }

  function renderUploads(uploads) {
    if (!uploads.length) {
      W.setState(list, { kind: "empty", title: "No sales history yet", message: "Upload a CSV above to create your first tenant-owned dataset." });
      return;
    }
    const wrapper = W.element("div", "table-scroll");
    const table = W.element("table", "data-table");
    const thead = W.element("thead");
    const headRow = W.element("tr");
    ["File", "Rows", "Uploaded", "Status", ""].forEach(function (label) { headRow.append(W.element("th", "", label)); });
    thead.append(headRow);
    const tbody = W.element("tbody");
    uploads.forEach(function (upload) {
      const row = W.element("tr");
      addCell(row, upload.original_filename, "table-primary");
      addCell(row, W.formatNumber(upload.row_count, 0), "numeric");
      addCell(row, W.formatDate(upload.uploaded_at, true));
      const statusCell = W.element("td"); statusCell.append(W.statusBadge(upload.status)); row.append(statusCell);
      const actionCell = W.element("td", "table-action");
      const button = W.element("button", "text-button", "View details"); button.type = "button";
      button.addEventListener("click", function () { showDetail(upload.id); });
      actionCell.append(button); row.append(actionCell); tbody.append(row);
    });
    table.append(thead, tbody); W.configureTable(wrapper, table, "Upload history"); wrapper.append(table); list.replaceChildren(wrapper);
  }

  async function loadUploads() {
    W.setState(list, { kind: "loading", title: "Loading uploads", message: "Retrieving your business datasets…" });
    try {
      const response = await window.RetailIQ.api.request("/uploads");
      renderUploads(response.uploads || []);
    } catch (error) {
      W.setState(list, { kind: "error", title: "Uploads unavailable", message: W.errorMessage(error) });
    }
  }

  function selectFile(file) {
    if (!file) return;
    const transfer = new DataTransfer(); transfer.items.add(file); fileInput.files = transfer.files;
    fileLabel.textContent = file.name;
    zone.classList.add("has-file");
  }

  ["dragenter", "dragover"].forEach(function (name) {
    zone.addEventListener(name, function (event) { event.preventDefault(); zone.classList.add("is-dragging"); });
  });
  ["dragleave", "drop"].forEach(function (name) {
    zone.addEventListener(name, function (event) { event.preventDefault(); zone.classList.remove("is-dragging"); });
  });
  zone.addEventListener("drop", function (event) { if (event.dataTransfer.files.length) selectFile(event.dataTransfer.files[0]); });
  fileInput.addEventListener("change", function () { if (fileInput.files.length) selectFile(fileInput.files[0]); });

  form.addEventListener("submit", async function (event) {
    event.preventDefault(); window.RetailIQUI.clearInlineError(errorBox); result.hidden = true;
    if (!fileInput.files.length) { window.RetailIQUI.showInlineError(errorBox, "Choose a CSV file to upload."); return; }
    const file = fileInput.files[0];
    if (!file.name.toLowerCase().endsWith(".csv")) { window.RetailIQUI.showInlineError(errorBox, "The selected file must use the .csv extension."); return; }
    const body = new FormData(); body.append("file", file);
    window.RetailIQUI.setButtonLoading(submit, true, "Uploading and validating…");
    try {
      const response = await window.RetailIQ.api.request("/uploads", { method: "POST", body: body });
      renderSummary(result, response.upload); result.hidden = false;
      window.RetailIQUI.showToast("Sales history uploaded successfully.", "success");
      form.reset(); fileLabel.textContent = "Choose a CSV or drop it here"; zone.classList.remove("has-file");
      await loadUploads();
    } catch (error) {
      window.RetailIQUI.showInlineError(errorBox, W.errorMessage(error));
    } finally { window.RetailIQUI.setButtonLoading(submit, false, "Upload and validate"); }
  });

  document.querySelector("[data-refresh]").addEventListener("click", loadUploads);
  W.onSessionReady(loadUploads);
})();
