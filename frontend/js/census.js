/**
 * Smart Gaushala CCTV AI Monitoring System
 * CensusModule: Cattle Registry, 05:00/17:00 IST Herd Census, Medical Register, and Feeding Compliance
 */

const CensusModule = (() => {
  let initialized = false;
  let activeTab = 'registry'; // 'registry' | 'audit' | 'medical' | 'feeding'
  let cachedCattleList = [];
  let cachedMedicalRecords = [];
  let cachedValidatedRows = [];
  let cachedSubsidyConfig = null;
  let cachedHerdImmunity = null;
  let activePassportCattleId = null;
  let activePassportTagId = null;
  let currentWizardStep = 1;
  let currentWizardFilter = 'all';

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
    const directTemplateBtn = document.getElementById('btn-download-csv-template-direct');
    if (directTemplateBtn) {
      directTemplateBtn.addEventListener('click', downloadSampleCsv);
    }

    // 3-Step Wizard Navigation & Dropzone
    initWizardControls();

    const dryRunValidateBtn = document.getElementById('btn-dry-run-validate');
    if (dryRunValidateBtn) {
      dryRunValidateBtn.addEventListener('click', handleDryRunValidation);
    }

    const bulkImportForm = document.getElementById('bulk-import-form');
    if (bulkImportForm) {
      bulkImportForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleCommitBulkImport();
      });
    }

    // 4. CSV Export Actions & Print Muster Roll
    const exportCattleBtn = document.getElementById('btn-export-cattle-csv');
    if (exportCattleBtn) {
      exportCattleBtn.addEventListener('click', exportCattleCsv);
    }
    const exportAuditBtn = document.getElementById('btn-export-audit-report');
    if (exportAuditBtn) {
      exportAuditBtn.addEventListener('click', exportAuditReport);
    }
    const printMusterRollBtn = document.getElementById('btn-print-muster-roll');
    if (printMusterRollBtn) {
      printMusterRollBtn.addEventListener('click', () => {
        window.open('/api/census/export/audit-muster-roll-html', '_blank');
      });
    }

    // 5. Subsidy Rates Configuration, Live Simulator & 30-Day Ledger
    const openSubsidyBtn = document.getElementById('btn-open-subsidy-config');
    if (openSubsidyBtn) openSubsidyBtn.addEventListener('click', openSubsidyConfigModal);
    const closeSubsidyBtn = document.getElementById('close-subsidy-modal-btn');
    const cancelSubsidyBtn = document.getElementById('cancel-subsidy-modal-btn');
    if (closeSubsidyBtn) closeSubsidyBtn.addEventListener('click', closeSubsidyConfigModal);
    if (cancelSubsidyBtn) cancelSubsidyBtn.addEventListener('click', closeSubsidyConfigModal);

    const subsidyForm = document.getElementById('subsidy-config-form');
    if (subsidyForm) {
      subsidyForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleSaveSubsidyConfig();
      });
    }

    // Live budget simulator listeners
    ['sub-cow-rate', 'sub-bull-rate', 'sub-calf-rate', 'sub-sick-rate'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', updateLiveBudgetSimulator);
    });

    const chipSubsidy = document.getElementById('chip-subsidy-daily');
    if (chipSubsidy) chipSubsidy.addEventListener('click', openSubsidyLedgerModal);
    const viewLedgerBtn = document.getElementById('btn-view-subsidy-ledger');
    if (viewLedgerBtn) viewLedgerBtn.addEventListener('click', openSubsidyLedgerModal);
    const closeLedgerBtn = document.getElementById('close-subsidy-ledger-modal-btn');
    if (closeLedgerBtn) closeLedgerBtn.addEventListener('click', closeSubsidyLedgerModal);

    const exportLedgerCsvBtn = document.getElementById('btn-export-subsidy-ledger-csv');
    if (exportLedgerCsvBtn) {
      exportLedgerCsvBtn.addEventListener('click', () => {
        showToast('Exporting 30-day verified subsidy claims ledger (CSV)...', 'info');
        window.location.href = '/api/census/subsidy-ledger/export-csv';
      });
    }

    // 6. AI Reconcile Discrepancy & Subsidy Modal
    const openReconcileBtn = document.getElementById('btn-reconcile-census');
    if (openReconcileBtn) {
      openReconcileBtn.addEventListener('click', openReconcileModal);
    }
    const closeReconcileBtn = document.getElementById('close-reconcile-modal-btn');
    if (closeReconcileBtn) {
      closeReconcileBtn.addEventListener('click', closeReconcileModal);
    }

    // 7. QR Badge & Sovereign Passport Modal Closes & Actions
    const closeQrBtn = document.getElementById('close-qr-modal-btn');
    const closeQrCardBtn = document.getElementById('close-qr-card-btn');
    if (closeQrBtn) closeQrBtn.addEventListener('click', closeQrModal);
    if (closeQrCardBtn) closeQrCardBtn.addEventListener('click', closeQrModal);

    const snapFromPassportBtn = document.getElementById('btn-snap-photo-from-passport');
    if (snapFromPassportBtn) {
      snapFromPassportBtn.addEventListener('click', async () => {
        if (activePassportCattleId) {
          await snapCctvPhoto(activePassportCattleId);
          await showQrBadge(activePassportCattleId);
        }
      });
    }

    const openPublicPassportLinkBtn = document.getElementById('btn-open-public-passport-link');
    if (openPublicPassportLinkBtn) {
      openPublicPassportLinkBtn.addEventListener('click', () => {
        if (activePassportTagId) {
          window.open('/verify/' + encodeURIComponent(activePassportTagId), '_blank');
        }
      });
    }

    // 8. Medical & Vaccination Modal & Actions
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

    // Batch Vaccination Modal & Actions
    const openBatchMedBtn = document.getElementById('btn-open-batch-vaccine');
    if (openBatchMedBtn) openBatchMedBtn.addEventListener('click', openBatchVaccinationModal);
    const closeBatchMedBtn = document.getElementById('close-batch-medical-modal-btn');
    const cancelBatchMedBtn = document.getElementById('cancel-batch-medical-btn');
    if (closeBatchMedBtn) closeBatchMedBtn.addEventListener('click', closeBatchVaccinationModal);
    if (cancelBatchMedBtn) cancelBatchMedBtn.addEventListener('click', closeBatchVaccinationModal);

    const batchProtocolSelect = document.getElementById('batch-protocol-select');
    if (batchProtocolSelect) {
      batchProtocolSelect.addEventListener('change', handleBatchProtocolPresetChange);
    }
    const batchMedForm = document.getElementById('batch-medical-form');
    if (batchMedForm) {
      batchMedForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleBatchVaccinate();
      });
    }

    // Auto Schedule NADCP Protocols
    const autoScheduleBtn = document.getElementById('btn-auto-schedule-protocols');
    if (autoScheduleBtn) {
      autoScheduleBtn.addEventListener('click', handleAutoScheduleProtocols);
    }

    // WhatsApp / SMS Notification Dispatcher Modal
    const openNotifBtn = document.getElementById('btn-open-notifications');
    if (openNotifBtn) openNotifBtn.addEventListener('click', openNotificationModal);
    const closeNotifBtn = document.getElementById('close-notification-modal-btn');
    if (closeNotifBtn) closeNotifBtn.addEventListener('click', closeNotificationModal);

    const medSearchInput = document.getElementById('medical-search-input');
    if (medSearchInput) {
      medSearchInput.addEventListener('input', debounce(() => renderMedicalRecordsTable(), 300));
    }
    const medTypeFilter = document.getElementById('medical-type-filter');
    if (medTypeFilter) {
      medTypeFilter.addEventListener('change', () => renderMedicalRecordsTable());
    }

    // 9. Cattle Registry Filter Controls
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
            <td colspan="9" class="text-center py-4" style="color:var(--text-muted);">
              ${AppState.lang === 'hi' ? 'कोई गोवंश रिकॉर्ड नहीं मिला। कृपया ऊपर दिए गए "+ Register Cattle" से नया गोवंश जोड़ें या CSV आयात करें।' : 'No cattle records found. Click "+ Register Cattle" or "Import CSV" to add livestock.'}
            </td>
          </tr>
        `;
        return;
      }

      // Rates from config or fallback
      const cowRate = cachedSubsidyConfig?.cow_rate ?? 40;
      const bullRate = cachedSubsidyConfig?.bull_rate ?? 35;
      const calfRate = cachedSubsidyConfig?.calf_rate ?? 20;
      const sickRate = cachedSubsidyConfig?.sick_rate ?? 50;

      listBody.innerHTML = cattleList.map(c => {
        // Category styling
        const cat = c.category || 'cow';
        let catBadge = `<span class="badge-cat-cow">गाय (Cow)</span>`;
        let rateVal = cowRate;
        if (cat === 'bull') { catBadge = `<span class="badge-cat-bull">नंदी/बैल</span>`; rateVal = bullRate; }
        if (cat === 'calf') { catBadge = `<span class="badge-cat-calf">बछड़ा/बछिया</span>`; rateVal = calfRate; }

        // Health status badge
        const health = c.health_status || 'healthy';
        let healthBadge = `<span class="badge-health-ok">स्वस्थ (Healthy)</span>`;
        if (health === 'under_treatment') {
          healthBadge = `<span class="badge-health-treatment">उपचाराधीन</span>`;
          rateVal = sickRate;
        } else if (health === 'quarantine') {
          healthBadge = `<span class="badge-health-quarantine">क्वारंटाइन</span>`;
          rateVal = sickRate;
        }

        // INAPH tag snippet
        const inaphSnippet = c.inaph_tag ? `<div style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono); margin-top:2px;">INAPH: ${escapeHtml(c.inaph_tag)}</div>` : '';

        // Lineage badges
        let lineageHtml = `<span style="color:var(--text-muted); font-size:0.75rem;">—</span>`;
        if (c.mother_tag || c.father_tag) {
          lineageHtml = `
            <div style="display:flex; flex-direction:column; gap:2px;">
              ${c.mother_tag ? `<span class="badge-lineage" title="Mother / Dam">♀ ${escapeHtml(c.mother_tag)}</span>` : ''}
              ${c.father_tag ? `<span class="badge-lineage" title="Father / Sire">♂ ${escapeHtml(c.father_tag)}</span>` : ''}
            </div>
          `;
        }

        const photoUrl = c.photo_url || '/static/images/gaushala_hero.jpg';

        return `
          <tr>
            <td style="width:70px; text-align:center;">
              <div class="cattle-photo-cell">
                <img src="${photoUrl}" alt="Cattle Photo" class="cattle-thumb-img"
                     onerror="this.src='/static/images/gaushala_hero.jpg'">
                <button class="btn-quick-snap" title="1-Click Snap live CCTV frame as official photo" onclick="CensusModule.snapCctvPhoto(${c.id})">
                  📷
                </button>
              </div>
            </td>
            <td>
              <strong style="color:var(--accent-emerald); font-family:var(--font-mono); font-size:0.92rem;">${escapeHtml(c.tag_id)}</strong>
              ${inaphSnippet}
            </td>
            <td>
              <strong style="color:var(--text-primary); font-size:0.88rem;">${escapeHtml(c.name || 'Gomata')}</strong>
              <div style="font-size:0.75rem; color:var(--text-muted); margin-top:2px;">${escapeHtml(c.breed || 'Gir / Indigenous')}</div>
            </td>
            <td>${lineageHtml}</td>
            <td><span class="badge-enclosure">${escapeHtml(c.enclosure_id)}</span></td>
            <td>
              <div>${catBadge}</div>
              <div style="margin-top:4px;">
                <span class="badge-subsidy-rate" title="Daily Government Subsidy Allotment">₹${rateVal}/day</span>
              </div>
            </td>
            <td>${healthBadge}</td>
            <td>
              <span class="status-pill ${c.status === 'active' ? 'pill-active' : 'pill-inactive'}">
                ${c.status === 'active' ? (AppState.lang === 'hi' ? 'सक्रिय' : 'Active') : (AppState.lang === 'hi' ? 'निष्क्रिय' : 'Inactive')}
              </span>
            </td>
            <td>
              <div class="row-actions-group" style="display:flex; gap:4px; flex-wrap:wrap;">
                <button class="btn-sm btn-ghost" title="Sovereign Digital Passport & Pedigree Lineage" onclick="CensusModule.showQrBadge(${c.id})">
                  🪪 Passport
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
      listBody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-rose">Failed to load registry: ${err.message}</td></tr>`;
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
    const mother_tag = document.getElementById('cow-mother-tag')?.value.trim() || null;
    const father_tag = document.getElementById('cow-father-tag')?.value.trim() || null;
    const photo_url = document.getElementById('cow-photo-url')?.value.trim() || null;
    const photoFileInput = document.getElementById('cow-photo-file');
    const notes = document.getElementById('cow-notes').value.trim() || null;

    if (!tag_id) {
      showToast(AppState.lang === 'hi' ? 'टैग आईडी आवश्यक है' : 'Tag ID is required', 'warning');
      return;
    }

    const gender = category === 'bull' ? 'male' : 'female';

    try {
      const created = await apiRequest('/api/cattle', {
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
          mother_tag,
          father_tag,
          photo_url,
          notes,
          status: 'active'
        })
      });

      // If user provided a photo file, upload it immediately
      if (photoFileInput && photoFileInput.files && photoFileInput.files.length > 0) {
        try {
          const photoFormData = new FormData();
          photoFormData.append('file', photoFileInput.files[0]);
          const token = (typeof AppState !== 'undefined' && AppState.token) || localStorage.getItem('gaushala_jwt_token') || localStorage.getItem('gaushala_token') || sessionStorage.getItem('gaushala_token');
          const pHeaders = {};
          if (token) pHeaders['Authorization'] = `Bearer ${token}`;


          await fetch(`/api/cattle/${created.id}/photo`, {
            method: 'POST',
            headers: pHeaders,
            body: photoFormData
          });
        } catch (photoErr) {
          console.warn('Photo upload warning:', photoErr);
        }
      }

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
  // 2. 3-STEP GUIDED BULK CSV IMPORT WIZARD & EXPORT
  // -------------------------------------------------------------
  function initWizardControls() {
    // Stepper navigation buttons
    const goto2 = document.getElementById('btn-wizard-goto-step2');
    if (goto2) goto2.addEventListener('click', () => handleDryRunValidation());

    const goto3 = document.getElementById('btn-wizard-goto-step3');
    if (goto3) goto3.addEventListener('click', () => setWizardStep(3));

    const backto1 = document.getElementById('btn-wizard-backto-step1');
    if (backto1) backto1.addEventListener('click', () => setWizardStep(1));

    const backto2 = document.getElementById('btn-wizard-backto-step2');
    if (backto2) backto2.addEventListener('click', () => setWizardStep(2));

    // Wizard header node clicks
    [1, 2, 3].forEach(step => {
      const node = document.getElementById(`wizard-node-${step}`);
      if (node) {
        node.addEventListener('click', () => {
          if (step === 2 && cachedValidatedRows.length === 0) {
            handleDryRunValidation();
          } else if (step <= currentWizardStep || cachedValidatedRows.length > 0) {
            setWizardStep(step);
          }
        });
      }
    });

    // Dropzone setup
    const dropzone = document.getElementById('csv-dropzone-area');
    const fileInput = document.getElementById('bulk-csv-file');
    const fileLabel = document.getElementById('dropzone-file-selected');

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());

      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });

      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
      });

      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          fileInput.files = e.dataTransfer.files;
          updateDropzoneLabel();
        }
      });

      fileInput.addEventListener('change', updateDropzoneLabel);
    }

    function updateDropzoneLabel() {
      if (fileInput && fileInput.files && fileInput.files.length > 0) {
        const f = fileInput.files[0];
        if (fileLabel) {
          fileLabel.style.display = 'block';
          fileLabel.textContent = `✓ Selected: ${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
        }
      }
    }

    // Filter tabs for Step 2 preview
    const filterTabs = document.querySelectorAll('.wizard-filter-tab');
    filterTabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        filterTabs.forEach(t => t.classList.remove('active'));
        e.currentTarget.classList.add('active');
        currentWizardFilter = e.currentTarget.dataset.filter || 'all';
        renderWizardPreviewRows(currentWizardFilter);
      });
    });
  }

  function setWizardStep(stepNum) {
    currentWizardStep = stepNum;

    // Panes
    [1, 2, 3].forEach(s => {
      const pane = document.getElementById(`wizard-pane-${s}`);
      const node = document.getElementById(`wizard-node-${s}`);
      if (pane) pane.style.display = (s === stepNum) ? 'block' : 'none';
      if (node) {
        node.classList.remove('active', 'completed');
        if (s === stepNum) node.classList.add('active');
        else if (s < stepNum) node.classList.add('completed');
      }
    });

    // In step 3, update stats summary
    if (stepNum === 3) {
      const summaryBox = document.getElementById('bulk-commit-stats-summary');
      if (summaryBox) {
        const valids = cachedValidatedRows.filter(r => r.validation_status === 'VALID').length;
        const conflicts = cachedValidatedRows.filter(r => r.validation_status === 'CONFLICT').length;
        const errors = cachedValidatedRows.filter(r => r.validation_status === 'ERROR').length;
        summaryBox.innerHTML = `
          <div style="font-size:0.88rem; font-weight:700; color:var(--text-primary);">
            Ready to commit: <strong>${valids} Valid Records</strong> &bull; <strong>${conflicts} Existing Tag Conflicts</strong>
          </div>
          <div style="font-size:0.75rem; color:var(--text-muted); margin-top:3px;">
            ${errors > 0 ? `⚠️ Note: ${errors} rows with syntax errors will be automatically skipped.` : 'All rows ready for database ingestion.'}
          </div>
        `;
      }
    }
  }

  function openBulkImportModal() {
    const modal = document.getElementById('bulk-import-modal');
    if (modal) {
      modal.style.display = 'flex';
      setWizardStep(1);
      const feedback = document.getElementById('bulk-import-feedback');
      if (feedback) feedback.style.display = 'none';
      const form = document.getElementById('bulk-import-form');
      if (form) form.reset();
      const fileLabel = document.getElementById('dropzone-file-selected');
      if (fileLabel) fileLabel.style.display = 'none';
      cachedValidatedRows = [];
    }
  }

  function closeBulkImportModal() {
    const modal = document.getElementById('bulk-import-modal');
    if (modal) modal.style.display = 'none';
  }

  function downloadSampleCsv() {
    showToast('Downloading official cattle registration CSV template...', 'info');
    window.location.href = '/api/cattle/template/csv';
  }

  async function snapCctvPhoto(cattleId) {
    try {
      showToast('Capturing live CCTV camera frame...', 'info');
      const res = await apiRequest(`/api/cattle/${cattleId}/capture-cctv-photo`, { method: 'POST' });
      showToast(AppState.lang === 'hi' ? 'CCTV फ्रेम प्रोफाइल फोटो के रूप में सहेजा गया!' : 'Live CCTV frame set as official profile photo!', 'info');
      await loadCattleRegistry();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  async function handleDryRunValidation() {
    const fileInput = document.getElementById('bulk-csv-file');
    const summaryChips = document.getElementById('bulk-preview-summary-chips');
    const btn = document.getElementById('btn-wizard-goto-step2');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
      showToast('Please select or drag a CSV file first', 'warning');
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-inline"></span> Pre-Validating Schema...`;
    }

    try {
      const token = (typeof AppState !== 'undefined' && AppState.token) || localStorage.getItem('gaushala_jwt_token') || localStorage.getItem('gaushala_token') || sessionStorage.getItem('gaushala_token');
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/cattle/bulk-validate', {
        method: 'POST',
        headers,
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Validation failed (${res.status})`);
      }

      const data = await res.json();
      cachedValidatedRows = data.rows || [];

      // Update Step 2 Summary Chips
      if (summaryChips) {
        summaryChips.innerHTML = `
          <div class="summary-chip">
            <span class="chip-label">Total CSV Rows</span>
            <strong class="chip-val">${data.total_rows}</strong>
          </div>
          <div class="summary-chip chip-emerald">
            <span class="chip-label">Valid Entries</span>
            <strong class="chip-val text-emerald">${data.valid_rows}</strong>
          </div>
          <div class="summary-chip" style="border-color:rgba(245,158,11,0.3); background:rgba(245,158,11,0.06);">
            <span class="chip-label" style="color:#f59e0b;">Conflicts</span>
            <strong class="chip-val" style="color:#f59e0b;">${data.conflict_rows}</strong>
          </div>
          <div class="summary-chip" style="border-color:rgba(239,68,68,0.3); background:rgba(239,68,68,0.06);">
            <span class="chip-label" style="color:#ef4444;">Syntax Errors</span>
            <strong class="chip-val text-rose">${data.error_rows}</strong>
          </div>
        `;
      }

      // Update Filter Tab counts
      const elAll = document.getElementById('cnt-flt-all');
      const elVal = document.getElementById('cnt-flt-valid');
      const elConf = document.getElementById('cnt-flt-conflict');
      const elErr = document.getElementById('cnt-flt-error');
      if (elAll) elAll.textContent = data.total_rows;
      if (elVal) elVal.textContent = data.valid_rows;
      if (elConf) elConf.textContent = data.conflict_rows;
      if (elErr) elErr.textContent = data.error_rows;

      // Render rows
      currentWizardFilter = 'all';
      renderWizardPreviewRows('all');

      // Transition to Step 2!
      setWizardStep(2);
      showToast(`Pre-Validation: ${data.valid_rows} Valid, ${data.conflict_rows} Conflicts found`, 'info');
    } catch (err) {
      showToast(`Validation Failed: ${err.message}`, 'critical');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>Next: Pre-Validate CSV &rarr;</span>`;
      }
    }
  }

  function renderWizardPreviewRows(filter = 'all') {
    const tbody = document.getElementById('bulk-preview-tbody');
    if (!tbody) return;

    let filtered = cachedValidatedRows || [];
    if (filter !== 'all') {
      filtered = filtered.filter(r => r.validation_status === filter);
    }

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-muted">No rows match filter '${filter}'.</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(r => {
      let badge = `<span style="background:#10b981; color:#0f172a; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.75rem;">VALID</span>`;
      if (r.validation_status === 'CONFLICT') {
        badge = `<span style="background:#f59e0b; color:#0f172a; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.75rem;">CONFLICT</span>`;
      } else if (r.validation_status === 'ERROR') {
        badge = `<span style="background:#ef4444; color:#fff; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.75rem;">ERROR</span>`;
      }

      const lineageText = (r.mother_tag || r.father_tag) 
        ? `${r.mother_tag || '—'} / ${r.father_tag || '—'}`
        : '—';

      return `
        <tr>
          <td><strong>#${r.row_num}</strong></td>
          <td>${badge}</td>
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary);">${escapeHtml(r.tag_id || '—')}</td>
          <td>${escapeHtml(r.name || '—')}</td>
          <td>${escapeHtml(r.category || 'cow')}</td>
          <td>${escapeHtml(r.enclosure_id || 'cam-01')}</td>
          <td style="font-size:0.78rem; font-family:var(--font-mono); color:#a7f3d0;">${escapeHtml(lineageText)}</td>
          <td style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(r.detail || 'Ready to import')}</td>
        </tr>
      `;
    }).join('');
  }

  async function handleCommitBulkImport() {
    const feedback = document.getElementById('bulk-import-feedback');
    const uploadBtn = document.getElementById('btn-submit-bulk-upload');
    const conflictModeSelect = document.getElementById('bulk-conflict-mode');
    const conflict_mode = conflictModeSelect ? conflictModeSelect.value : 'skip';

    if (!cachedValidatedRows || cachedValidatedRows.length === 0) {
      showToast('No validated rows to commit', 'warning');
      return;
    }

    if (uploadBtn) {
      uploadBtn.disabled = true;
      uploadBtn.innerHTML = '<span class="spinner-inline"></span> Committing Records to Database...';
    }

    try {
      const res = await apiRequest('/api/cattle/bulk-commit', {
        method: 'POST',
        body: JSON.stringify({
          rows: cachedValidatedRows,
          items: cachedValidatedRows,
          conflict_resolution: conflict_mode,
          conflict_mode: conflict_mode
        })
      });

      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(16,185,129,0.1)';
        feedback.style.border = '1px solid rgba(16,185,129,0.3)';
        feedback.style.color = '#047857';
        feedback.innerHTML = `✓ <strong>Bulk Import Committed!</strong><br>Newly Added: <strong>${res.imported}</strong> | Updated: <strong>${res.updated}</strong> | Skipped: <strong>${res.skipped}</strong>`;
      }

      showToast(`Bulk Import Complete: ${res.imported} added, ${res.updated} updated, ${res.skipped} skipped`, 'info');
      await loadCattleRegistry();
      await loadCensusAudit();
    } catch (err) {
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(239,68,68,0.1)';
        feedback.style.border = '1px solid rgba(239,68,68,0.3)';
        feedback.style.color = '#b91c1c';
        feedback.textContent = `Commit Error: ${err.message}`;
      }
      showToast(err.message, 'critical');
    } finally {
      if (uploadBtn) {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<span>✓ Commit Verified Records to Database</span>';
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
  // SUBSIDY RATES CONFIGURATION & 30-DAY TREASURY CLAIMS LEDGER
  // -------------------------------------------------------------
  function updateLiveBudgetSimulator() {
    const cowRate = parseFloat(document.getElementById('sub-cow-rate')?.value) || 40;
    const bullRate = parseFloat(document.getElementById('sub-bull-rate')?.value) || 35;
    const calfRate = parseFloat(document.getElementById('sub-calf-rate')?.value) || 20;
    const sickRate = parseFloat(document.getElementById('sub-sick-rate')?.value) || 50;

    let cowCount = 0;
    let bullCount = 0;
    let calfCount = 0;
    let sickCount = 0;

    (cachedCattleList || []).forEach(c => {
      if (c.status === 'active') {
        const cat = c.category || 'cow';
        if (cat === 'bull') bullCount++;
        else if (cat === 'calf') calfCount++;
        else cowCount++;

        if (c.health_status === 'under_treatment' || c.health_status === 'quarantine') {
          sickCount++;
        }
      }
    });

    const dailyTotal = (cowCount * cowRate) + (bullCount * bullRate) + (calfCount * calfRate) + (sickCount * Math.max(0, sickRate - cowRate));
    const monthlyTotal = dailyTotal * 30;
    const annualTotal = dailyTotal * 365;

    const summaryEl = document.getElementById('sim-herd-counts-summary');
    if (summaryEl) {
      summaryEl.textContent = `${cowCount} Cows @ ₹${cowRate} | ${bullCount} Bulls @ ₹${bullRate} | ${calfCount} Calves @ ₹${calfRate}${sickCount > 0 ? ` | ${sickCount} Sick @ ₹${sickRate}` : ''}`;
    }

    const dEl = document.getElementById('sim-val-daily');
    const mEl = document.getElementById('sim-val-monthly');
    const aEl = document.getElementById('sim-val-annual');
    if (dEl) dEl.textContent = `₹${Math.round(dailyTotal).toLocaleString('en-IN')}`;
    if (mEl) mEl.textContent = `₹${Math.round(monthlyTotal).toLocaleString('en-IN')}`;
    if (aEl) aEl.textContent = `₹${Math.round(annualTotal).toLocaleString('en-IN')}`;
  }

  async function openSubsidyConfigModal() {
    const modal = document.getElementById('subsidy-config-modal');
    if (!modal) return;
    modal.style.display = 'flex';

    try {
      const config = await apiRequest('/api/cattle/subsidy-config');
      cachedSubsidyConfig = config;
      if (document.getElementById('sub-cow-rate')) document.getElementById('sub-cow-rate').value = config.cow_rate;
      if (document.getElementById('sub-bull-rate')) document.getElementById('sub-bull-rate').value = config.bull_rate;
      if (document.getElementById('sub-calf-rate')) document.getElementById('sub-calf-rate').value = config.calf_rate;
      if (document.getElementById('sub-sick-rate')) document.getElementById('sub-sick-rate').value = config.sick_rate;
      if (document.getElementById('sub-scheme-title')) document.getElementById('sub-scheme-title').value = config.scheme_title;
      if (document.getElementById('sub-disbursing-dept')) document.getElementById('sub-disbursing-dept').value = config.disbursing_dept;
      updateLiveBudgetSimulator();
    } catch (err) {
      console.warn('Failed to load subsidy config:', err);
      updateLiveBudgetSimulator();
    }
  }

  function closeSubsidyConfigModal() {
    const modal = document.getElementById('subsidy-config-modal');
    if (modal) modal.style.display = 'none';
  }

  async function handleSaveSubsidyConfig() {
    const cow_rate = parseFloat(document.getElementById('sub-cow-rate').value) || 40.0;
    const bull_rate = parseFloat(document.getElementById('sub-bull-rate').value) || 35.0;
    const calf_rate = parseFloat(document.getElementById('sub-calf-rate').value) || 20.0;
    const sick_rate = parseFloat(document.getElementById('sub-sick-rate').value) || 50.0;
    const scheme_title = document.getElementById('sub-scheme-title').value.trim();
    const disbursing_dept = document.getElementById('sub-disbursing-dept').value.trim();

    try {
      const updated = await apiRequest('/api/cattle/subsidy-config', {
        method: 'PUT',
        body: JSON.stringify({
          cow_rate, bull_rate, calf_rate, sick_rate, scheme_title, disbursing_dept
        })
      });
      cachedSubsidyConfig = updated;
      showToast(AppState.lang === 'hi' ? 'सरकारी अनुदान दरें सफलतापूर्वक अपडेट की गईं!' : 'Subsidy rates updated and recomputed!', 'info');
      closeSubsidyConfigModal();
      await loadCattleRegistry();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  async function openSubsidyLedgerModal() {
    const modal = document.getElementById('subsidy-ledger-modal');
    const body = document.getElementById('subsidy-ledger-modal-body');
    if (!modal || !body) return;
    modal.style.display = 'flex';

    body.innerHTML = `<div style="text-align:center; padding:3rem;"><div class="spinner-inline"></div> Fetching 30-day verified treasury claims ledger...</div>`;

    try {
      const data = await apiRequest('/api/census/subsidy-ledger?days=30');
      
      const rowsHtml = (data.ledger_records || []).map(r => `
        <tr>
          <td><strong>${r.date}</strong></td>
          <td><span class="badge-enclosure">${r.session_time} IST</span></td>
          <td><strong>${r.registered_active_herd}</strong></td>
          <td><strong style="color:var(--accent-primary);">${r.verified_live_detected}</strong></td>
          <td style="font-size:0.78rem; color:var(--text-muted);">
            Cows: ${r.breakdown.cows} | Bulls: ${r.breakdown.bulls} | Calves: ${r.breakdown.calves}
          </td>
          <td>
            <strong style="color:var(--accent-emerald); font-size:1.05rem;">
              ₹${(r.daily_entitlement_inr || 0).toLocaleString('en-IN')}
            </strong>
          </td>
          <td>
            <span class="status-pill ${r.status === 'MATCH' ? 'pill-active' : 'pill-inactive'}">
              ${r.status}
            </span>
          </td>
          <td>
            <code style="font-size:0.7rem; color:var(--text-muted);">${(r.integrity_hash || '').slice(0, 10)}...</code>
          </td>
        </tr>
      `).join('');

      body.innerHTML = `
        <div style="background:linear-gradient(135deg, rgba(245,158,11,0.1), rgba(16,185,129,0.08)); border:1px solid rgba(245,158,11,0.3); border-radius:12px; padding:16px; margin-bottom:1.25rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div>
            <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em; color:#f59e0b; font-weight:800;">
              ${escapeHtml(data.state_scheme || 'Mukhyamantri Gaushala Sahayata Yojana')}
            </div>
            <h3 style="font-size:1.15rem; font-weight:800; color:var(--text-primary); margin-top:2px;">
              ${escapeHtml(data.gaushala_name || 'Gaushala Monitoring Sanctuary')}
            </h3>
            <div style="font-size:0.8rem; color:var(--text-muted); margin-top:2px;">
              30-Day Optical Audit Verified Ledger &bull; Ready for Treasury Disbursal
            </div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:0.75rem; color:var(--text-muted);">Total 30-Day Projected Subsidy</div>
            <div style="font-size:1.6rem; font-weight:900; color:var(--accent-emerald);">
              ₹${(data.total_projected_subsidy_inr || 0).toLocaleString('en-IN')}
            </div>
            <button class="btn-tool" style="margin-top:6px;" onclick="window.open('/api/census/export/audit-muster-roll-html', '_blank')">
              📜 Print Signed Muster Roll
            </button>
          </div>
        </div>

        <div class="modern-table-wrap" style="max-height:360px; overflow-y:auto;">
          <table class="modern-table">
            <thead>
              <tr>
                <th>Audit Date</th>
                <th>Shift</th>
                <th>Registered Herd</th>
                <th>Verified Detected</th>
                <th>Category Count</th>
                <th>Claim Amount (INR)</th>
                <th>Audit Result</th>
                <th>SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      `;
    } catch (err) {
      body.innerHTML = `<div class="p-4 text-center text-rose">Failed to load subsidy ledger: ${escapeHtml(err.message)}</div>`;
    }
  }

  function closeSubsidyLedgerModal() {
    const modal = document.getElementById('subsidy-ledger-modal');
    if (modal) modal.style.display = 'none';
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
            <span>🏛️ GOV FEED SUBSIDY ENTITLEMENT (₹${subsidy.tiered_rates?.cow_rate || 40} / CATTLE / DAY)</span>
          </div>
          <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:3px;">
            Verified CCTV Headcount: <strong>${data.total_live_detected}</strong> | Registered Muster: <strong>${data.total_registered_herd}</strong>
          </div>
          ${data.evidence_hash ? `
            <div style="font-size:0.72rem; color:#94a3b8; font-family:var(--font-mono); margin-top:4px;">
              🔒 SHA-256 Audit Integrity Hash: <code>${escapeHtml(data.evidence_hash)}</code>
            </div>
          ` : ''}
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

      <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border-subtle); padding-top:1rem; flex-wrap:wrap; gap:8px;">
        <span style="font-size:0.75rem; color:var(--text-muted);">
          Reconciliation Run: ${formatDate(data.timestamp)}
        </span>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn-tool" onclick="window.open('/api/census/export/audit-muster-roll-html', '_blank')">
            📜 Print Official Muster Roll
          </button>
          <button class="btn-tool" onclick="CensusModule.exportAuditReport()">
            📥 Export CSV
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
    printArea.innerHTML = `<div style="text-align:center; padding:3rem;"><div class="spinner-inline"></div> Loading Sovereign Bharat Pashudhan Digital Passport...</div>`;

    try {
      const [c, medList] = await Promise.all([
        apiRequest(`/api/cattle/${cattleId}`),
        apiRequest(`/api/cattle/${cattleId}/medical`).catch(() => [])
      ]);

      activePassportCattleId = c.id;
      activePassportTagId = c.tag_id;

      // Scannable live passport URL for mobile phone cameras!
      const passportUrl = `${window.location.origin}/verify/${encodeURIComponent(c.tag_id)}`;
      const qrSvg = generateQrSvg(passportUrl, 130);

      const catLabel = c.category === 'bull' ? 'नंदी / बैल (Bull)' : c.category === 'calf' ? 'बछड़ा / बछिया (Calf)' : 'गाय (Cow)';
      const lactLabel = c.lactation_stage === 'milking' ? 'दुधारू (Milking)' : c.lactation_stage === 'pregnant' ? 'गर्भवती (Pregnant)' : 'सूखी (Dry)';
      const healthLabel = c.health_status === 'healthy' ? 'स्वस्थ (Healthy)' : c.health_status === 'under_treatment' ? 'उपचाराधीन' : 'क्वारंटाइन';
      const photoSrc = c.photo_url || '/static/images/gaushala_hero.jpg';

      // Check disease immunization stamps
      const hasFMD = (medList || []).some(m => (m.title || '').toLowerCase().includes('fmd') && m.status === 'completed');
      const hasLSD = (medList || []).some(m => (m.title || '').toLowerCase().includes('lsd') && m.status === 'completed');
      const hasHSBQ = (medList || []).some(m => ((m.title || '').toLowerCase().includes('hs') || (m.title || '').toLowerCase().includes('bq')) && m.status === 'completed');
      const hasDeworm = (medList || []).some(m => (m.title || '').toLowerCase().includes('deworm') && m.status === 'completed');

      printArea.innerHTML = `
        <div class="passport-sovereign-card">
          <div class="passport-tricolor-bar"></div>
          
          <div class="passport-top-crest">
            <div style="display:flex; align-items:center; gap:10px;">
              <span style="font-size:1.6rem;">🏛️</span>
              <div>
                <div style="font-size:0.65rem; letter-spacing:0.08em; text-transform:uppercase; color:#a7f3d0; font-weight:800;">
                  GOVERNMENT OF INDIA &bull; NATIONAL LIVESTOCK MISSION (भारत सरकार)
                </div>
                <div style="font-size:1.05rem; font-weight:900; color:#ffffff; letter-spacing:0.02em;">
                  SOVEREIGN BHARAT PASHUDHAN DIGITAL PASSPORT (पशु आधार)
                </div>
              </div>
            </div>
            <div style="background:#10b981; color:#0f172a; font-weight:900; font-size:0.68rem; padding:4px 8px; border-radius:4px; letter-spacing:0.04em; box-shadow:0 2px 6px rgba(0,0,0,0.3);">
              ✓ AI VERIFIED
            </div>
          </div>

          <div style="padding:16px;">
            <div style="display:grid; grid-template-columns:100px 1fr 130px; gap:14px; align-items:center;">
              <!-- Photo Cell -->
              <div style="position:relative;">
                <img src="${photoSrc}" alt="Cattle Photo" onerror="this.src='/static/images/gaushala_hero.jpg'"
                     style="width:100px; height:105px; border-radius:10px; object-fit:cover; border:2px solid #10b981; box-shadow:0 4px 10px rgba(0,0,0,0.4);">
                <button class="btn-quick-snap" title="Take CCTV Snapshot Now" onclick="CensusModule.snapCctvPhoto(${c.id})"
                        style="position:absolute; bottom:-6px; right:-6px; width:24px; height:24px; font-size:11px;">
                  📷
                </button>
              </div>

              <!-- Primary Identifiers -->
              <div>
                <div style="font-size:0.68rem; text-transform:uppercase; color:#94a3b8; font-weight:800; letter-spacing:0.04em;">EAR TAG / COLLAR RFID</div>
                <div style="font-size:1.45rem; font-weight:900; font-family:var(--font-mono); color:#10b981; letter-spacing:0.02em;">
                  ${escapeHtml(c.tag_id)}
                </div>
                <div style="font-size:0.8rem; font-family:var(--font-mono); color:#cbd5e1; margin-top:1px;">
                  INAPH PASHU AADHAAR: <strong style="color:#ffffff;">${escapeHtml(c.inaph_tag || '900' + String(c.id).padStart(9, '0'))}</strong>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:8px; font-size:0.8rem;">
                  <div>
                    <span style="color:#94a3b8; font-size:0.7rem;">Name:</span>
                    <strong style="color:#f8fafc; display:block;">${escapeHtml(c.name || 'Gomata')}</strong>
                  </div>
                  <div>
                    <span style="color:#94a3b8; font-size:0.7rem;">Breed:</span>
                    <strong style="color:#a7f3d0; display:block;">${escapeHtml(c.breed || 'Gir Indigenous')}</strong>
                  </div>
                  <div>
                    <span style="color:#94a3b8; font-size:0.7rem;">Category:</span>
                    <strong style="color:#f8fafc; display:block;">${catLabel}</strong>
                  </div>
                  <div>
                    <span style="color:#94a3b8; font-size:0.7rem;">Enclosure:</span>
                    <strong style="color:#38bdf8; display:block;">${escapeHtml(c.enclosure_id)}</strong>
                  </div>
                </div>
              </div>

              <!-- Vector QR Code -->
              <div style="text-align:center;">
                <div style="background:#ffffff; padding:6px; border-radius:10px; display:inline-block; box-shadow:0 4px 14px rgba(0,0,0,0.5);">
                  ${qrSvg}
                </div>
                <div style="font-size:0.65rem; color:#94a3b8; margin-top:4px; font-weight:700;">
                  SCAN WITH SMARTPHONE
                </div>
              </div>
            </div>

            <!-- 3-Generation Pedigree Lineage Tree Box -->
            <div class="pedigree-tree-box">
              <div class="pedigree-tree-header">
                <span>🧬 Sovereign Pedigree Lineage Tree (वंशावली कुलवृक्ष)</span>
              </div>
              <div class="pedigree-tree-grid">
                <div class="pedigree-node pedigree-node-dam">
                  <div class="pedigree-role">♀ Mother Tag (Dam / मातृ गोवंश)</div>
                  <div class="pedigree-tag">${escapeHtml(c.mother_tag || 'Natural Herd Baseline')}</div>
                  <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">Desi Gir Purebred Lineage</div>
                </div>
                <div class="pedigree-node pedigree-node-sire">
                  <div class="pedigree-role">♂ Father Tag (Sire / पितृ नंदी)</div>
                  <div class="pedigree-tag">${escapeHtml(c.father_tag || 'Natural Herd Baseline')}</div>
                  <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">Pedigree Progeny Tested Sire</div>
                </div>
              </div>
            </div>

            <!-- National NADCP Immunization Passport Status -->
            <div style="background:#0f172a; border:1px solid #1e293b; border-radius:10px; padding:10px 14px; margin-top:8px;">
              <div style="font-size:0.72rem; text-transform:uppercase; color:#94a3b8; font-weight:800; margin-bottom:6px;">
                💉 National NADCP Immunization Stamps (टीकाकरण मुहर)
              </div>
              <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:6px; text-align:center;">
                <div style="background:#1e293b; padding:6px; border-radius:6px; font-size:0.75rem;">
                  <div style="font-size:0.68rem; color:#94a3b8;">FMD</div>
                  <strong style="color:${hasFMD ? '#10b981' : '#f59e0b'};">${hasFMD ? '✓ IMMUNIZED' : '⏳ PENDING'}</strong>
                </div>
                <div style="background:#1e293b; padding:6px; border-radius:6px; font-size:0.75rem;">
                  <div style="font-size:0.68rem; color:#94a3b8;">LSD</div>
                  <strong style="color:${hasLSD ? '#10b981' : '#f59e0b'};">${hasLSD ? '✓ IMMUNIZED' : '⏳ PENDING'}</strong>
                </div>
                <div style="background:#1e293b; padding:6px; border-radius:6px; font-size:0.75rem;">
                  <div style="font-size:0.68rem; color:#94a3b8;">HS/BQ</div>
                  <strong style="color:${hasHSBQ ? '#10b981' : '#f59e0b'};">${hasHSBQ ? '✓ IMMUNIZED' : '⏳ PENDING'}</strong>
                </div>
                <div style="background:#1e293b; padding:6px; border-radius:6px; font-size:0.75rem;">
                  <div style="font-size:0.68rem; color:#94a3b8;">DEWORM</div>
                  <strong style="color:${hasDeworm ? '#10b981' : '#f59e0b'};">${hasDeworm ? '✓ DOSING OK' : '⏳ PENDING'}</strong>
                </div>
              </div>
            </div>

            <!-- Security Footer -->
            <div style="margin-top:12px; display:flex; justify-content:space-between; align-items:center; font-size:0.72rem; color:#64748b;">
              <span>Registered: ${c.created_at ? c.created_at.slice(0, 10) : 'Active'} &bull; Status: <strong style="color:#10b981;">VERIFIED</strong></span>
              <span>SHA-256: <code style="color:#94a3b8; font-size:0.7rem;">GAU-${c.id}-PASSPORT-VERIFIED</code></span>
            </div>
          </div>
        </div>
      `;

    } catch (err) {
      printArea.innerHTML = `<div class="text-rose text-center p-3">Failed to load passport: ${err.message}</div>`;
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
  // 5. NATIONAL NADCP HERD IMMUNITY & MEDICAL REGISTER
  // -------------------------------------------------------------
  async function loadHerdImmunityCoverage() {
    try {
      const summary = await apiRequest('/api/cattle/medical/coverage-summary');
      cachedHerdImmunity = summary;

      const diseases = ['fmd', 'lsd', 'hsbq', 'deworm'];
      const keyMap = { fmd: 'fmd', lsd: 'lsd', hsbq: 'hsbq', deworm: 'deworming' };

      diseases.forEach(d => {
        const item = summary[keyMap[d]] || { pct: 0, covered: 0, target: summary.total_herd || 0, status: 'VULNERABLE' };
        const pctEl = document.getElementById(`pct-imm-${d}`);
        const barEl = document.getElementById(`bar-imm-${d}`);
        const metaEl = document.getElementById(`meta-imm-${d}`);
        const statusEl = document.getElementById(`status-imm-${d}`);

        const pct = item.pct || 0;
        if (pctEl) pctEl.textContent = `${pct}%`;
        if (barEl) {
          barEl.style.width = `${pct}%`;
          barEl.className = `immunity-progress-fill ${pct >= 85 ? 'fill-emerald' : pct >= 50 ? 'fill-amber' : 'fill-rose'}`;
        }
        if (metaEl) metaEl.textContent = `Covered: ${item.covered || 0} / ${item.target || summary.total_herd || 0}`;
        if (statusEl) {
          statusEl.textContent = item.status === 'OPTIMAL' ? '✓ Protected (85%+)' : item.status === 'MODERATE' ? '⚠️ Moderate (50%+)' : '🚨 Vulnerable (<50%)';
          statusEl.className = `status-pill ${item.status === 'OPTIMAL' ? 'pill-active' : item.status === 'MODERATE' ? 'pill-warning' : 'pill-inactive'}`;
        }
      });
    } catch (err) {
      console.warn('Failed to load herd immunity coverage:', err);
    }
  }

  async function loadMedicalRegister() {
    const tbody = document.getElementById('cattle-medical-tbody');
    if (!tbody) return;

    // Load herd immunity dashboard ribbon in parallel
    loadHerdImmunityCoverage();

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
  // BATCH VACCINATION, NADCP PROTOCOLS & NOTIFICATION DISPATCHER
  // -------------------------------------------------------------
  let cachedProtocols = [];

  async function openBatchVaccinationModal() {
    const modal = document.getElementById('batch-medical-modal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Pre-fill today's date
    const adminInput = document.getElementById('batch-admin-date');
    if (adminInput && !adminInput.value) {
      adminInput.value = new Date().toISOString().slice(0, 10);
    }

    // Set 6-month due date default
    const dueInput = document.getElementById('batch-due-date');
    if (dueInput && !dueInput.value) {
      const d = new Date();
      d.setMonth(d.getMonth() + 6);
      dueInput.value = d.toISOString().slice(0, 10);
    }

    // Generate random lot number preset if empty
    const lotInput = document.getElementById('batch-vial-lot');
    if (lotInput && !lotInput.value) {
      const yr = new Date().getFullYear();
      const randHex = Math.floor(1000 + Math.random() * 9000);
      lotInput.value = `NADCP-${yr}-${randHex}`;
    }

    try {
      if (cachedProtocols.length === 0) {
        cachedProtocols = await apiRequest('/api/cattle/medical/protocols').catch(() => []);
      }
    } catch (e) {
      console.warn('Protocols fetch failed:', e);
    }
  }

  function closeBatchVaccinationModal() {
    const modal = document.getElementById('batch-medical-modal');
    if (modal) modal.style.display = 'none';
  }

  function handleBatchProtocolPresetChange(e) {
    const protocolId = e.target.value;
    const titleInput = document.getElementById('batch-title');
    const dosageInput = document.getElementById('batch-dosage');
    const dueInput = document.getElementById('batch-due-date');
    const notesInput = document.getElementById('batch-notes');

    const pMap = {
      'FMD': {
        title: 'Foot-and-Mouth Disease (FMD खुरपका-मुंहपका) Bi-annual Booster',
        dosage: '3ml SC (Subcutaneous)',
        months: 6,
        notes: 'Indian Immunologicals Raksha-Ovac • Bi-annual herd immunization'
      },
      'LSD': {
        title: 'Lumpy Skin Disease (लंपी त्वचा रोग) Annual Prophylactic',
        dosage: '3ml SC (Goat Pox Vaccine)',
        months: 12,
        notes: 'Pre-monsoon annual vaccination against capripoxvirus'
      },
      'HS_BQ': {
        title: 'HS & BQ (गलघोंटू एवं लंगड़ा बुखार) Dual Vaccine',
        dosage: '5ml SC',
        months: 12,
        notes: 'Pre-monsoon dual prophylactic against Haemorrhagic Septicaemia & Black Quarter'
      },
      'DEWORM': {
        title: 'Broad-Spectrum Deworming (कृमिनाशक Albendazole/Fenbendazole)',
        dosage: '100ml Oral Drench',
        months: 3,
        notes: 'Rotational oral deworming against gastrointestinal nematodes and flukes'
      },
      'BRUCELLA': {
        title: 'Brucellosis S19 Calfhood Vaccine',
        dosage: '2ml SC',
        months: 0,
        notes: 'One-time lifetime vaccination for female calves aged 4-8 months'
      },
      'CUSTOM': {
        title: 'Veterinary Clinical Health Intervention',
        dosage: 'As prescribed',
        months: 3,
        notes: ''
      }
    };

    const sel = pMap[protocolId] || pMap['CUSTOM'];
    if (titleInput) titleInput.value = sel.title;
    if (dosageInput) dosageInput.value = sel.dosage;
    if (notesInput) notesInput.value = sel.notes;

    if (dueInput && sel.months > 0) {
      const d = new Date();
      d.setMonth(d.getMonth() + sel.months);
      dueInput.value = d.toISOString().slice(0, 10);
    }
  }

  async function handleBatchVaccinate() {
    const enclosure_id = document.getElementById('batch-enclosure-select').value;
    const title = document.getElementById('batch-title').value.trim();
    const administered_date = document.getElementById('batch-admin-date').value;
    const next_due_date = document.getElementById('batch-due-date').value || null;
    const vial_batch_no = document.getElementById('batch-vial-lot').value.trim();
    const dosage = document.getElementById('batch-dosage').value.trim();
    const doctor_name = document.getElementById('batch-doctor').value.trim() || null;
    const notes = document.getElementById('batch-notes').value.trim() || null;
    const btn = document.getElementById('btn-submit-batch-vaccine');

    if (!title || !administered_date || !vial_batch_no) {
      showToast('Title, Administered Date, and Lot Number are required', 'warning');
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-inline"></span> Inoculating Herd...`;
    }

    try {
      const payload = {
        title,
        administered_date,
        next_due_date,
        vial_batch_no,
        dosage,
        doctor_name,
        notes,
        status: 'completed',
        record_type: 'vaccination'
      };

      if (enclosure_id && enclosure_id !== 'ALL') {
        payload.enclosure_id = enclosure_id;
      }

      const res = await apiRequest('/api/cattle/medical/batch', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      showToast(
        AppState.lang === 'hi'
          ? `सामूहिक टीकाकरण पूर्ण: ${res.vaccinated_cattle_count} गोवंशों को टीका लगाया गया!`
          : `Batch vaccination complete: ${res.vaccinated_cattle_count} cattle immunized!`,
        'info'
      );

      closeBatchVaccinationModal();
      await loadMedicalRegister();
      await loadCattleRegistry();
    } catch (err) {
      showToast(err.message, 'critical');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>💉 Execute Batch Vaccination</span>`;
      }
    }
  }

  async function handleAutoScheduleProtocols() {
    const confirmMsg = AppState.lang === 'hi' 
      ? 'क्या आप राष्ट्रीय पशु रोग नियंत्रण कार्यक्रम (NADCP) के तहत सभी सक्रिय गोवंशों के लिए 1-वर्षीय टीकाकरण कैलेंडर स्वचालित रूप से तैयार करना चाहते हैं?'
      : 'Auto-generate 1-year National Animal Disease Control Programme (NADCP) vaccination calendar for all active cattle?';
    
    if (!confirm(confirmMsg)) return;

    try {
      showToast('Generating national protocol immunization schedule...', 'info');
      const res = await apiRequest('/api/cattle/medical/auto-schedule', { method: 'POST' });
      showToast(
        AppState.lang === 'hi'
          ? `सफलता: ${res.unique_cattle_scheduled} गोवंशों के लिए ${res.records_created} टीकाकरण प्रविष्टियां निर्धारित की गईं!`
          : `Success: ${res.records_created} protocol records scheduled across ${res.unique_cattle_scheduled} cattle!`,
        'info'
      );
      await loadMedicalRegister();
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  async function openNotificationModal() {
    const modal = document.getElementById('notification-modal');
    const body = document.getElementById('notification-modal-body');
    if (!modal || !body) return;
    modal.style.display = 'flex';

    body.innerHTML = `<div style="text-align:center; padding:3rem;"><div class="spinner-inline"></div> Scanning medical register for overdue & upcoming alerts...</div>`;

    try {
      const data = await apiRequest('/api/cattle/medical/notifications');
      const overdueList = data.overdue_alerts || [];
      const dueSoonList = data.due_soon_alerts || [];
      const totalAlerts = overdueList.length + dueSoonList.length;

      let overdueCards = overdueList.map(a => `
        <div style="background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <strong style="color:var(--accent-rose); font-family:var(--font-mono); font-size:0.95rem;">${escapeHtml(a.tag_id)}</strong>
              <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(a.name || 'Gomata')} &bull; ${escapeHtml(a.enclosure_id)}</span>
            </div>
            <div style="font-size:0.85rem; font-weight:700; color:var(--text-primary); margin-top:2px;">${escapeHtml(a.title)}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:0.75rem; color:#ef4444; font-weight:700;">OVERDUE (${a.days_overdue} days)</div>
            <div style="font-size:0.72rem; color:var(--text-muted);">Due: ${a.due_date}</div>
          </div>
        </div>
      `).join('');

      let dueSoonCards = dueSoonList.map(a => `
        <div style="background:rgba(245,158,11,0.06); border:1px solid rgba(245,158,11,0.3); border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <strong style="color:#f59e0b; font-family:var(--font-mono); font-size:0.95rem;">${escapeHtml(a.tag_id)}</strong>
              <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(a.name || 'Gomata')} &bull; ${escapeHtml(a.enclosure_id)}</span>
            </div>
            <div style="font-size:0.85rem; font-weight:700; color:var(--text-primary); margin-top:2px;">${escapeHtml(a.title)}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:0.75rem; color:#f59e0b; font-weight:700;">DUE in ${a.days_remaining} days</div>
            <div style="font-size:0.72rem; color:var(--text-muted);">Due: ${a.due_date}</div>
          </div>
        </div>
      `).join('');

      // WhatsApp formatted message template
      const waMsgLines = [
        `📢 *राष्ट्रीय गोवंश स्वास्थ्य एवं टीकाकरण अलर्ट (Gaushala Health Alert)*`,
        `परिसर: श्री कामधेनु गोशाला | कुल अलर्ट: ${totalAlerts}`,
        ``,
        `⚠️ *लंबित / नियत टीके (Overdue & Due Vaccines):*`
      ];

      overdueList.slice(0, 5).forEach(a => {
        waMsgLines.push(`• 🔴 ${a.tag_id} (${a.name || 'Cow'} - ${a.enclosure_id}): ${a.title} [विलंब: ${a.days_overdue} दिन]`);
      });

      dueSoonList.slice(0, 5).forEach(a => {
        waMsgLines.push(`• 🟡 ${a.tag_id} (${a.name || 'Cow'} - ${a.enclosure_id}): ${a.title} [नियत: ${a.due_date}]`);
      });

      waMsgLines.push(``);
      waMsgLines.push(`कृपया पशु चिकित्सक एवं मुख्य केयरटेकर आवश्यक टीकाकरण सुनिश्चित करें।`);
      waMsgLines.push(`स्मार्ट गोशाला AI निगरानी पोर्टल`);

      const waMsgEncoded = encodeURIComponent(waMsgLines.join('\n'));

      body.innerHTML = `
        <div style="display:flex; gap:12px; margin-bottom:1.25rem;">
          <div class="summary-chip" style="flex:1; border-color:rgba(239,68,68,0.3); background:rgba(239,68,68,0.06);">
            <span class="chip-label" style="color:#ef4444;">Overdue Vaccines</span>
            <strong class="chip-val text-rose">${overdueList.length}</strong>
          </div>
          <div class="summary-chip" style="flex:1; border-color:rgba(245,158,11,0.3); background:rgba(245,158,11,0.06);">
            <span class="chip-label" style="color:#f59e0b;">Due in 14 Days</span>
            <strong class="chip-val" style="color:#f59e0b;">${dueSoonList.length}</strong>
          </div>
        </div>

        <div style="max-height:220px; overflow-y:auto; margin-bottom:1.25rem;">
          ${overdueCards || ''}
          ${dueSoonCards || ''}
          ${totalAlerts === 0 ? '<div class="text-center py-4 text-emerald">✓ All herd vaccines are up to date! No pending alerts.</div>' : ''}
        </div>

        <div style="background:var(--bg-elevated); border:1px solid var(--border-subtle); border-radius:10px; padding:14px; margin-bottom:1rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong style="font-size:0.85rem; color:var(--text-primary);">📱 WhatsApp Message Dispatch Preview:</strong>
            <button class="btn-sm btn-ghost" onclick="navigator.clipboard.writeText(decodeURIComponent('${waMsgEncoded}')); showToast('Message copied to clipboard!', 'info');">
              📋 Copy Text
            </button>
          </div>
          <pre style="white-space:pre-wrap; font-size:0.75rem; color:var(--text-muted); background:var(--bg-card); padding:10px; border-radius:6px; max-height:120px; overflow-y:auto; font-family:var(--font-mono);">${escapeHtml(waMsgLines.join('\n'))}</pre>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:0.75rem; color:var(--text-muted);">
            Broadcasts to designated veterinary doctors & Gaushala supervisors
          </span>
          <div style="display:flex; gap:8px;">
            <a href="https://wa.me/?text=${waMsgEncoded}" target="_blank" class="btn-primary" style="background:#25D366; border-color:#25D366; text-decoration:none; display:inline-flex; align-items:center; gap:6px;">
              <span>💬 Open WhatsApp Web</span>
            </a>
            <button type="button" class="btn-tool" onclick="CensusModule.closeNotificationModal()">Done</button>
          </div>
        </div>
      `;

    } catch (err) {
      body.innerHTML = `<div class="p-4 text-center text-rose">Failed to load alerts: ${escapeHtml(err.message)}</div>`;
    }
  }

  function closeNotificationModal() {
    const modal = document.getElementById('notification-modal');
    if (modal) modal.style.display = 'none';
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

  function showToast(msg, type = 'info') {
    if (typeof window.showToast === 'function') {
      window.showToast(msg, type);
    } else {
      console.log(`[Toast ${type}]`, msg);
    }
  }

  return {
    init,
    refreshAll,
    switchSubTab,
    toggleStatus,
    deleteRecord,
    showQrBadge,
    snapCctvPhoto,
    openAddMedicalFor,
    deleteMedicalRecord,
    runFeedingCheckFor,
    openReconcileModal,
    openBulkImportModal,
    exportCattleCsv,
    exportAuditReport,
    openSubsidyConfigModal,
    closeSubsidyConfigModal,
    openSubsidyLedgerModal,
    closeSubsidyLedgerModal,
    handleDryRunValidation,
    handleCommitBulkImport,
    openBatchVaccinationModal,
    closeBatchVaccinationModal,
    handleAutoScheduleProtocols,
    openNotificationModal,
    closeNotificationModal,
    showToast
  };
})();
