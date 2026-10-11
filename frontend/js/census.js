/**
 * Smart Gaushala CCTV AI Monitoring System
 * CensusModule: Cattle Registry, 05:00/17:00 IST Herd Census, and Feeding Compliance
 */

const CensusModule = (() => {
  let initialized = false;
  let activeTab = 'registry'; // 'registry' | 'census' | 'feeding'

  function init() {
    if (!initialized) {
      bindEvents();
      initialized = true;
    }
    refreshAll();
  }

  function bindEvents() {
    // Sub-tab toggles inside Census View
    const subTabBtns = document.querySelectorAll('.census-subtab-btn');
    subTabBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const subtab = e.currentTarget.dataset.subtab;
        switchSubTab(subtab);
      });
    });

    // Register Cattle Button (Open Modal)
    const openAddCattleBtn = document.getElementById('btn-open-add-cattle');
    if (openAddCattleBtn) {
      openAddCattleBtn.addEventListener('click', () => {
        openCattleModal();
      });
    }

    // Modal Close buttons
    const closeModalBtn = document.getElementById('close-cattle-modal-btn');
    const cancelModalBtn = document.getElementById('cancel-cattle-modal-btn');
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeCattleModal);
    if (cancelModalBtn) cancelModalBtn.addEventListener('click', closeCattleModal);

    // Cattle Registration Form Submit
    const cattleForm = document.getElementById('cattle-registration-form');
    if (cattleForm) {
      cattleForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleRegisterCattle();
      });
    }

    // Run Census Diagnostic Button
    const runDiagBtn = document.getElementById('btn-run-census-diagnostic');
    if (runDiagBtn) {
      runDiagBtn.addEventListener('click', async () => {
        await handleRunDiagnosticCensus();
      });
    }

    // Run Feeding Check Now Button
    const runFeedBtn = document.getElementById('btn-run-feeding-check');
    if (runFeedBtn) {
      runFeedBtn.addEventListener('click', async () => {
        await handleRunFeedingCheck();
      });
    }

    // Search input in registry
    const searchInput = document.getElementById('cattle-search-input');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(() => {
        loadCattleRegistry();
      }, 300));
    }

    // Filter status in registry
    const filterStatus = document.getElementById('cattle-status-filter');
    if (filterStatus) {
      filterStatus.addEventListener('change', () => {
        loadCattleRegistry();
      });
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
    if (subtab === 'feeding') loadFeedingCompliance();
  }

  async function refreshAll() {
    await Promise.allSettled([
      loadCattleRegistry(),
      loadCensusAudit(),
      loadFeedingCompliance()
    ]);
  }

  // -------------------------------------------------------------
  // 1. CATTLE REGISTRY
  // -------------------------------------------------------------
  async function loadCattleRegistry() {
    const listBody = document.getElementById('cattle-registry-tbody');
    if (!listBody) return;

    const searchInput = document.getElementById('cattle-search-input');
    const filterStatus = document.getElementById('cattle-status-filter');
    const search = searchInput ? searchInput.value.trim() : '';
    const statusVal = filterStatus ? filterStatus.value : '';

    let url = '/api/cattle?';
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (statusVal) url += `status=${encodeURIComponent(statusVal)}&`;

    try {
      const [cattleList, summary] = await Promise.all([
        apiRequest(url),
        apiRequest('/api/cattle/summary')
      ]);

      // Update summary chips
      updateRegistrySummaryChips(summary);

      if (!cattleList || cattleList.length === 0) {
        listBody.innerHTML = `
          <tr>
            <td colspan="7" class="text-center py-4" style="color:var(--text-muted);">
              ${AppState.lang === 'hi' ? 'कोई गोवंश रिकॉर्ड नहीं मिला। कृपया ऊपर दिए गए बटन से नया गोवंश जोड़ें।' : 'No cattle records found. Click "+ Register Cattle" to add genuine livestock.'}
            </td>
          </tr>
        `;
        return;
      }

      listBody.innerHTML = cattleList.map(c => `
        <tr>
          <td><strong style="color:var(--accent-emerald);">${escapeHtml(c.tag_id)}</strong></td>
          <td>${escapeHtml(c.name || '—')}</td>
          <td><span class="badge-enclosure">${escapeHtml(c.enclosure_id)}</span></td>
          <td>${escapeHtml(c.breed || 'Gir / Indigenous')}</td>
          <td>
            <span class="status-pill ${c.status === 'active' ? 'pill-active' : 'pill-inactive'}">
              ${c.status === 'active' ? (AppState.lang === 'hi' ? 'सक्रिय' : 'Active') : (AppState.lang === 'hi' ? 'निष्क्रिय' : 'Inactive')}
            </span>
          </td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${formatDate(c.created_at)}</td>
          <td>
            <div class="row-actions-group">
              <button class="btn-sm btn-ghost" title="${c.status === 'active' ? 'Mark Inactive' : 'Mark Active'}" onclick="CensusModule.toggleStatus(${c.id})">
                ${c.status === 'active' ? (AppState.lang === 'hi' ? 'निष्क्रिय करें' : 'Deactivate') : (AppState.lang === 'hi' ? 'सक्रिय करें' : 'Activate')}
              </button>
              <button class="btn-sm btn-danger-ghost" title="Delete" onclick="CensusModule.deleteRecord(${c.id})">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `).join('');

    } catch (err) {
      console.error('Error loading cattle registry:', err);
      listBody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-rose">Failed to load registry: ${err.message}</td></tr>`;
    }
  }

  function updateRegistrySummaryChips(summary) {
    if (!summary) return;
    const totalElem = document.getElementById('reg-total-cows');
    const activeElem = document.getElementById('reg-active-cows');
    const inactiveElem = document.getElementById('reg-inactive-cows');

    if (totalElem) totalElem.textContent = summary.total_registered ?? 0;
    if (activeElem) activeElem.textContent = summary.active_herd ?? 0;
    if (inactiveElem) inactiveElem.textContent = summary.inactive_herd ?? 0;

    // Update main dashboard metric if available
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
    const name = document.getElementById('cow-name').value.trim();
    const enclosure_id = document.getElementById('cow-enclosure').value.trim();
    const breed = document.getElementById('cow-breed').value.trim();
    const notes = document.getElementById('cow-notes').value.trim();

    if (!tag_id) {
      showToast(AppState.lang === 'hi' ? 'टैग आईडी आवश्यक है' : 'Tag ID is required', 'warning');
      return;
    }

    try {
      await apiRequest('/api/cattle', {
        method: 'POST',
        body: JSON.stringify({ tag_id, name, enclosure_id, breed, notes, status: 'active' })
      });
      showToast(AppState.lang === 'hi' ? `गोवंश ${tag_id} सफलतापूर्वक पंजीकृत किया गया!` : `Cattle ${tag_id} registered successfully!`, 'info');
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
    } catch (err) {
      showToast(err.message, 'critical');
    }
  }

  // -------------------------------------------------------------
  // 2. HERD CENSUS AUDIT (05:00 & 17:00 IST)
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

    // Active Registered Herd
    const regHerdElem = document.getElementById('census-registered-count');
    if (regHerdElem) regHerdElem.textContent = data.active_registered_herd ?? 0;

    // Next scheduled run
    const nextRunElem = document.getElementById('census-next-scheduled-time');
    if (nextRunElem) nextRunElem.textContent = data.next_scheduled_run || '05:00 / 17:00 IST';

    // Camera online state
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

    // Set detected & difference
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

    // Morning Card (05:00)
    const mCard = document.getElementById('census-morning-status');
    if (mCard && data.last_morning) {
      mCard.innerHTML = formatCensusSessionSnippet(data.last_morning);
    }

    // Evening Card (17:00)
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
  // 3. FEEDING COMPLIANCE & TROUGH MONITORING
  // -------------------------------------------------------------
  async function loadFeedingCompliance() {
    const schedTbody = document.getElementById('feeding-schedules-tbody');
    const obsTbody = document.getElementById('feeding-observations-tbody');

    try {
      const [schedules, observations] = await Promise.all([
        apiRequest('/api/feeding/schedules'),
        apiRequest('/api/feeding/observations?limit=20')
      ]);

      // Render Schedules
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

      // Render Observations
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
    runFeedingCheckFor
  };
})();
