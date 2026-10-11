const AlertsModule = {
  alerts: [],
  currentFilter: 'ALL',
  lightboxModal: null,

  init() {
    this.setupFilters();
    this.setupLightbox();
    this.setupClearAll();
  },

  setupFilters() {
    document.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        this.currentFilter = chip.dataset.severity;
        this.renderAlerts();
      });
    });
  },

  setupLightbox() {
    this.lightboxModal = document.getElementById('lightbox-modal');
    const closeBtn = document.getElementById('close-lightbox-btn');
    if (closeBtn && this.lightboxModal) {
      closeBtn.addEventListener('click', () => {
        this.lightboxModal.classList.remove('active');
      });
    }
  },

  setupClearAll() {
    const clearBtn = document.getElementById('clear-alerts-btn');
    if (clearBtn) {
      clearBtn.addEventListener('click', async () => {
        try {
          await apiRequest('/api/alerts/clear', { method: 'POST' });
          this.alerts = [];
          this.renderAlerts();
          showToast(AppState.lang === 'hi' ? 'अलर्ट लॉग साफ़ किया गया' : 'Alerts log cleared', 'info');
        } catch (err) {
          showToast(AppState.lang === 'hi' ? 'अलर्ट साफ़ करने में विफल' : 'Failed to clear alerts', 'critical');
        }
      });
    }
  },

  async loadAlerts() {
    try {
      this.alerts = await apiRequest('/api/alerts?limit=100');
      this.renderAlerts();
    } catch (err) {
      console.debug('Failed to load alerts:', err);
    }
  },

  prependAlert(alert) {
    if (!this.alerts.some(a => a.id === alert.id)) {
      this.alerts.unshift(alert);
      this.renderAlerts();
    }
  },

  renderAlerts() {
    const container = document.getElementById('alerts-list-container');
    if (!container) return;

    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    let filtered = this.alerts;
    if (this.currentFilter !== 'ALL') {
      filtered = filtered.filter(a => a.severity === this.currentFilter);
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          <h3>${isHi ? 'सभी गौशाला परिसर सामान्य स्थिति में' : 'All Gaushala Enclosures Nominal'}</h3>
          <p>${isHi ? 'वर्तमान फ़िल्टर के तहत कोई सक्रिय असामान्यता या संकट दर्ज नहीं हुआ।' : 'No active distress triggers or anomalies detected.'}</p>
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    filtered.forEach(alert => {
      const card = document.createElement('div');
      const sevLower = alert.severity.toLowerCase();
      card.className = `alert-card ${sevLower} ${alert.resolved ? 'resolved' : ''}`;
      card.id = `alert-card-${alert.id}`;

      let formattedTime = alert.timestamp;
      try {
        const d = new Date(alert.timestamp);
        formattedTime = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      } catch (e) {}

      const thumbnailHtml = alert.snapshot_url
        ? `<div class="alert-snapshot-wrapper" onclick="AlertsModule.openLightbox('${alert.snapshot_url}', '${alert.alert_type}', '${alert.message.replace(/'/g, "\\'")}')">
             <img src="${alert.snapshot_url}" loading="lazy" alt="Detection Evidence" />
             <span class="snapshot-zoom-hint">${isHi ? 'निरीक्षण' : 'Inspect'}</span>
           </div>`
        : `<div class="alert-snapshot-wrapper placeholder-snapshot">
             <span>${isHi ? 'साक्ष्य उपलब्ध नहीं' : 'No Frame'}</span>
           </div>`;

      // Store alert object in dataset or lookup
      const alertJsonStr = JSON.stringify(alert).replace(/"/g, '&quot;');

      card.innerHTML = `
        ${thumbnailHtml}
        <div class="alert-content">
          <div class="alert-top-row">
            <div class="alert-meta">
              <span class="severity-badge badge-${sevLower}">${alert.severity}</span>
              <span class="alert-zone-tag">${alert.zone_name} (${alert.camera_id})</span>
            </div>
            <span class="alert-time">${formattedTime}</span>
          </div>

          <div>
            <div class="alert-headline">${this.getFriendlyTitle(alert.alert_type, lang)}</div>
            <div class="alert-desc">${alert.message}</div>
          </div>

          <div class="alert-actions">
            ${!alert.resolved 
              ? `<button class="btn-ack" onclick="AlertsModule.resolveAlert('${alert.id}')">
                   ${isHi ? '✓ समाधान चिह्नित करें' : '✓ Resolve'}
                 </button>
                 <button class="btn-groq-mini" onclick='AlertsModule.triggerDiagnosis(${alertJsonStr})'>
                   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                   <span>${isHi ? 'ग्रोक ए.आई. नैदानिक परामर्श' : 'Groq AI Diagnosis'}</span>
                 </button>`
              : `<span class="badge-success-subtle">
                   ${isHi ? '✓ निस्तारित' : '✓ Resolved'}
                 </span>
                 <button class="btn-groq-mini" onclick='AlertsModule.triggerDiagnosis(${alertJsonStr})'>
                   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                   <span>${isHi ? 'ग्रोक विश्लेषण देखें' : 'View Groq Analysis'}</span>
                 </button>`}
          </div>
        </div>
      `;
      container.appendChild(card);
    });
  },

  triggerDiagnosis(alert) {
    if (window.AiModule) {
      AiModule.openDiagnosisForAlert(alert);
    }
  },

  getFriendlyTitle(type, lang = 'en') {
    const isHi = (lang === 'hi');
    switch (type) {
      case 'GEOFENCE_BREACH': 
        return isHi ? 'गोवंश परिधि उल्लंघन / बाड़ा पलायन' : 'Geofence Perimeter Breach';
      case 'PROSTRATION_DISTRESS': 
        return isHi ? 'असामान्य दीर्घकालिक निष्क्रियता / संकट चेतावनी' : 'Prolonged Recumbency Distress';
      case 'FEEDER_OVERCROWDING': 
        return isHi ? 'चारागाह अत्यधिक भीड़ व आक्रामकता चेतावनी' : 'Feed Trough Overcrowding & Crush';
      case 'CAMERA_OFFLINE': 
        return isHi ? 'सीसीटीवी नोड विच्छेद चेतावनी' : 'Camera Stream Offline';
      default: 
        return type.replace(/_/g, ' ');
    }
  },

  async resolveAlert(alertId) {
    try {
      await apiRequest(`/api/alerts/${alertId}/resolve`, { method: 'POST' });
      const target = this.alerts.find(a => a.id === alertId);
      if (target) target.resolved = true;
      this.renderAlerts();
      showToast(AppState.lang === 'hi' ? 'अलर्ट समाधान दर्ज हुआ' : 'Alert marked as resolved', 'info');
    } catch (err) {
      showToast(AppState.lang === 'hi' ? 'अलर्ट निस्तारण में त्रुटि' : 'Failed to resolve alert', 'critical');
    }
  },

  openLightbox(imgUrl, title, description) {
    if (!this.lightboxModal) return;
    const img = document.getElementById('lightbox-img');
    const titleElem = document.getElementById('lightbox-title');
    const descElem = document.getElementById('lightbox-desc');

    if (img) img.src = imgUrl;
    if (titleElem) titleElem.textContent = this.getFriendlyTitle(title, AppState.lang);
    if (descElem) descElem.textContent = description;

    this.lightboxModal.classList.add('active');
  }
};
