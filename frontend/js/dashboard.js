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

  updateTelemetry(metrics) {
    if (!metrics) return;
    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    // 1. Summary Metrics Numbers
    const totalElem = document.getElementById('metric-total-cattle');
    const activeElem = document.getElementById('metric-active-cattle');
    const restingElem = document.getElementById('metric-resting-cattle');
    const statusElem = document.getElementById('metric-system-status');
    const headerStatus = document.getElementById('header-system-status');

    if (totalElem) totalElem.textContent = metrics.total_cattle;
    if (activeElem) activeElem.textContent = metrics.active_cattle;
    if (restingElem) restingElem.textContent = metrics.resting_cattle;
    if (statusElem) {
      statusElem.textContent = `${metrics.cameras_online}/${metrics.cameras_total} ${isHi ? 'सक्रिय' : 'Active'}`;
    }
    if (headerStatus) {
      headerStatus.textContent = `${metrics.cameras_online}/${metrics.cameras_total} ${isHi ? 'ऑनलाइन' : 'Online'}`;
    }

    // 2. Zone Breakdown Cards
    const zonesContainer = document.getElementById('zones-breakdown-container');
    if (zonesContainer && metrics.zones) {
      zonesContainer.innerHTML = '';
      metrics.zones.forEach(zone => {
        const activePercent = zone.total > 0 ? Math.round((zone.active / zone.total) * 100) : 0;
        const restingPercent = zone.total > 0 ? Math.round((zone.resting / zone.total) * 100) : 0;
        const isAlert = zone.health === 'Alert';
        const localizedName = this.getZoneName(zone.name, lang);

        const card = document.createElement('div');
        card.className = 'zone-card';
        card.innerHTML = `
          <div class="zone-card-top">
            <div class="zone-name">${localizedName}</div>
            <div class="zone-badge ${isAlert ? 'badge-alert' : 'badge-nominal'}">
              <span class="status-dot ${isAlert ? 'dot-red' : 'dot-green'}"></span>
              ${isAlert ? (isHi ? 'अलर्ट (ALERT)' : 'ALERT') : (isHi ? 'सामान्य (NOMINAL)' : 'NOMINAL')}
            </div>
          </div>

          <div class="zone-stats-row">
            <div class="stat-col">
              <span class="stat-lbl">${isHi ? 'कुल गोवंश' : 'Total Cattle'}</span>
              <span class="stat-val">${zone.total}</span>
            </div>
            <div class="stat-col">
              <span class="stat-lbl">${isHi ? 'सक्रिय' : 'Active'}</span>
              <span class="stat-val text-emerald">${zone.active}</span>
            </div>
            <div class="stat-col">
              <span class="stat-lbl">${isHi ? 'विश्राम' : 'Resting'}</span>
              <span class="stat-val text-amber">${zone.resting}</span>
            </div>
          </div>

          <div class="ratio-progress-wrap">
            <div class="ratio-labels">
              <span>${isHi ? 'गतिविधि अनुपात' : 'Motion Ratio'}</span>
              <span>${activePercent}% ${isHi ? 'सक्रिय' : 'Active'} / ${restingPercent}% ${isHi ? 'विश्राम' : 'Rest'}</span>
            </div>
            <div class="ratio-bar">
              <div class="ratio-fill-active" style="width: ${activePercent}%;"></div>
              <div class="ratio-fill-resting" style="width: ${restingPercent}%;"></div>
            </div>
          </div>
        `;
        zonesContainer.appendChild(card);
      });
    }

    // 3. Telemetry Table
    const tableBody = document.getElementById('telemetry-table-body');
    if (tableBody && metrics.zones) {
      tableBody.innerHTML = '';
      metrics.zones.forEach(zone => {
        const isAlert = zone.health === 'Alert';
        const localizedName = this.getZoneName(zone.name, lang);
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${localizedName}</strong></td>
          <td><code class="code-badge">CAM-${(zone.camera_id || '01').toUpperCase()}</code></td>
          <td class="text-muted" style="font-size:0.75rem; font-family:var(--font-mono);">rtsp://stream/${zone.camera_id || 'main'}</td>
          <td><strong>${zone.total}</strong> ${isHi ? 'गोवंश' : 'Cattle'}</td>
          <td>${zone.feeder ?? 0} / 4 ${isHi ? 'क्षमता' : 'Bunks'}</td>
          <td>
            <span class="chip-status ${isAlert ? 'status-danger' : 'status-safe'}">
              ${isAlert ? (isHi ? '⚠ उल्लंघन' : '⚠ Breach Alert') : (isHi ? '✓ सुरक्षित' : '✓ Secure')}
            </span>
          </td>
          <td>
            <span class="chip-status ${isAlert ? 'status-danger' : 'status-safe'}">
              ${isAlert ? (isHi ? 'ध्यान दें' : 'Attention') : (isHi ? 'सामान्य' : 'Nominal')}
            </span>
          </td>
        `;
        tableBody.appendChild(tr);
      });
    }
  }
};
