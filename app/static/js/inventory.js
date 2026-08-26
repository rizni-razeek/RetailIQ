(function () {
  "use strict";

  const W = window.RetailIQWorkspace;
  const form = document.querySelector("[data-inventory-form]");
  const list = document.querySelector("[data-inventory-list]");
  const errorBox = document.querySelector("[data-form-error]");
  const submit = document.querySelector("[data-submit]");
  const familyInput = document.querySelector("[name='family']");
  const stockInput = document.querySelector("[name='current_stock']");
  const familyOptions = document.querySelector("[data-family-options]");

  function renderInventory(records) {
    familyOptions.replaceChildren();
    records.forEach(function (record) { const option = document.createElement("option"); option.value = record.family; familyOptions.append(option); });
    if (!records.length) {
      W.setState(list, { kind: "empty", title: "No inventory recorded", message: "Add the current stock for a category using the form above." }); return;
    }
    const wrapper = W.element("div", "table-scroll"); const table = W.element("table", "data-table");
    const thead = W.element("thead"); const hr = W.element("tr");
    ["Category", "Current stock", "Last updated", ""].forEach(function (label) { hr.append(W.element("th", "", label)); }); thead.append(hr);
    const tbody = W.element("tbody");
    records.forEach(function (record) {
      const row = W.element("tr");
      row.append(W.element("td", "table-primary", record.family), W.element("td", "numeric", W.formatNumber(record.current_stock)), W.element("td", "", W.formatDate(record.updated_at, true)));
      const action = W.element("td", "table-action"); const button = W.element("button", "text-button", "Update"); button.type = "button";
      button.addEventListener("click", function () { familyInput.value = record.family; stockInput.value = record.current_stock; stockInput.focus(); });
      action.append(button); row.append(action); tbody.append(row);
    });
    table.append(thead, tbody); W.configureTable(wrapper, table, "Current inventory by category"); wrapper.append(table); list.replaceChildren(wrapper);
  }

  async function loadInventory() {
    W.setState(list, { kind: "loading", title: "Loading inventory", message: "Retrieving current category stock…" });
    try { const response = await window.RetailIQ.api.request("/inventory"); renderInventory(response.inventory || []); }
    catch (error) { W.setState(list, { kind: "error", title: "Inventory unavailable", message: W.errorMessage(error) }); }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault(); window.RetailIQUI.clearInlineError(errorBox);
    const family = familyInput.value.trim(); const stock = Number(stockInput.value);
    if (!family) { window.RetailIQUI.showInlineError(errorBox, "Enter a category name."); return; }
    if (stockInput.value === "" || !Number.isFinite(stock) || stock < 0) { window.RetailIQUI.showInlineError(errorBox, "Current stock must be a non-negative number."); return; }
    window.RetailIQUI.setButtonLoading(submit, true, "Saving…");
    try {
      await window.RetailIQ.api.request("/inventory", { method: "POST", body: { family: family, current_stock: stock } });
      window.RetailIQUI.showToast("Inventory saved for " + family.toUpperCase() + ".", "success");
      form.reset(); await loadInventory();
    } catch (error) { window.RetailIQUI.showInlineError(errorBox, W.errorMessage(error)); }
    finally { window.RetailIQUI.setButtonLoading(submit, false, "Save inventory"); }
  });

  document.querySelector("[data-refresh]").addEventListener("click", loadInventory);
  W.onSessionReady(loadInventory);
})();
