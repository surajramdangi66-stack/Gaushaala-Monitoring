/**
 * Smart Gaushala Monitoring - Dashboard Module
 * Dedicated Overview: Live herd KPIs, Enclosure Telemetry, and Real-Time CCTV AI Detections & Quick Access Register.
 */
const DashboardModule = {
  initialized: false,
  currentFilter: 'all',
  lastDetections: null,

  init() {
    if (this.initialized) return;
    this.initialized = true;
    this.setupFilterButtons();
    this.refreshDashboard();
    this.fetchDetections();
  },

  setupFilterButtons() {
    const buttons = document.querySelectorAll('.det-filter-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.currentFilter = btn.dataset.filter || 'all';
        if (this.lastDetections) {
          this.renderDetectionsTable(this.lastDetections);
        }
      });
    });
  },

  async refreshDashboard() {
    try {
      const metrics = await apiRequest('/api/metrics/summary');
      this.updateTelemetry(metrics);
    } catch (err) {
      console.debug('Dashboard refresh err:', err);
    }
  },

  async fetchDetections() {
    try {
      const data = await apiRequest('/api/detections/live');
      this.updateDetections(data);
    } catch (err) {
      console.debug('Fetch detections err:', err);
    }
  },

  getZoneName(name, lang = 'en') {
    if (!name) return 'General Enclosure';
    if (lang === 'hi') {
      if (name.includes('Shed A')) return 'शेड A - मुख्य बाड़ा';
      if (name.includes('Shed B')) return 'शेड B - चारागाह बे';
      if (name.includes('Paddock') || name.includes('Yard')) return 'खुला चारागाह परिसर';
      if (name.includes('Medical') || name.includes('Calving')) return 'प्रसूति एवं चिकित्सा वार्ड';
      return name;
    }
    return name;
  },

  inspectCamera(camId) {
    if (typeof switchTab === 'function') {
      switchTab('monitor');
    }
  },

  updateTelemetry(metrics) {
    if (!metrics) return;
    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    // 1. KPI Metric Numbers
    const totalElem = document.getElementById('metric-total-cattle');
    const activeElem = document.getElementById('metric-active-cattle');
    const restingElem = document.getElementById('metric-resting-cattle');
    const statusElem = document.getElementById('metric-system-status');

    if (totalElem) totalElem.textContent = metrics.total_cattle ?? 0;
    if (activeElem) activeElem.textContent = metrics.active_cattle ?? 0;
    if (restingElem) restingElem.textContent = metrics.resting_cattle ?? 0;
    if (statusElem) {
      statusElem.textContent = `${metrics.cameras_online ?? 0}/${metrics.cameras_total ?? 0}`;
    }

    // 2. Enclosure Operations & Telemetry Table (Clean, Full-Width)
    const tableBody = document.getElementById('telemetry-table-body');
    if (tableBody) {
      tableBody.innerHTML = '';
      const zones = (metrics.zones && Array.isArray(metrics.zones)) ? metrics.zones : [];
      if (zones.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4" style="color:var(--text-muted);">${isHi ? 'कोई सक्रिय बाड़ा या कैमरा उपलब्ध नहीं है।' : 'No active enclosure zones configured.'}</td></tr>`;
        return;
      }

      zones.forEach(zone => {
        const total = zone.total ?? 0;
        const active = zone.active ?? 0;
        const resting = zone.resting ?? 0;
        const activePercent = total > 0 ? Math.round((active / total) * 100) : 0;
        const restingPercent = total > 0 ? Math.round((resting / total) * 100) : 0;
        const isAlert = zone.health === 'Alert';
        const localizedName = this.getZoneName(zone.name, lang);

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${localizedName}</strong></td>
          <td><code class="code-badge">DL-${String(zone.camera_id || '01').toUpperCase()}</code></td>
          <td><strong>${total}</strong> <span class="text-muted" style="font-size:0.75rem;">${isHi ? 'गोवंश' : 'Cattle'}</span> <span style="margin:0 4px; color:var(--text-muted); opacity:0.6;">|</span> <strong style="color:#f59e0b;">${zone.workers ?? 0}</strong> <span class="text-muted" style="font-size:0.75rem;">${isHi ? 'स्टाफ' : 'Staff'}</span></td>
          <td>
            <div class="tbl-ratio-bar-wrap">
              <div class="tbl-ratio-bar">
                <div class="tbl-fill-active" style="width: ${activePercent}%;"></div>
                <div class="tbl-fill-resting" style="width: ${restingPercent}%;"></div>
              </div>
              <span class="tbl-ratio-text">${active} ${isHi ? 'सक्रिय' : 'Act'} / ${resting} ${isHi ? 'विश्राम' : 'Rest'}</span>
            </div>
          </td>
          <td>${zone.feeder ?? 0} / 4 <span class="text-muted" style="font-size:0.75rem;">${isHi ? 'गर्त' : 'Bunks'}</span></td>
          <td>
            <span class="chip-status ${isAlert ? 'status-danger' : 'status-safe'}">
              ${isAlert ? (isHi ? '⚠ परिधि उल्लंघन' : '⚠ Geofence Breach') : (isHi ? '✓ सुरक्षित' : '✓ Secure')}
            </span>
          </td>
          <td style="text-align:right;">
            <button class="btn-tbl-inspect" onclick="DashboardModule.inspectCamera('${zone.camera_id}')">
              ${isHi ? 'लाइव देखें' : 'View Stream'}
            </button>
          </td>
        `;
        tableBody.appendChild(tr);
      });
    }
  },

  updateDetections(data) {
    if (!data) return;
    this.lastDetections = data;

    // 1. Update quick access metric badges
    const workerBadge = document.getElementById('qa-worker-count');
    const cattleBadge = document.getElementById('qa-cattle-count');
    const entriesBadge = document.getElementById('qa-entries-count');

    if (workerBadge) workerBadge.textContent = data.active_workers ?? 0;
    if (cattleBadge) cattleBadge.textContent = data.active_animals ?? 0;
    if (entriesBadge) entriesBadge.textContent = data.total_entries_today ?? 0;

    // Filter button counts
    const countAll = document.getElementById('count-filter-all');
    const countWorkers = document.getElementById('count-filter-workers');
    const countCattle = document.getElementById('count-filter-cattle');

    if (countAll) countAll.textContent = data.active_count ?? 0;
    if (countWorkers) countWorkers.textContent = data.active_workers ?? 0;
    if (countCattle) countCattle.textContent = data.active_animals ?? 0;

    // 2. Render table rows according to active filter
    this.renderDetectionsTable(data);
  },

  renderDetectionsTable(data) {
    const tableBody = document.getElementById('live-detections-table-body');
    if (!tableBody) return;

    const inside = data.inside || [];
    const recent = data.recent_events || [];

    let displayList = [];
    if (this.currentFilter === 'all') {
      displayList = inside;
    } else if (this.currentFilter === 'workers') {
      displayList = inside.filter(i => i.entity_type === 'worker');
    } else if (this.currentFilter === 'cattle') {
      displayList = inside.filter(i => i.entity_type === 'animal');
    } else if (this.currentFilter === 'history') {
      displayList = recent;
    }

    if (displayList.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align:center; padding:1.75rem; color:var(--text-muted);">
            <div style="font-size:1.4rem; margin-bottom:0.35rem;">📡</div>
            <div>No active detections in this filter. AI monitors feeds in real time without repeating records.</div>
          </td>
        </tr>
      `;
      return;
    }

    tableBody.innerHTML = '';
    displayList.forEach(item => {
      const isWorker = (item.entity_type === 'worker');
      const isInside = (item.status === 'INSIDE');

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          ${isWorker
            ? `<span class="entity-badge-worker">👷 ${item.entity_id}</span>`
            : `<span class="entity-badge-cattle">🐄 ${item.entity_id}</span>`
          }
        </td>
        <td>
          <strong>${item.label || (isWorker ? 'Gaushala Staff' : 'Desi Cattle')}</strong>
          <span style="font-size:0.75rem; color:var(--text-muted); display:block;">${item.breed || (isWorker ? 'Worker' : 'Indigenous')}</span>
        </td>
        <td>
          <code class="code-badge">${(item.camera_id || 'CAM-01').toUpperCase()}</code>
          <span style="font-size:0.75rem; color:var(--text-secondary); margin-left:4px;">${item.camera_name || 'Pen'}</span>
        </td>
        <td>
          <span style="font-family:var(--font-mono); font-size:0.82rem; color:var(--text-primary); font-weight:600;">
            ${item.entry_time ? item.entry_time.split(' ')[1] || item.entry_time : '--:--:--'}
          </span>
          <span style="font-size:0.7rem; color:var(--text-muted); display:block;">${item.entry_time ? item.entry_time.split(' ')[0] : ''}</span>
        </td>
        <td>
          ${isInside
            ? `<span style="color:#059669; font-weight:700; font-size:0.8rem; display:inline-flex; align-items:center; gap:4px;"><span class="pulse-dot-green" style="width:6px; height:6px;"></span> Present</span>`
            : `<span style="font-family:var(--font-mono); font-size:0.82rem; color:var(--text-muted);">${item.exit_time ? item.exit_time.split(' ')[1] || item.exit_time : '--:--:--'}</span>`
          }
        </td>
        <td>
          <span style="font-family:var(--font-mono); font-weight:600; font-size:0.82rem; color:var(--text-secondary);">
            ${item.duration_formatted || `${Math.round(item.duration_seconds || 0)}s`}
          </span>
        </td>
        <td>
          ${isInside
            ? `<span class="status-pulse-inside"><span class="pulse-dot-green"></span> INSIDE</span>`
            : `<span class="status-pill-exited">EXITED</span>`
          }
        </td>
      `;
      tableBody.appendChild(tr);
    });
  }
};
