/**
 * Smart Gaushala CCTV AI Monitoring System
 * CensusModule: Cattle Registry, 05:00/17:00 IST Herd Census, Medical Register, and Feeding Compliance
 */

const CensusModule = (() => {
  let initialized = false;
  let activeTab = 'registry'; // 'registry' | 'audit' | 'medical' | 'feeding'
  let cachedCattleList = [];
  let cachedMedicalRecords = [];

  function init() {
    if (!initialized) {
      bindEvents();
      initialized = true;
    }
    refreshAll();
  }

  function bindEvents() {
    // 1. Sub-tab toggles inside Census View
    const subTabBtns = document.querySelectorAll('.census-subtab-btn');
    subTabBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const subtab = e.currentTarget.dataset.subtab;
        switchSubTab(subtab);
      });
    });

    // 2. Cattle Modal (Open / Close / Submit)
    const openAddCattleBtn = document.getElementById('btn-open-add-cattle');
    if (openAddCattleBtn) {
      openAddCattleBtn.addEventListener('click', openCattleModal);
    }
    const closeModalBtn = document.getElementById('close-cattle-modal-btn');
    const cancelModalBtn = document.getElementById('cancel-cattle-modal-btn');
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeCattleModal);
    if (cancelModalBtn) cancelModalBtn.addEventListener('click', closeCattleModal);

    const cattleForm = document.getElementById('cattle-registration-form');
    if (cattleForm) {
      cattleForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleRegisterCattle();
      });
    }

    // 3. Bulk CSV Import Modal & Actions
    const openBulkBtn = document.getElementById('btn-open-bulk-import');
    if (openBulkBtn) {
      openBulkBtn.addEventListener('click', openBulkImportModal);
    }
    const closeBulkBtn = document.getElementById('close-bulk-import-modal-btn');
    const cancelBulkBtn = document.getElementById('cancel-bulk-import-btn');
    if (closeBulkBtn) closeBulkBtn.addEventListener('click', closeBulkImportModal);
    if (cancelBulkBtn) cancelBulkBtn.addEventListener('click', closeBulkImportModal);

    const downloadSampleBtn = document.getElementById('btn-download-sample-csv');
    if (downloadSampleBtn) {
      downloadSampleBtn.addEventListener('click', downloadSampleCsv);
    }

    const bulkImportForm = document.getElementById('bulk-import-form');
    if (bulkImportForm) {
      bulkImportForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleBulkImportCsv();
      });
    }

    // 4. CSV Export Actions
    const exportCattleBtn = document.getElementById('btn-export-cattle-csv');
    if (exportCattleBtn) {
      exportCattleBtn.addEventListener('click', exportCattleCsv);
    }
    const exportAuditBtn = document.getElementById('btn-export-audit-report');
    if (exportAuditBtn) {
      exportAuditBtn.addEventListener('click', exportAuditReport);
    }

    // 5. AI Reconcile Discrepancy & Subsidy Modal
    const openReconcileBtn = document.getElementById('btn-reconcile-census');
    if (openReconcileBtn) {
      openReconcileBtn.addEventListener('click', openReconcileModal);
    }
    const closeReconcileBtn = document.getElementById('close-reconcile-modal-btn');
    if (closeReconcileBtn) {
      closeReconcileBtn.addEventListener('click', closeReconcileModal);
    }

    // 6. QR Badge Modal Closes
    const closeQrBtn = document.getElementById('close-qr-modal-btn');
    const closeQrCardBtn = document.getElementById('close-qr-card-btn');
    if (closeQrBtn) closeQrBtn.addEventListener('click', closeQrModal);
    if (closeQrCardBtn) closeQrCardBtn.addEventListener('click', closeQrModal);

    // 7. Medical & Vaccination Modal & Actions
    const openAddMedBtn = document.getElementById('btn-open-add-medical');
    if (openAddMedBtn) {
      openAddMedBtn.addEventListener('click', () => openMedicalModal());
    }
    const closeMedBtn = document.getElementById('close-medical-modal-btn');
    const cancelMedBtn = document.getElementById('cancel-medical-modal-btn');
    if (closeMedBtn) closeMedBtn.addEventListener('click', closeMedicalModal);
    if (cancelMedBtn) cancelMedBtn.addEventListener('click', closeMedicalModal);

    const medForm = document.getElementById('medical-record-form');
    if (medForm) {
      medForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleSaveMedicalRecord();
      });
    }

    const medSearchInput = document.getElementById('medical-search-input');
    if (medSearchInput) {
      medSearchInput.addEventListener('input', debounce(() => renderMedicalRecordsTable(), 300));
    }
    const medTypeFilter = document.getElementById('medical-type-filter');
    if (medTypeFilter) {
      medTypeFilter.addEventListener('change', () => renderMedicalRecordsTable());
    }

    // 8. Cattle Registry Filter Controls
    const searchInput = document.getElementById('cattle-search-input');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(() => loadCattleRegistry(), 300));
    }
    const catFilter = document.getElementById('cattle-category-filter');
    if (catFilter) {
      catFilter.addEventListener('change', () => loadCattleRegistry());
    }
    const lactFilter = document.getElementById('cattle-lactation-filter');
    if (lactFilter) {
      lactFilter.addEventListener('change', () => loadCattleRegistry());
    }
    const statusFilter = document.getElementById('cattle-status-filter');
    if (statusFilter) {
      statusFilter.addEventListener('change', () => loadCattleRegistry());
    }

    // 9. Diagnostic & Feeding Actions
    const runDiagBtn = document.getElementById('btn-run-census-diagnostic');
    if (runDiagBtn) {
      runDiagBtn.addEventListener('click', async () => handleRunDiagnosticCensus());
    }

    const runFeedBtn = document.getElementById('btn-run-feeding-check');
    if (runFeedBtn) {
      runFeedBtn.addEventListener('click', async () => handleRunFeedingCheck());
    }
  }

  function switchSubTab(subtab) {
    activeTab = subtab;
    document.querySelectorAll('.census-subtab-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.subtab === subtab);
    });
    document.querySelectorAll('.census-subtab-panel').forEach(p => {
      p.classList.toggle('active', p.id === `subtab-${subtab}`);
    });

    if (subtab === 'registry') loadCattleRegistry();
    if (subtab === 'audit') loadCensusAudit();
    if (subtab === 'medical') loadMedicalRegister();
    if (subtab === 'feeding') loadFeedingCompliance();
  }

  async function refreshAll() {
    await Promise.allSettled([
      loadCattleRegistry(),
      loadCensusAudit(),
      loadMedicalRegister(),
      loadFeedingCompliance()
    ]);
  }

  // -------------------------------------------------------------
  // 1. CATTLE REGISTRY & PROFILES
  // -------------------------------------------------------------
  async function loadCattleRegistry() {
    const listBody = document.getElementById('cattle-registry-tbody');
    if (!listBody) return;

    const searchInput = document.getElementById('cattle-search-input');
    const catFilter = document.getElementById('cattle-category-filter');
    const lactFilter = document.getElementById('cattle-lactation-filter');
    const statusFilter = document.getElementById('cattle-status-filter');

    const search = searchInput ? searchInput.value.trim() : '';
    const category = catFilter ? catFilter.value : '';
    const lactation = lactFilter ? lactFilter.value : '';
    const statusVal = statusFilter ? statusFilter.value : '';

    let url = '/api/cattle?';
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (category) url += `category=${encodeURIComponent(category)}&`;
    if (lactation) url += `lactation_stage=${encodeURIComponent(lactation)}&`;
    if (statusVal) url += `status=${encodeURIComponent(statusVal)}&`;

    try {
      const [cattleList, summary] = await Promise.all([
        apiRequest(url),
        apiRequest('/api/cattle/summary')
      ]);

      cachedCattleList = cattleList || [];
      updateRegistrySummaryChips(summary);

      if (!cattleList || cattleList.length === 0) {
        listBody.innerHTML = `
          <tr>
            <td colspan="8" class="text-center py-4" style="color:var(--text-muted);">
              ${AppState.lang === 'hi' ? 'कोई गोवंश रिकॉर्ड नहीं मिला। कृपया ऊपर दिए गए "+ Register Cattle" से नया गोवंश जोड़ें या CSV आयात करें।' : 'No cattle records found. Click "+ Register Cattle" or "Import CSV" to add livestock.'}
            </td>
          </tr>
        `;
        return;
      }

      listBody.innerHTML = cattleList.map(c => {
        // Category styling
        const cat = c.category || 'cow';
        let catBadge = `<span class="badge-cat-cow">गाय (Cow)</span>`;
        if (cat === 'bull') catBadge = `<span class="badge-cat-bull">नंदी/बैल (Bull)</span>`;
        if (cat === 'calf') catBadge = `<span class="badge-cat-calf">बछड़ा/बछिया (Calf)</span>`;

        // Lactation badge
        const lact = c.lactation_stage || 'dry';
        let lactBadge = `<span class="badge-lact-dry">सूखी (Dry)</span>`;
        if (lact === 'milking') lactBadge = `<span class="badge-lact-milking">दुधारू (Milking)</span>`;
        if (lact === 'pregnant') lactBadge = `<span class="badge-lact-pregnant">गर्भवती (Pregnant)</span>`;
        if (lact === 'na') lactBadge = `<span class="badge-lact-na">—</span>`;

        // Health status badge
        const health = c.health_status || 'healthy';
        let healthBadge = `<span class="badge-health-ok">स्वस्थ (Healthy)</span>`;
        if (health === 'under_treatment') healthBadge = `<span class="badge-health-treatment">उपचाराधीन</span>`;
        if (health === 'quarantine') healthBadge = `<span class="badge-health-quarantine">क्वारंटाइन</span>`;

        // INAPH tag snippet
        const inaphSnippet = c.inaph_tag ? `<div style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono); margin-top:2px;">UID: ${escapeHtml(c.inaph_tag)}</div>` : '';

        return `
          <tr>
            <td>
              <strong style="color:var(--accent-emerald); font-family:var(--font-mono); font-size:0.92rem;">${escapeHtml(c.tag_id)}</strong>
              ${inaphSnippet}
            </td>
            <td>
              <strong style="color:var(--text-primary); font-size:0.9rem;">${escapeHtml(c.name || '—')}</strong>
              <div style="font-size:0.75rem; color:var(--text-muted);">${c.age_years ? c.age_years + ' Yrs' : ''}</div>
            </td>
            <td><span class="badge-enclosure">${escapeHtml(c.enclosure_id)}</span></td>
            <td>
              <div>${catBadge}</div>
              <div style="font-size:0.75rem; color:var(--text-muted); margin-top:3px;">${escapeHtml(c.breed || 'Gir / Indigenous')}</div>
            </td>
            <td>${lactBadge}</td>
            <td>${healthBadge}</td>
            <td>
              <span class="status-pill ${c.status === 'active' ? 'pill-active' : 'pill-inactive'}">
                ${c.status === 'active' ? (AppState.lang === 'hi' ? 'सक्रिय' : 'Active') : (AppState.lang === 'hi' ? 'निष्क्रिय' : 'Inactive')}
              </span>
            </td>
            <td>
              <div class="row-actions-group" style="display:flex; gap:4px; flex-wrap:wrap;">
                <button class="btn-sm btn-ghost" title="Printable ID Badge & QR Code" onclick="CensusModule.showQrBadge(${c.id})">
                  🪪 ID / QR
                </button>
                <button class="btn-sm btn-ghost" title="Log Medical / Vaccine Record" onclick="CensusModule.openAddMedicalFor(${c.id})">
                  💉 Medical
                </button>
                <button class="btn-sm btn-ghost" title="${c.status === 'active' ? 'Mark Inactive' : 'Mark Active'}" onclick="CensusModule.toggleStatus(${c.id})">
                  ${c.status === 'active' ? 'Deactivate' : 'Activate'}
                </button>
                <button class="btn-sm btn-danger-ghost" title="Remove Record" onclick="CensusModule.deleteRecord(${c.id})">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

    } catch (err) {
      console.error('Error loading cattle registry:', err);
      listBody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-rose">Failed to load registry: ${err.message}</td></tr>`;
    }
  }

  function updateRegistrySummaryChips(summary) {
    if (!summary) return;
    const totalElem = document.getElementById('reg-total-cows');
    const activeElem = document.getElementById('reg-active-cows');
    const subsidyElem = document.getElementById('reg-subsidy-daily');

    if (totalElem) totalElem.textContent = summary.total_registered ?? 0;
    if (activeElem) activeElem.textContent = summary.active_herd ?? 0;
    if (subsidyElem && summary.subsidy) {
      subsidyElem.textContent = `₹${(summary.subsidy.daily_total_inr || 0).toLocaleString('en-IN')}`;
    }

    // Sync main dashboard metric if available
    const dashTotal = document.getElementById('metric-total-cattle');
    if (dashTotal && summary.active_herd !== undefined) {
      dashTotal.textContent = summary.active_herd;
    }
  }

  function openCattleModal() {
    const modal = document.getElementById('cattle-modal');
    if (modal) modal.style.display = 'flex';
  }

  function closeCattleModal() {
    const modal = document.getElementById('cattle-modal');
    if (modal) modal.style.display = 'none';
    const form = document.getElementById('cattle-registration-form');
    if (form) form.reset();
  }

  async function handleRegisterCattle() {
    const tag_id = document.getElementById('cow-tag-id').value.trim();
    const inaph_tag = document.getElementById('cow-inaph-tag').value.trim() || null;
    const name = document.getElementById('cow-name').value.trim() || null;
    const enclosure_id = document.getElementById('cow-enclosure').value.trim() || 'cam-01';
    const category = document.getElementById('cow-category').value;
    const lactation_stage = document.getElementById('cow-lactation').value;
    const health_status = document.getElementById('cow-health').value;
    const breed = document.getElementById('cow-breed').value.trim() || 'Gir / Indigenous';
    const intake_source = document.getElementById('cow-intake').value;
    const ageVal = document.getElementById('cow-age').value;
    const age_years = parseFloat(ageVal) || 3.0;
    const notes = document.getElementById('cow-notes').value.trim() || null;

    if (!tag_id) {
      showToast(AppState.lang === 'hi' ? 'टैग आईडी आवश्यक है' : 'Tag ID is required', 'warning');
      return;
    }

    const gender = category === 'bull' ? 'male' : 'female';

    try {
      await apiRequest('/api/cattle', {
        method: 'POST',
        body: JSON.stringify({
          tag_id,
          inaph_tag,
          name,
          enclosure_id,
          category,
          gender,
          lactation_stage,
          health_status,
          breed,
          intake_source,
          age_years,
          notes,
          status: 'active'
        })
      });

      showToast(
        AppState.lang === 'hi' 
          ? `गोवंश ${tag_id} (${breed}) सफलतापूर्वक पंजीकृत किया गया!` 
          : `Cattle ${tag_id} registered successfully!`, 
        'info'
      );
      closeCattleModal();
      await loadCattleRegistry();
      await loadCensusAudit();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  async function toggleStatus(id) {
    try {
      await apiRequest(`/api/cattle/${id}/status`, { method: 'PATCH' });
      showToast(AppState.lang === 'hi' ? 'स्थिति अपडेट की गई' : 'Cattle status updated', 'info');
      await loadCattleRegistry();
      await loadCensusAudit();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  async function deleteRecord(id) {
    const confirmMsg = AppState.lang === 'hi' ? 'क्या आप निश्चित रूप से इस गोवंश को हटाना चाहते हैं?' : 'Are you sure you want to remove this cattle record?';
    if (!confirm(confirmMsg)) return;

    try {
      await apiRequest(`/api/cattle/${id}`, { method: 'DELETE' });
      showToast(AppState.lang === 'hi' ? 'रिकॉर्ड हटा दिया गया' : 'Record removed', 'info');
      await loadCattleRegistry();
      await loadCensusAudit();
      if (activeTab === 'medical') await loadMedicalRegister();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  // -------------------------------------------------------------
  // 2. BULK CSV IMPORT & EXPORT
  // -------------------------------------------------------------
  function openBulkImportModal() {
    const modal = document.getElementById('bulk-import-modal');
    if (modal) {
      modal.style.display = 'flex';
      const feedback = document.getElementById('bulk-import-feedback');
      if (feedback) feedback.style.display = 'none';
      const form = document.getElementById('bulk-import-form');
      if (form) form.reset();
    }
  }

  function closeBulkImportModal() {
    const modal = document.getElementById('bulk-import-modal');
    if (modal) modal.style.display = 'none';
  }

  function downloadSampleCsv() {
    const sampleRows = [
      'Tag ID,INAPH National ID,Name,Enclosure Pen,Breed,Category,Gender,Lactation Stage,Health Status,Age (Years),Intake Source,Notes',
      'DL-GAU-0105,100012345678,Nandini,cam-01,Gir Cow,cow,female,milking,healthy,4.5,rescue,Red-brown speckled coat with long pendulous ears',
      'DL-GAU-0106,100012345679,Gauri,cam-01,Sahiwal,cow,female,dry,healthy,5.0,donated,Light red coat with loose skin folds',
      'DL-GAU-0107,100012345680,Nandi Rudra,cam-02,Tharparkar,bull,male,na,healthy,3.5,rescue,Large robust white bull with lyre horns',
      'DL-GAU-0108,100012345681,Kamdhenu,cam-01,Rathi,cow,female,pregnant,healthy,4.0,rescue,Due calving in 2 months. High nutrition diet',
      'DL-GAU-0109,100012345682,Chhoti,cam-04,Gir Calf,calf,female,na,healthy,0.8,born,Calf born in Gaushala hospital bay'
    ].join('\n');

    const blob = new Blob(['\ufeff' + sampleRows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'gaushala_cattle_bulk_sample.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  async function handleBulkImportCsv() {
    const fileInput = document.getElementById('bulk-csv-file');
    const feedback = document.getElementById('bulk-import-feedback');
    const uploadBtn = document.getElementById('btn-submit-bulk-upload');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
      showToast('Please select a CSV file to upload', 'warning');
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    if (uploadBtn) {
      uploadBtn.disabled = true;
      uploadBtn.innerHTML = '<span class="spinner-inline"></span> Importing CSV...';
    }

    try {
      const token = localStorage.getItem('gaushala_token') || sessionStorage.getItem('gaushala_token');
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/cattle/bulk-import/csv', {
        method: 'POST',
        headers,
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with status ${res.status}`);
      }

      const result = await res.json();
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(16,185,129,0.1)';
        feedback.style.border = '1px solid rgba(16,185,129,0.3)';
        feedback.style.color = '#047857';
        feedback.innerHTML = `✓ <strong>Bulk Import Successful!</strong><br>Imported: <strong>${result.imported}</strong> cattle | Skipped/Duplicate: <strong>${result.skipped}</strong>`;
      }

      showToast(`Bulk Import Complete: ${result.imported} added, ${result.skipped} skipped`, 'info');
      await loadCattleRegistry();
      await loadCensusAudit();
    } catch (err) {
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(239,68,68,0.1)';
        feedback.style.border = '1px solid rgba(239,68,68,0.3)';
        feedback.style.color = '#b91c1c';
        feedback.textContent = `Import Error: ${err.message}`;
      }
      showToast(err.message, 'critical');
    } finally {
      if (uploadBtn) {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<span>Upload & Import Records</span>';
      }
    }
  }

  function exportCattleCsv() {
    showToast('Downloading official Cattle Registry muster roll...', 'info');
    window.location.href = '/api/cattle/export/csv';
  }

  function exportAuditReport() {
    showToast('Downloading official Government Census Audit Report...', 'info');
    window.location.href = '/api/census/export/audit-report';
  }

  // -------------------------------------------------------------
  // 3. AI RECONCILIATION ENGINE & SUBSIDY AUDIT
  // -------------------------------------------------------------
  async function openReconcileModal() {
    const modal = document.getElementById('reconcile-modal');
    const body = document.getElementById('reconcile-modal-body');
    if (!modal || !body) return;

    modal.style.display = 'flex';
    body.innerHTML = `
      <div style="text-align:center; padding:3rem 1rem;">
        <div class="spinner-inline" style="width:28px; height:28px; border-width:3px; margin:0 auto 12px;"></div>
        <p style="color:var(--text-secondary); font-size:0.95rem; font-weight:600;">
          Running Live AI Headcount Reconciliation across all camera enclosures...
        </p>
        <p style="color:var(--text-muted); font-size:0.8rem;">
          Cross-referencing real-time YOLOv8 tracks against active database registration
        </p>
      </div>
    `;

    try {
      const data = await apiRequest('/api/census/reconcile', { method: 'POST' });
      renderReconcileModalContent(data);
    } catch (err) {
      body.innerHTML = `
        <div style="padding:2rem; text-align:center; color:var(--accent-rose);">
          <p><strong>Failed to run reconciliation:</strong> ${escapeHtml(err.message)}</p>
          <button class="btn-primary" style="margin-top:1rem;" onclick="CensusModule.openReconcileModal()">Retry</button>
        </div>
      `;
    }
  }

  function closeReconcileModal() {
    const modal = document.getElementById('reconcile-modal');
    if (modal) modal.style.display = 'none';
  }

  function renderReconcileModalContent(data) {
    const body = document.getElementById('reconcile-modal-body');
    if (!body) return;

    const diff = data.overall_difference;
    let diffColor = 'var(--accent-emerald)';
    let diffText = '0 (PERFECT MATCH)';
    if (diff > 0) {
      diffColor = 'var(--accent-amber)';
      diffText = `+${diff} (EXCESS)`;
    } else if (diff < 0) {
      diffColor = 'var(--accent-rose)';
      diffText = `${diff} (SHORTFALL)`;
    }

    const subsidy = data.government_subsidy || {};
    const regDaily = subsidy.registered_daily_amount_inr || 0;
    const verDaily = subsidy.verified_daily_amount_inr || 0;
    const monthProj = subsidy.monthly_projected_amount_inr || 0;

    let pensHtml = (data.enclosures || []).map(p => {
      let statusBadge = `<span class="badge-match">MATCH</span>`;
      if (p.status === 'SHORTFALL') statusBadge = `<span class="badge-shortfall">SHORTFALL</span>`;
      if (p.status === 'EXCESS') statusBadge = `<span class="badge-excess">EXCESS</span>`;
      if (p.status === 'STANDBY') statusBadge = `<span class="status-pill pill-inactive">STANDBY</span>`;

      return `
        <tr>
          <td>
            <strong>${escapeHtml(p.enclosure_name)}</strong>
            <div style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">${escapeHtml(p.camera_id)}</div>
          </td>
          <td><strong style="font-size:1rem;">${p.expected_count}</strong></td>
          <td><strong style="font-size:1rem; color:${p.camera_online ? 'var(--accent-primary)' : 'var(--text-muted)'};">${p.detected_count !== null ? p.detected_count : '—'}</strong></td>
          <td>
            <strong style="color:${p.difference === 0 ? 'var(--accent-emerald)' : p.difference < 0 ? 'var(--accent-rose)' : 'var(--accent-amber)'};">
              ${p.difference !== null ? (p.difference > 0 ? '+' + p.difference : p.difference) : '—'}
            </strong>
          </td>
          <td>${statusBadge}</td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${escapeHtml(p.recommendation)}</td>
        </tr>
      `;
    }).join('');

    body.innerHTML = `
      <div class="subsidy-highlight-card">
        <div>
          <div class="subsidy-title">
            <span>🏛️ GOV FEED SUBSIDY ENTITLEMENT (₹40 / CATTLE / DAY)</span>
          </div>
          <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:3px;">
            Verified CCTV Headcount: <strong>${data.total_live_detected}</strong> | Registered Muster: <strong>${data.total_registered_herd}</strong>
          </div>
        </div>
        <div style="text-align:right;">
          <div class="subsidy-amount">₹${verDaily.toLocaleString('en-IN')} / Day</div>
          <div style="font-size:0.75rem; color:var(--text-muted);">Projected: ₹${monthProj.toLocaleString('en-IN')} / Month</div>
        </div>
      </div>

      <div class="reconcile-kpi-grid">
        <div class="reconcile-kpi-card">
          <div class="reconcile-kpi-title">Registered Herd</div>
          <div class="reconcile-kpi-val text-primary">${data.total_registered_herd}</div>
        </div>
        <div class="reconcile-kpi-card">
          <div class="reconcile-kpi-title">CCTV Verified</div>
          <div class="reconcile-kpi-val" style="color:var(--accent-emerald);">${data.total_live_detected}</div>
        </div>
        <div class="reconcile-kpi-card">
          <div class="reconcile-kpi-title">Herd Variance</div>
          <div class="reconcile-kpi-val" style="color:${diffColor};">${diffText}</div>
        </div>
        <div class="reconcile-kpi-card">
          <div class="reconcile-kpi-title">Subsidy Match</div>
          <div class="reconcile-kpi-val" style="color:${verDaily >= regDaily ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
            ${regDaily > 0 ? Math.round((verDaily / regDaily) * 100) : 100}%
          </div>
        </div>
      </div>

      <h4 style="font-size:0.9rem; font-weight:700; margin-bottom:8px; color:var(--text-primary);">
        Enclosure-by-Enclosure Breakdown
      </h4>
      <div class="modern-table-wrap" style="max-height:240px; overflow-y:auto; margin-bottom:1.25rem;">
        <table class="modern-table">
          <thead>
            <tr>
              <th>Enclosure / Node</th>
              <th>Registered</th>
              <th>Detected</th>
              <th>Variance</th>
              <th>Status</th>
              <th>AI Inspection Note</th>
            </tr>
          </thead>
          <tbody>
            ${pensHtml}
          </tbody>
        </table>
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border-subtle); padding-top:1rem;">
        <span style="font-size:0.75rem; color:var(--text-muted);">
          Reconciliation Run: ${formatDate(data.timestamp)}
        </span>
        <div style="display:flex; gap:8px;">
          <button class="btn-tool" onclick="CensusModule.exportAuditReport()">
            📥 Export Audit Roll
          </button>
          <button class="btn-primary" onclick="CensusModule.openReconcileModal()">
            ⚡ Re-Scan Now
          </button>
        </div>
      </div>
    `;
  }

  // -------------------------------------------------------------
  // 4. PRINTABLE OFFICIAL CATTLE ID BADGE & QR GENERATOR
  // -------------------------------------------------------------
  async function showQrBadge(cattleId) {
    const modal = document.getElementById('qr-id-modal');
    const printArea = document.getElementById('cattle-id-card-print-area');
    if (!modal || !printArea) return;

    modal.style.display = 'flex';
    printArea.innerHTML = `<div style="text-align:center; padding:2rem;"><div class="spinner-inline"></div> Generating official cattle identity badge...</div>`;

    try {
      const c = await apiRequest(`/api/cattle/${cattleId}`);
      
      const qrPayload = `TAG:${c.tag_id}|INAPH:${c.inaph_tag || 'NA'}|BREED:${c.breed || 'Desi'}|PEN:${c.enclosure_id}|GAUSHALA:GOV_AI`;
      const qrSvg = generateQrSvg(qrPayload, 140);

      const catLabel = c.category === 'bull' ? 'नंदी / बैल (Bull)' : c.category === 'calf' ? 'बछड़ा / बछिया (Calf)' : 'गाय (Cow)';
      const lactLabel = c.lactation_stage === 'milking' ? 'दुधारू (Milking)' : c.lactation_stage === 'pregnant' ? 'गर्भवती (Pregnant)' : 'सूखी (Dry)';
      const healthLabel = c.health_status === 'healthy' ? 'स्वस्थ (Healthy)' : c.health_status === 'under_treatment' ? 'उपचाराधीन' : 'क्वारंटाइन';

      printArea.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid #334155; padding-bottom:12px; margin-bottom:14px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:1.4rem;">🇮🇳</span>
              <div>
                <div style="font-size:0.7rem; letter-spacing:0.08em; text-transform:uppercase; color:#94a3b8; font-weight:800;">
                  STATE GAU SEVA AYOG &bull; ANIMAL HUSBANDRY DEPT
                </div>
                <div style="font-size:1.05rem; font-weight:900; color:#f8fafc; letter-spacing:0.02em;">
                  OFFICIAL LIVESTOCK IDENTITY CARD
                </div>
              </div>
            </div>
          </div>
          <div style="background:#10b981; color:#0f172a; font-weight:900; font-size:0.7rem; padding:3px 8px; border-radius:4px; letter-spacing:0.04em;">
            AI VERIFIED
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 140px; gap:16px; align-items:center;">
          <div>
            <div style="margin-bottom:10px;">
              <div style="font-size:0.7rem; text-transform:uppercase; color:#94a3b8; font-weight:700;">Ear Tag / Collar RFID</div>
              <div style="font-size:1.4rem; font-weight:900; font-family:var(--font-mono); color:#10b981;">
                ${escapeHtml(c.tag_id)}
              </div>
              ${c.inaph_tag ? `<div style="font-size:0.8rem; font-family:var(--font-mono); color:#cbd5e1; margin-top:2px;">INAPH UID: <strong>${escapeHtml(c.inaph_tag)}</strong></div>` : ''}
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.82rem; margin-bottom:8px;">
              <div>
                <span style="color:#94a3b8; font-size:0.72rem;">Name:</span>
                <div style="font-weight:700; color:#f8fafc;">${escapeHtml(c.name || 'Gomata')}</div>
              </div>
              <div>
                <span style="color:#94a3b8; font-size:0.72rem;">Desi Breed:</span>
                <div style="font-weight:700; color:#f8fafc;">${escapeHtml(c.breed || 'Gir')}</div>
              </div>
              <div>
                <span style="color:#94a3b8; font-size:0.72rem;">Category & Age:</span>
                <div style="font-weight:600; color:#f8fafc;">${catLabel} (${c.age_years || 3} Yrs)</div>
              </div>
              <div>
                <span style="color:#94a3b8; font-size:0.72rem;">Assigned Enclosure:</span>
                <div style="font-weight:700; color:#38bdf8;">${escapeHtml(c.enclosure_id)}</div>
              </div>
              <div>
                <span style="color:#94a3b8; font-size:0.72rem;">Lactation Stage:</span>
                <div style="font-weight:600; color:#f8fafc;">${lactLabel}</div>
              </div>
              <div>
                <span style="color:#94a3b8; font-size:0.72rem;">Health Status:</span>
                <div style="font-weight:700; color:#10b981;">${healthLabel}</div>
              </div>
            </div>
          </div>

          <div style="text-align:center;">
            <div style="background:#ffffff; padding:6px; border-radius:10px; display:inline-block; box-shadow:0 4px 12px rgba(0,0,0,0.4);">
              ${qrSvg}
            </div>
            <div style="font-size:0.65rem; color:#94a3b8; margin-top:6px; font-weight:600;">
              Mobile Quick-Scan
            </div>
          </div>
        </div>

        <div style="margin-top:14px; padding-top:10px; border-top:1px dashed #334155; display:flex; justify-content:space-between; align-items:center; font-size:0.72rem; color:#64748b;">
          <span>Gaushala CCTV Vision Portal &bull; Reg: ${c.created_at ? c.created_at.slice(0, 10) : 'Active'}</span>
          <span>Security Hash: <code style="color:#94a3b8; font-size:0.7rem;">GAU-${c.id}-SEC</code></span>
        </div>
      `;

    } catch (err) {
      printArea.innerHTML = `<div class="text-rose text-center p-3">Failed to load ID card: ${err.message}</div>`;
    }
  }

  function closeQrModal() {
    const modal = document.getElementById('qr-id-modal');
    if (modal) modal.style.display = 'none';
  }

  // Pure-JS Standalone QR Code Vector SVG Generator (Version 3, 29x29)
  function generateQrSvg(text, size = 140) {
    const version = 3;
    const N = 17 + 4 * version; // 29x29
    const totalCodewords = 70;
    const ecCodewords = 26;
    const dataCodewords = totalCodewords - ecCodewords; // 44 bytes

    // 1. Galois Field GF(256)
    const GF_EXP = new Uint8Array(512);
    const GF_LOG = new Uint8Array(256);
    let x = 1;
    for (let i = 0; i < 255; i++) {
      GF_EXP[i] = x;
      GF_EXP[i + 255] = x;
      GF_LOG[x] = i;
      x = (x << 1) ^ (x & 128 ? 0x11d : 0);
    }
    function gfMul(a, b) {
      return (a === 0 || b === 0) ? 0 : GF_EXP[GF_LOG[a] + GF_LOG[b]];
    }

    // 2. Reed-Solomon Generator Polynomial
    let genPoly = [1];
    for (let i = 0; i < ecCodewords; i++) {
      const nextPoly = new Array(genPoly.length + 1).fill(0);
      const root = GF_EXP[i];
      for (let j = 0; j < genPoly.length; j++) {
        nextPoly[j] ^= gfMul(genPoly[j], root);
        nextPoly[j + 1] ^= genPoly[j];
      }
      genPoly = nextPoly;
    }

    // 3. UTF-8 Byte Encoding
    const utf8Bytes = [];
    for (let i = 0; i < text.length; i++) {
      const code = text.charCodeAt(i);
      if (code < 128) utf8Bytes.push(code);
      else if (code < 2048) {
        utf8Bytes.push(192 | (code >> 6));
        utf8Bytes.push(128 | (code & 63));
      } else {
        utf8Bytes.push(224 | (code >> 12));
        utf8Bytes.push(128 | ((code >> 6) & 63));
        utf8Bytes.push(128 | (code & 63));
      }
    }

    const bitBuf = [];
    function putBits(val, len) {
      for (let i = len - 1; i >= 0; i--) {
        bitBuf.push((val >> i) & 1);
      }
    }

    putBits(4, 4); // Byte mode indicator
    const count = Math.min(utf8Bytes.length, dataCodewords - 2);
    putBits(count, 8);
    for (let i = 0; i < count; i++) putBits(utf8Bytes[i], 8);

    const maxBits = dataCodewords * 8;
    const padTerm = Math.min(4, maxBits - bitBuf.length);
    putBits(0, padTerm);
    while (bitBuf.length % 8 !== 0) bitBuf.push(0);

    const data = [];
    for (let i = 0; i < bitBuf.length; i += 8) {
      let b = 0;
      for (let j = 0; j < 8; j++) b = (b << 1) | bitBuf[i + j];
      data.push(b);
    }
    const padPatterns = [0xec, 0x11];
    let padIdx = 0;
    while (data.length < dataCodewords) {
      data.push(padPatterns[padIdx % 2]);
      padIdx++;
    }

    // 4. Calculate EC codewords
    const ec = new Array(ecCodewords).fill(0);
    for (let i = 0; i < data.length; i++) {
      const factor = data[i] ^ ec[0];
      for (let j = 0; j < ecCodewords - 1; j++) {
        ec[j] = ec[j + 1] ^ gfMul(genPoly[ecCodewords - 1 - j], factor);
      }
      ec[ecCodewords - 1] = gfMul(genPoly[0], factor);
    }
    const allCodewords = data.concat(ec);

    // 5. Build 29x29 matrix
    const matrix = Array.from({ length: N }, () => new Array(N).fill(null));
    const isFunction = Array.from({ length: N }, () => new Array(N).fill(false));

    function setModule(r, c, val, func = true) {
      if (r >= 0 && r < N && c >= 0 && c < N) {
        matrix[r][c] = val;
        if (func) isFunction[r][c] = true;
      }
    }

    function setFinder(startR, startC) {
      for (let r = -1; r <= 7; r++) {
        for (let c = -1; c <= 7; c++) {
          const nr = startR + r;
          const nc = startC + c;
          if (nr < 0 || nr >= N || nc < 0 || nc >= N) continue;
          if (r >= 0 && r <= 6 && c >= 0 && c <= 6) {
            const isBlack = (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4));
            setModule(nr, nc, isBlack ? 1 : 0);
          } else {
            setModule(nr, nc, 0);
          }
        }
      }
    }

    setFinder(0, 0);
    setFinder(0, N - 7);
    setFinder(N - 7, 0);

    // Alignment pattern
    const alignPos = 22;
    for (let r = -2; r <= 2; r++) {
      for (let c = -2; c <= 2; c++) {
        const isBlack = Math.max(Math.abs(r), Math.abs(c)) !== 1;
        setModule(alignPos + r, alignPos + c, isBlack ? 1 : 0);
      }
    }

    // Timing patterns
    for (let i = 8; i < N - 8; i++) {
      if (matrix[6][i] === null) setModule(6, i, i % 2 === 0 ? 1 : 0);
      if (matrix[i][6] === null) setModule(i, 6, i % 2 === 0 ? 1 : 0);
    }
    setModule(N - 8, 8, 1);

    // Reserve format modules
    for (let i = 0; i < 9; i++) { setModule(8, i, 0); setModule(i, 8, 0); }
    for (let i = 0; i < 8; i++) { setModule(8, N - 1 - i, 0); setModule(N - 1 - i, 8, 0); }

    // Place data bits in zig-zag
    const allBits = [];
    for (const b of allCodewords) {
      for (let bit = 7; bit >= 0; bit--) allBits.push((b >> bit) & 1);
    }

    let bitIdx = 0;
    let upwards = true;
    for (let rightCol = N - 1; rightCol > 0; rightCol -= 2) {
      if (rightCol === 6) rightCol--;
      const leftCol = rightCol - 1;
      for (let i = 0; i < N; i++) {
        const r = upwards ? (N - 1 - i) : i;
        for (const c of [rightCol, leftCol]) {
          if (!isFunction[r][c]) {
            const bitVal = bitIdx < allBits.length ? allBits[bitIdx++] : 0;
            const mask = (r + c) % 2 === 0;
            matrix[r][c] = (bitVal ^ (mask ? 1 : 0));
          }
        }
      }
      upwards = !upwards;
    }

    // Format bits
    const fmtBits = [1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0];
    const tlCoords = [
      [8, 0], [8, 1], [8, 2], [8, 3], [8, 4], [8, 5], [8, 7], [8, 8],
      [7, 8], [5, 8], [4, 8], [3, 8], [2, 8], [1, 8], [0, 8]
    ];
    for (let i = 0; i < 15; i++) matrix[tlCoords[i][0]][tlCoords[i][1]] = fmtBits[i];
    for (let i = 0; i < 7; i++) matrix[N - 1 - i][8] = fmtBits[i];
    for (let i = 0; i < 8; i++) matrix[8][N - 8 + i] = fmtBits[7 + i];

    // Build SVG
    const moduleSize = (size / (N + 4)).toFixed(2);
    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">`;
    svg += `<rect width="${size}" height="${size}" fill="#ffffff" rx="6"/>`;
    svg += `<g fill="#0f172a" transform="translate(${(moduleSize * 2).toFixed(1)}, ${(moduleSize * 2).toFixed(1)})">`;

    for (let r = 0; r < N; r++) {
      for (let c = 0; c < N; c++) {
        if (matrix[r][c] === 1) {
          svg += `<rect x="${(c * moduleSize).toFixed(1)}" y="${(r * moduleSize).toFixed(1)}" width="${moduleSize}" height="${moduleSize}"/>`;
        }
      }
    }
    svg += `</g></svg>`;
    return svg;
  }

  // -------------------------------------------------------------
  // 5. MEDICAL & VACCINATION REGISTER
  // -------------------------------------------------------------
  async function loadMedicalRegister() {
    const tbody = document.getElementById('cattle-medical-tbody');
    if (!tbody) return;

    try {
      const [alertsData, cattleList] = await Promise.all([
        apiRequest('/api/cattle/medical/alerts'),
        apiRequest('/api/cattle')
      ]);

      cachedCattleList = cattleList || [];

      // Update due chips
      const dueElem = document.getElementById('med-due-count');
      const compElem = document.getElementById('med-completed-count');
      if (dueElem) dueElem.textContent = alertsData.due_soon_count ?? 0;
      if (compElem) compElem.textContent = (alertsData.recent_completed || []).length;

      // Fetch all medical records across all registered cattle
      const allMedPromises = cachedCattleList.map(c => 
        apiRequest(`/api/cattle/${c.id}/medical`).catch(() => [])
      );
      const results = await Promise.all(allMedPromises);
      
      const flatRecords = [];
      results.forEach((recList, idx) => {
        const cow = cachedCattleList[idx];
        recList.forEach(r => {
          flatRecords.push({ ...r, cow_tag: cow.tag_id, cow_name: cow.name, cow_breed: cow.breed });
        });
      });

      // Sort by administered date desc
      flatRecords.sort((a, b) => (b.administered_date || '').localeCompare(a.administered_date || ''));
      cachedMedicalRecords = flatRecords;

      renderMedicalRecordsTable();

    } catch (err) {
      console.error('Error loading medical register:', err);
      tbody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-rose">Failed to load medical records: ${err.message}</td></tr>`;
    }
  }

  function renderMedicalRecordsTable() {
    const tbody = document.getElementById('cattle-medical-tbody');
    if (!tbody) return;

    const searchInput = document.getElementById('medical-search-input');
    const typeFilter = document.getElementById('medical-type-filter');

    const search = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const typeVal = typeFilter ? typeFilter.value : '';

    let records = cachedMedicalRecords || [];

    if (search) {
      records = records.filter(r => 
        (r.tag_id && r.tag_id.toLowerCase().includes(search)) ||
        (r.title && r.title.toLowerCase().includes(search)) ||
        (r.doctor_name && r.doctor_name.toLowerCase().includes(search)) ||
        (r.cow_name && r.cow_name.toLowerCase().includes(search))
      );
    }

    if (typeVal) {
      records = records.filter(r => r.record_type === typeVal);
    }

    if (records.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" class="text-center py-4" style="color:var(--text-muted);">
            No medical records found. Click "+ Log Medical / Vaccine" to record treatments or vaccines.
          </td>
        </tr>
      `;
      return;
    }

    const todayStr = new Date().toISOString().slice(0, 10);

    tbody.innerHTML = records.map(r => {
      // Type pill
      let typePill = `<span class="badge-med-vaccine">💉 Vaccination</span>`;
      if (r.record_type === 'deworming') typePill = `<span class="badge-med-deworm">💊 Deworming</span>`;
      if (r.record_type === 'checkup') typePill = `<span class="badge-med-checkup">🩺 Checkup</span>`;
      if (r.record_type === 'treatment') typePill = `<span class="badge-med-treatment">🩹 Treatment</span>`;

      // Due date alert
      let dueDateHtml = `<span style="color:var(--text-muted); font-size:0.8rem;">—</span>`;
      if (r.next_due_date) {
        const isOverdue = r.next_due_date < todayStr && r.status !== 'completed';
        dueDateHtml = `
          <strong style="font-size:0.83rem; color:${isOverdue ? 'var(--accent-rose)' : 'var(--text-primary)'};">
            ${r.next_due_date}
          </strong>
          ${isOverdue ? '<div class="status-badge-overdue" style="margin-top:2px;">OVERDUE</div>' : ''}
        `;
      }

      return `
        <tr>
          <td>
            <strong style="color:var(--accent-emerald); font-family:var(--font-mono); font-size:0.88rem;">${escapeHtml(r.tag_id)}</strong>
            <div style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(r.cow_name || '')}</div>
          </td>
          <td>${typePill}</td>
          <td>
            <strong style="color:var(--text-primary); font-size:0.88rem;">${escapeHtml(r.title)}</strong>
          </td>
          <td style="font-size:0.82rem; color:var(--text-secondary);">${r.administered_date || '—'}</td>
          <td>${dueDateHtml}</td>
          <td style="font-size:0.82rem; color:var(--text-secondary);">${escapeHtml(r.doctor_name || '—')}</td>
          <td>
            <span class="status-pill ${r.status === 'completed' ? 'pill-active' : 'pill-inactive'}">
              ${r.status === 'completed' ? 'Completed' : 'Scheduled / Due'}
            </span>
          </td>
          <td style="font-size:0.78rem; color:var(--text-muted); max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            ${escapeHtml(r.notes || '—')}
          </td>
          <td>
            <button class="btn-sm btn-danger-ghost" title="Delete Medical Record" onclick="CensusModule.deleteMedicalRecord(${r.id})">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  async function openMedicalModal(preselectedCattleId = null) {
    const modal = document.getElementById('medical-modal');
    const select = document.getElementById('med-cattle-select');
    if (!modal || !select) return;

    modal.style.display = 'flex';

    // Populate cattle dropdown
    if (cachedCattleList.length === 0) {
      cachedCattleList = await apiRequest('/api/cattle').catch(() => []);
    }

    select.innerHTML = cachedCattleList.map(c => `
      <option value="${c.id}" ${preselectedCattleId === c.id ? 'selected' : ''}>
        ${escapeHtml(c.tag_id)} - ${escapeHtml(c.name || c.breed || 'Desi Cow')} (${c.enclosure_id})
      </option>
    `).join('');

    // Pre-fill today's date
    const adminDateInput = document.getElementById('med-admin-date');
    if (adminDateInput && !adminDateInput.value) {
      adminDateInput.value = new Date().toISOString().slice(0, 10);
    }
  }

  function openAddMedicalFor(cattleId) {
    openMedicalModal(cattleId);
  }

  function closeMedicalModal() {
    const modal = document.getElementById('medical-modal');
    if (modal) modal.style.display = 'none';
    const form = document.getElementById('medical-record-form');
    if (form) form.reset();
  }

  async function handleSaveMedicalRecord() {
    const select = document.getElementById('med-cattle-select');
    const cattleId = select ? select.value : null;

    if (!cattleId) {
      showToast('Please select a cattle head', 'warning');
      return;
    }

    const record_type = document.getElementById('med-record-type').value;
    const title = document.getElementById('med-title').value.trim();
    const administered_date = document.getElementById('med-admin-date').value;
    const next_due_date = document.getElementById('med-due-date').value || null;
    const doctor_name = document.getElementById('med-doctor').value.trim() || null;
    const statusVal = document.getElementById('med-status').value;
    const notes = document.getElementById('med-notes').value.trim() || null;

    if (!title || !administered_date) {
      showToast('Title and Administered Date are required', 'warning');
      return;
    }

    try {
      await apiRequest(`/api/cattle/${cattleId}/medical`, {
        method: 'POST',
        body: JSON.stringify({
          record_type,
          title,
          administered_date,
          next_due_date,
          doctor_name,
          status: statusVal,
          notes
        })
      });

      showToast('Medical & Vaccination record logged successfully!', 'info');
      closeMedicalModal();
      await loadMedicalRegister();
      await loadCattleRegistry();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  async function deleteMedicalRecord(recordId) {
    if (!confirm('Are you sure you want to delete this medical record?')) return;
    try {
      await apiRequest(`/api/cattle/medical/${recordId}`, { method: 'DELETE' });
      showToast('Medical record deleted', 'info');
      await loadMedicalRegister();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  // -------------------------------------------------------------
  // 6. HERD CENSUS AUDIT (05:00 & 17:00 IST)
  // -------------------------------------------------------------
  async function loadCensusAudit() {
    try {
      const data = await apiRequest('/api/census/latest');
      renderCensusSummaryBanner(data);
      await loadCensusHistoryTable();
    } catch (err) {
      console.error('Error loading census audit:', err);
    }
  }

  function renderCensusSummaryBanner(data) {
    if (!data) return;

    const regHerdElem = document.getElementById('census-registered-count');
    if (regHerdElem) regHerdElem.textContent = data.active_registered_herd ?? 0;

    const nextRunElem = document.getElementById('census-next-scheduled-time');
    if (nextRunElem) nextRunElem.textContent = data.next_scheduled_run || '05:00 / 17:00 IST';

    const camOnlineElem = document.getElementById('census-cam-status-pill');
    if (camOnlineElem) {
      camOnlineElem.className = `status-pill ${data.camera_online ? 'pill-active' : 'pill-inactive'}`;
      camOnlineElem.textContent = data.camera_online ? 'Camera Online' : 'Camera Offline';
    }

    const latest = data.latest_census;
    const statusPill = document.getElementById('census-latest-status-pill');
    const detectedElem = document.getElementById('census-detected-count');
    const diffElem = document.getElementById('census-diff-count');
    const lastTimeElem = document.getElementById('census-last-executed-time');

    if (!latest) {
      if (statusPill) {
        statusPill.className = 'census-status-pill status-unverified';
        statusPill.textContent = AppState.lang === 'hi' ? 'प्रतीक्षारत' : 'PENDING SCHEDULE';
      }
      if (detectedElem) detectedElem.textContent = '—';
      if (diffElem) diffElem.textContent = '—';
      if (lastTimeElem) lastTimeElem.textContent = 'Not yet executed';
      return;
    }

    if (detectedElem) detectedElem.textContent = latest.detected_count !== null ? latest.detected_count : '—';
    if (diffElem) {
      if (latest.difference === null) {
        diffElem.textContent = '—';
      } else if (latest.difference > 0) {
        diffElem.textContent = `+${latest.difference} (${AppState.lang === 'hi' ? 'अतिरिक्त' : 'Excess'})`;
        diffElem.style.color = 'var(--accent-amber)';
      } else if (latest.difference < 0) {
        diffElem.textContent = `${latest.difference} (${AppState.lang === 'hi' ? 'कमी' : 'Missing'})`;
        diffElem.style.color = 'var(--accent-rose)';
      } else {
        diffElem.textContent = `0 (${AppState.lang === 'hi' ? 'सटीक' : 'Perfect Match'})`;
        diffElem.style.color = 'var(--accent-emerald)';
      }
    }

    if (lastTimeElem) {
      lastTimeElem.textContent = `${latest.scheduled_time} (${formatDate(latest.executed_at)})`;
    }

    if (statusPill) {
      statusPill.className = `census-status-pill status-${latest.status.toLowerCase()}`;
      if (latest.status === 'MATCH') {
        statusPill.textContent = AppState.lang === 'hi' ? '✓ सत्यापित मिलान (MATCH)' : '✓ VERIFIED MATCH';
      } else if (latest.status === 'SHORTFALL') {
        statusPill.textContent = AppState.lang === 'hi' ? '⚠ गोवंश की कमी (SHORTFALL)' : '⚠ HERD SHORTFALL';
      } else if (latest.status === 'EXCESS') {
        statusPill.textContent = AppState.lang === 'hi' ? '⚠ अतिरिक्त गोवंश (EXCESS)' : '⚠ HERD EXCESS';
      } else {
        statusPill.textContent = AppState.lang === 'hi' ? '✕ असत्यापित (NOT VERIFIED)' : '✕ NOT VERIFIED';
      }
    }

    const mCard = document.getElementById('census-morning-status');
    if (mCard && data.last_morning) {
      mCard.innerHTML = formatCensusSessionSnippet(data.last_morning);
    }
    const eCard = document.getElementById('census-evening-status');
    if (eCard && data.last_evening) {
      eCard.innerHTML = formatCensusSessionSnippet(data.last_evening);
    }
  }

  function formatCensusSessionSnippet(record) {
    const isMatch = record.status === 'MATCH';
    const color = isMatch ? 'var(--accent-emerald)' : record.status === 'NOT_VERIFIED' ? 'var(--text-muted)' : 'var(--accent-rose)';
    return `
      <div class="session-snippet">
        <div class="d-flex justify-between items-center mb-1">
          <span class="badge-${record.status.toLowerCase()}">${record.status}</span>
          <span style="font-size:0.75rem; color:var(--text-muted);">${formatDate(record.executed_at)}</span>
        </div>
        <div style="font-size:0.85rem;">
          Expected: <strong>${record.expected_count}</strong> | Verified: <strong style="color:${color};">${record.detected_count ?? 'N/A'}</strong>
        </div>
      </div>
    `;
  }

  async function loadCensusHistoryTable() {
    const tbody = document.getElementById('census-history-tbody');
    if (!tbody) return;

    try {
      const historyData = await apiRequest('/api/census/history?limit=25');
      const records = historyData.records || [];

      if (records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4" style="color:var(--text-muted);">No census runs executed yet.</td></tr>`;
        return;
      }

      tbody.innerHTML = records.map(r => `
        <tr>
          <td><code style="font-size:0.75rem;">${escapeHtml(r.session_id)}</code></td>
          <td><span class="badge-enclosure">${escapeHtml(r.enclosure_name)}</span></td>
          <td><strong>${escapeHtml(r.scheduled_time)}</strong></td>
          <td style="font-size:0.8rem;">${formatDate(r.executed_at)}</td>
          <td>${r.expected_count}</td>
          <td><strong style="color:${r.status === 'MATCH' ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${r.detected_count !== null ? r.detected_count : '—'}</strong></td>
          <td>
            <span class="badge-${r.status.toLowerCase()}">${r.status}</span>
          </td>
        </tr>
      `).join('');

    } catch (err) {
      console.error('Error loading history:', err);
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-rose">Error loading history: ${err.message}</td></tr>`;
    }
  }

  async function handleRunDiagnosticCensus() {
    const btn = document.getElementById('btn-run-census-diagnostic');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-inline"></span> ${AppState.lang === 'hi' ? 'गणना जारी है...' : 'Executing Multi-Frame Capture...'}`;
    }

    try {
      const result = await apiRequest('/api/census/run-diagnostic', {
        method: 'POST',
        body: JSON.stringify({ capture_window_seconds: 5.0 })
      });

      showToast(
        AppState.lang === 'hi' 
          ? `जनगणना पूर्ण: अपेक्षित ${result.expected_count}, सत्यापित ${result.detected_count ?? 'N/A'} [${result.status}]`
          : `Census Completed: Expected ${result.expected_count}, Detected ${result.detected_count ?? 'N/A'} [${result.status}]`,
        result.status === 'MATCH' ? 'info' : 'warning'
      );

      await loadCensusAudit();
    } catch (err) {
      showToast(err.message, 'critical');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = AppState.lang === 'hi' ? '⚡ त्वरित नैदानिक जनगणना चलाएं' : '⚡ Run Diagnostic Census';
      }
    }
  }

  // -------------------------------------------------------------
  // 7. FEEDING COMPLIANCE & TROUGH MONITORING
  // -------------------------------------------------------------
  async function loadFeedingCompliance() {
    const schedTbody = document.getElementById('feeding-schedules-tbody');
    const obsTbody = document.getElementById('feeding-observations-tbody');

    try {
      const [schedules, observations] = await Promise.all([
        apiRequest('/api/feeding/schedules'),
        apiRequest('/api/feeding/observations?limit=20')
      ]);

      if (schedTbody) {
        if (!schedules || schedules.length === 0) {
          schedTbody.innerHTML = `<tr><td colspan="5" class="text-center py-3" style="color:var(--text-muted);">No feeding schedules configured.</td></tr>`;
        } else {
          schedTbody.innerHTML = schedules.map(s => `
            <tr>
              <td><strong>${escapeHtml(s.trough_name)}</strong></td>
              <td><span class="badge-enclosure">${escapeHtml(s.camera_id)}</span></td>
              <td><strong style="color:var(--accent-primary); font-size:1.05rem;">${escapeHtml(s.target_time)} IST</strong></td>
              <td>
                <span class="status-pill ${s.is_active ? 'pill-active' : 'pill-inactive'}">
                  ${s.is_active ? 'Active' : 'Disabled'}
                </span>
              </td>
              <td>
                <button class="btn-sm btn-ghost" onclick="CensusModule.runFeedingCheckFor(${s.id}, '${escapeHtml(s.camera_id)}', '${escapeHtml(s.trough_name)}')">
                  Inspect Trough
                </button>
              </td>
            </tr>
          `).join('');
        }
      }

      if (obsTbody) {
        if (!observations || observations.length === 0) {
          obsTbody.innerHTML = `<tr><td colspan="5" class="text-center py-3" style="color:var(--text-muted);">No feeding compliance checks logged yet.</td></tr>`;
        } else {
          obsTbody.innerHTML = observations.map(o => `
            <tr>
              <td><strong>${escapeHtml(o.trough_name)}</strong></td>
              <td style="font-size:0.8rem;">${formatDate(o.observed_at)}</td>
              <td>
                <span class="badge-${o.status.toLowerCase().replace('_', '-')}">
                  ${o.status}
                </span>
              </td>
              <td style="font-size:0.8rem; color:var(--text-muted);">
                ${escapeHtml(o.diagnostic_details?.inspection?.reason || o.diagnostic_details?.reason || 'Standard check')}
              </td>
              <td>
                ${o.alert_generated ? '<span class="status-pill pill-inactive">Alert Generated</span>' : '<span style="color:var(--text-muted);">None</span>'}
              </td>
            </tr>
          `).join('');
        }
      }

    } catch (err) {
      console.error('Error loading feeding compliance:', err);
    }
  }

  async function handleRunFeedingCheck() {
    await runFeedingCheckFor(null, 'cam-01', 'Feeder Trough A');
  }

  async function runFeedingCheckFor(scheduleId, cameraId, troughName) {
    const btn = document.getElementById('btn-run-feeding-check');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-inline"></span> Inspecting...`;
    }

    try {
      const res = await apiRequest('/api/feeding/check-now', {
        method: 'POST',
        body: JSON.stringify({
          schedule_id: scheduleId,
          camera_id: cameraId,
          trough_name: troughName
        })
      });

      showToast(
        AppState.lang === 'hi'
          ? `चारा निरीक्षण पूर्ण: [${res.status}]`
          : `Trough Inspection Result: [${res.status}]`,
        res.status === 'FEED_VISIBLE' ? 'info' : res.status === 'MISSED_FEEDING' ? 'critical' : 'warning'
      );

      await loadFeedingCompliance();
    } catch (err) {
      showToast(err.message, 'critical');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = AppState.lang === 'hi' ? '🔍 चारा अनुपालन जांचें' : '🔍 Check Feeding Compliance Now';
      }
    }
  }

  // Helpers
  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(AppState.lang === 'hi' ? 'hi-IN' : 'en-IN', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    } catch (e) {
      return isoStr;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }

  function debounce(fn, ms) {
    let timer;
    return function(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  return {
    init,
    refreshAll,
    switchSubTab,
    toggleStatus,
    deleteRecord,
    showQrBadge,
    openAddMedicalFor,
    deleteMedicalRecord,
    runFeedingCheckFor,
    openReconcileModal,
    openBulkImportModal,
    exportCattleCsv,
    exportAuditReport
  };
})();
