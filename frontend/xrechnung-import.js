"use strict";

async function showXRechnungImport(partners) {
  const editor = document.getElementById("invoice-editor");
  const invoiceList = editor.nextElementSibling;

  if (invoiceList && invoiceList.classList.contains("panel")) {
    invoiceList.hidden = true;
  }

  const accounts = await api("/api/accounts");

  const suppliers = partners.filter(
    p => p.is_supplier && p.is_active !== false
  );

  const expenseAccounts = accounts.filter(
    a => a.account_type === "expense" && a.is_active !== false
  );

  let selectedFile = null;
  let preview = null;

  editor.innerHTML = `
    <div class="panel">
      <h2>XRechnung importieren</h2>
      <p class="muted">
        Die XML-Datei wird zunächst nur geprüft.
        Eine dauerhafte Speicherung erfolgt erst nach ausdrücklicher Bestätigung.
      </p>

      <label>
        XRechnung (XML)
        <input type="file" id="xr-file" accept=".xml,application/xml,text/xml">
      </label>

      <div class="form-actions">
        <button type="button" id="xr-preview">Vorschau prüfen</button>
        <button type="button" class="secondary" id="xr-cancel">Abbrechen</button>
      </div>

      <div id="xr-message" role="status"></div>
      <div id="xr-result"></div>
    </div>
  `;

  const fileInput = document.getElementById("xr-file");
  const previewButton = document.getElementById("xr-preview");
  const cancelButton = document.getElementById("xr-cancel");
  const resultElement = document.getElementById("xr-result");
  const messageElement = document.getElementById("xr-message");

  function clearPreview() {
    preview = null;
    selectedFile = null;
    resultElement.replaceChildren();
    messageElement.textContent = "";
  }

  fileInput.onchange = () => {
    clearPreview();
    selectedFile = fileInput.files[0] || null;
  };

  cancelButton.onclick = () => {
    clearPreview();
    fileInput.value = "";
    editor.replaceChildren();
    if (invoiceList) invoiceList.hidden = false;
  };

  previewButton.onclick = async () => {
    clearPreview();
    selectedFile = fileInput.files[0] || null;

    if (!selectedFile) {
      messageElement.textContent = "Bitte eine XML-Datei auswählen.";
      return;
    }

    previewButton.disabled = true;
    messageElement.textContent = "XRechnung wird geprüft …";

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch("/api/xrechnung/incoming/preview", {
        method: "POST",
        credentials: "same-origin",
        headers: {"X-Tenant-ID": String(state.tenantId)},
        body: formData
      });

      if (response.status === 401) {
        showLogin();
        throw Error("Sitzung abgelaufen. Bitte anmelden.");
      }

      const data = await response.json();

      if (!response.ok) {
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail || data)
        );
      }

      preview = data;
      messageElement.textContent =
        "KoSIT-Prüfung erfolgreich. Noch nichts gespeichert.";

      renderPreview(data);
    } catch (error) {
      messageElement.textContent = error.message;
    } finally {
      previewButton.disabled = false;
    }
  };

  function renderPreview(data) {
    const supplier = data.supplier || {};
    const customer = data.customer || {};
    const match = data.supplier_match || {};
    const duplicate = data.duplicate_check || {};

    const supplierOptions = suppliers.map(p =>
      `<option value="${esc(p.id)}"
        ${Number(match.partner_id) === p.id ? "selected" : ""}>
        ${esc(p.name)}
      </option>`
    ).join("");

    const accountOptions = expenseAccounts.map(a =>
      `<option value="${esc(a.id)}">
        ${esc(a.number)} – ${esc(a.name)}
      </option>`
    ).join("");

    const positions = (data.lines || []).map(line => `
      <tr>
        <td>${esc(line.position)}</td>
        <td>${esc(line.description)}</td>
        <td>${esc(line.quantity)}</td>
        <td>${esc(line.unit)}</td>
        <td>${euro(line.unit_net_price)}</td>
        <td>${esc(line.vat_rate)} %</td>
        <td>${euro(line.net_total)}</td>
      </tr>
    `).join("");

    resultElement.innerHTML = `
      <h3>Rechnungsvorschau</h3>

      ${duplicate.duplicate
        ? '<p class="error">Achtung: Diese Rechnung ist bereits vorhanden.</p>'
        : ""}

      <div class="grid-form">
        <div><strong>Rechnungsnummer</strong><p>${esc(data.invoice_number)}</p></div>
        <div><strong>Rechnungsdatum</strong><p>${esc(data.invoice_date)}</p></div>
        <div><strong>Fälligkeit</strong><p>${esc(data.due_date || "–")}</p></div>
        <div><strong>Format</strong><p>${esc(data.format)}</p></div>
        <div><strong>Lieferant laut XML</strong><p>${esc(supplier.name || "–")}</p></div>
        <div><strong>Lieferanten-USt-ID</strong><p>${esc(supplier.vat_id || "–")}</p></div>
        <div><strong>Rechnungsempfänger</strong><p>${esc(customer.name || "–")}</p></div>
        <div><strong>Währung</strong><p>${esc(data.currency)}</p></div>
      </div>

      <h3>Rechnungspositionen</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Pos.</th><th>Beschreibung</th><th>Menge</th>
              <th>Einheit</th><th>Einzelpreis</th><th>USt</th><th>Netto</th>
            </tr>
          </thead>
          <tbody>${positions}</tbody>
        </table>
      </div>

      <div class="invoice-totals">
        <div><span>Netto</span><strong>${euro(data.net_total)}</strong></div>
        <div><span>Umsatzsteuer</span><strong>${euro(data.tax_total)}</strong></div>
        <div class="invoice-total">
          <span>Brutto</span><strong>${euro(data.gross_total)}</strong>
        </div>
        <div><span>Zahlbetrag</span><strong>${euro(data.payable_amount)}</strong></div>
      </div>

      <div class="grid-form">
        <label>Lieferant in BUHA
          <select id="xr-supplier">
            <option value="">Bitte Lieferant auswählen</option>
            ${supplierOptions}
          </select>
        </label>

        <label>Aufwandskonto
          <select id="xr-account">
            <option value="">Bitte Aufwandskonto auswählen</option>
            ${accountOptions}
          </select>
        </label>
      </div>

      <p class="muted">
        Die Zuordnung wird erst bei der endgültigen Importbestätigung gespeichert.
      </p>

      <div class="form-actions">
        <button type="button" id="xr-confirm" disabled>
          Import bestätigen
        </button>
        <button type="button" class="secondary" id="xr-cancel-preview">
          Abbrechen
        </button>
      </div>
    `;

    document.getElementById("xr-cancel-preview").onclick =
      cancelButton.onclick;

    const confirmButton = document.getElementById("xr-confirm");
    const supplierSelect = document.getElementById("xr-supplier");
    const accountSelect = document.getElementById("xr-account");

    function updateConfirmState() {
      confirmButton.disabled =
        !data.importable ||
        duplicate.duplicate === true ||
        !selectedFile ||
        !supplierSelect.value ||
        !accountSelect.value;
    }

    supplierSelect.onchange = updateConfirmState;
    accountSelect.onchange = updateConfirmState;
    updateConfirmState();

    if (!data.importable) {
      const warning = document.createElement("p");
      warning.className = "error";
      warning.textContent =
        "Import nicht möglich: " +
        (data.import_error || "Rechnung wird nicht unterstützt.");
      resultElement.prepend(warning);
    }

    confirmButton.onclick = async () => {
      if (confirmButton.disabled || !selectedFile || !preview) return;

      const supplierId = supplierSelect.value;
      const accountId = accountSelect.value;
      const fileToImport = selectedFile;

      confirmButton.disabled = true;
      previewButton.disabled = true;
      fileInput.disabled = true;
      supplierSelect.disabled = true;
      accountSelect.disabled = true;
      cancelButton.disabled = true;
      document.getElementById("xr-cancel-preview").disabled = true;

      messageElement.textContent = "XRechnung wird importiert …";

      try {
        const formData = new FormData();
        formData.append("file", fileToImport);
        formData.append("partner_id", supplierId);
        formData.append("account_id", accountId);

        const response = await fetch("/api/xrechnung/incoming/import", {
          method: "POST",
          credentials: "same-origin",
          headers: {"X-Tenant-ID": String(state.tenantId)},
          body: formData
        });

        if (response.status === 401) {
          showLogin();
          throw Error("Sitzung abgelaufen. Bitte anmelden.");
        }

        const result = await response.json();

        if (!response.ok) {
          throw Error(
            typeof result.detail === "string"
              ? result.detail
              : JSON.stringify(result.detail || result)
          );
        }

        const importedId = result.invoice_id;

        clearPreview();
        fileInput.value = "";
        editor.replaceChildren();

        notify(
          "XRechnung erfolgreich als Eingangsrechnungsentwurf importiert."
        );

        await invoices();

        const importedRow = document.querySelector(
          '[data-invoice="' + importedId + '"]'
        );

        if (importedRow) {
          importedRow.scrollIntoView({
            behavior: "smooth",
            block: "center"
          });
        }

      } catch (error) {
        messageElement.textContent =
          "Import fehlgeschlagen: " + error.message;

        previewButton.disabled = false;
        fileInput.disabled = false;
        supplierSelect.disabled = false;
        accountSelect.disabled = false;
        cancelButton.disabled = false;
        document.getElementById("xr-cancel-preview").disabled = false;
        updateConfirmState();
      }
    };
  }
}
