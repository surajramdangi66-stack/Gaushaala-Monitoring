/**
 * Smart Gaushala Monitoring - Dashboard Module
 * Dedicated Overview: Live herd KPIs and clean full-width enclosure operations table.
 */
const DashboardModule = {
  initialized: false,

  init() {
    if (this.initialized) return;
    this.initialized = true;
    this.refreshDashboard();
  },

  async refreshDashboard() {
    try {
      const metrics = await apiRequest('/api/metrics/summary');
      this.updateTelemetry(metrics);
    } catch (err) {
      console.debug('Dashboard refresh err:', err);
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
      statusElem.textContent = `${metrics.cameras_online ?? 0}/${metrics.cameras_total ?? 4}`;
    }

    // 2. Enclosure Operations & Telemetry Table (Clean, Full-Width)
    const tableBody = document.getElementById('telemetry-table-body');
    if (tableBody) {
      tableBody.innerHTML = '';
      const zones = (metrics.zones && metrics.zones.length > 0)
        ? metrics.zones
        : [
            { camera_id: '01', name: 'Shed A - Main Herd', total: 0, active: 0, resting: 0, feeder: 0, health: 'Nominal' },
            { camera_id: '02', name: 'Shed B - Milking Bay', total: 0, active: 0, resting: 0, feeder: 0, health: 'Nominal' },
            { camera_id: '03', name: 'Open Grazing Paddock', total: 0, active: 0, resting: 0, feeder: 0, health: 'Nominal' },
            { camera_id: '04', name: 'Calving & Medical Pen', total: 0, active: 0, resting: 0, feeder: 0, health: 'Nominal' }
          ];

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
          <td><code class="code-badge">CAM-${String(zone.camera_id || '01').toUpperCase()}</code></td>
          <td><strong>${total}</strong> <span class="text-muted" style="font-size:0.75rem;">${isHi ? 'गोवंश' : 'Heads'}</span></td>
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
  }
};
