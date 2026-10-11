const AiModule = {
  initialized: false,
  cachedAlerts: [],

  init() {
    if (this.initialized) return;
    this.initialized = true;
    this.bindEvents();
    this.checkStatus();
    this.refreshAlertSelect();
  },

  async refreshAlertSelect() {
    const select = document.getElementById('ai-diag-select');
    if (!select) return;

    try {
      const res = await apiRequest('/api/alerts');
      this.cachedAlerts = Array.isArray(res) ? res : (res.alerts || []);
      const lang = AppState.lang || 'en';

      if (this.cachedAlerts.length === 0) {
        select.innerHTML = `
          <option value="" disabled selected>
            ${lang === 'hi' ? '-- कोई सक्रिय असामान्य अलर्ट नहीं है --' : '-- No Active Distress Alerts Detected --'}
          </option>
        `;
        return;
      }

      select.innerHTML = `
        <option value="" disabled selected>
          ${lang === 'hi' ? '-- लाइव असामान्य अलर्ट चुनें --' : '-- Select Live Distress Alert Event --'}
        </option>
      ` + this.cachedAlerts.map(a => `
        <option value="${a.id}">
          [${a.alert_type}] #${a.entity_id || 'Cattle'} - ${a.message} (${a.zone_name || 'Pen'})
        </option>
      `).join('');
    } catch (e) {
      console.debug('Failed to fetch alerts for AI select:', e);
    }
  },

  async checkStatus() {
    try {
      const res = await apiRequest('/api/ai/status');
      const badgeText = document.getElementById('groq-model-status-text');
      const summaryText = document.getElementById('ai-status-summary');
      if (res.groq_active) {
        if (badgeText) badgeText.textContent = `⚡ Groq Cloud Active (${res.model})`;
        if (summaryText) summaryText.innerHTML = `<code>${res.model}</code> via Groq API Key`;
      } else {
        if (badgeText) badgeText.textContent = `⚡ Groq Intelligence Engine (.env Ready)`;
        if (summaryText) summaryText.innerHTML = `<code>${res.model}</code> (Clinical Hybrid)`;
      }
    } catch (e) {
      console.debug('AI Status check failed:', e);
    }
  },

  bindEvents() {
    // 1. Run Diagnosis button in AI tab
    const diagBtn = document.getElementById('run-groq-diag-btn');
    if (diagBtn) {
      diagBtn.addEventListener('click', () => this.handleRunDiagnosis());
    }

    // 2. Generate Shift Audit Report
    const reportBtn = document.getElementById('generate-shift-report-btn');
    if (reportBtn) {
      reportBtn.addEventListener('click', () => this.handleGenerateShiftReport());
    }

    // 3. Interactive Chat Form
    const chatForm = document.getElementById('ai-chat-form');
    if (chatForm) {
      chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleSendChatMessage();
      });
    }

    // 4. Modal Close
    const closeDiagBtn = document.getElementById('close-diag-modal-btn');
    const diagModal = document.getElementById('diagnosis-modal');
    if (closeDiagBtn && diagModal) {
      closeDiagBtn.addEventListener('click', () => {
        diagModal.classList.remove('active');
      });
    }
  },

  async handleRunDiagnosis() {
    const select = document.getElementById('ai-diag-select');
    const alertId = select ? select.value : '';
    const outputBox = document.getElementById('ai-diag-output');
    const lang = AppState.lang || 'en';

    if (!alertId) {
      showToast(lang === 'hi' 
        ? 'कृपया पहले सूची से कोई सक्रिय लाइव अलर्ट चुनें।' 
        : 'Please select an active live alert from the list first.', 'warning');
      return;
    }

    const alert = this.cachedAlerts.find(a => String(a.id) === String(alertId));
    if (!alert) {
      showToast(lang === 'hi' ? 'चुना गया अलर्ट उपलब्ध नहीं है।' : 'Selected alert not found.', 'warning');
      return;
    }

    if (outputBox) {
      outputBox.style.display = 'block';
      outputBox.innerHTML = `
        <div class="ai-loading-spinner">
          <div class="spinner"></div>
          <span>${lang === 'hi' ? 'ग्रोक ए.आई. नैदानिक विश्लेषण लोड हो रहा है...' : 'Running Groq Veterinary AI inference on live alert...'}</span>
        </div>
      `;
    }

    try {
      const res = await apiRequest('/api/ai/diagnose', {
        method: 'POST',
        body: JSON.stringify({
          alert_type: alert.alert_type,
          message: alert.message,
          entity_id: String(alert.entity_id || 'Livestock'),
          duration: alert.duration_seconds || 60,
          zone_name: alert.zone_name,
          lang
        })
      });

      if (outputBox && res.success) {
        outputBox.innerHTML = this.renderDiagnosisCard(res.diagnosis, lang);
      }
    } catch (err) {
      if (outputBox) {
        outputBox.innerHTML = `<div class="ai-error-box">${err.message}</div>`;
      }
    }
  },

  async openDiagnosisForAlert(alert) {
    const diagModal = document.getElementById('diagnosis-modal');
    const modalBody = document.getElementById('diag-modal-body');
    const modalTitle = document.getElementById('diag-modal-title');
    const lang = AppState.lang || 'en';

    if (!diagModal || !modalBody) return;
    diagModal.classList.add('active');

    if (modalTitle) {
      modalTitle.textContent = lang === 'hi' 
        ? `ग्रोक ए.आई. नैदानिक परामर्श: गोवंश #${alert.entity_id || 'Livestock'}` 
        : `Groq AI Clinical Diagnosis: Cattle #${alert.entity_id || 'Livestock'}`;
    }

    modalBody.innerHTML = `
      <div class="ai-loading-spinner">
        <div class="spinner"></div>
        <span>${lang === 'hi' ? 'ग्रोक ए.आई. नैदानिक परामर्श तैयार कर रहा है...' : 'Groq LLaMA-3.3 evaluating alert clinical telemetry...'}</span>
      </div>
    `;

    try {
      const res = await apiRequest('/api/ai/diagnose', {
        method: 'POST',
        body: JSON.stringify({
          alert_type: alert.alert_type,
          message: alert.message,
          entity_id: String(alert.entity_id || 'Livestock'),
          duration: alert.duration_seconds || 60,
          zone_name: alert.zone_name,
          lang
        })
      });

      if (res.success) {
        modalBody.innerHTML = this.renderDiagnosisCard(res.diagnosis, lang);
      }
    } catch (err) {
      modalBody.innerHTML = `<div class="ai-error-box">${err.message}</div>`;
    }
  },

  renderDiagnosisCard(d, lang) {
    const isHi = (lang === 'hi');
    const riskScore = d.risk_score || 7.5;
    const riskColor = riskScore >= 7.5 ? '#e11d48' : (riskScore >= 5 ? '#f59e0b' : '#10b981');
    const riskLabel = riskScore >= 7.5 ? (isHi ? 'उच्च जोखिम (HIGH RISK)' : 'HIGH RISK') : (riskScore >= 5 ? (isHi ? 'मध्यम जोखिम (MODERATE)' : 'MODERATE') : (isHi ? 'न्यूनतम (LOW)' : 'LOW'));

    const actionsHtml = (d.immediate_actions || []).map((act, i) => `
      <li class="action-item">
        <span class="action-num">${i + 1}</span>
        <span class="action-text">${act}</span>
      </li>
    `).join('');

    return `
      <div class="diag-result-card">
        <div class="diag-top-banner">
          <div class="diag-score-wrap">
            <div class="diag-score-circle" style="border-color:${riskColor}; color:${riskColor};">
              <span class="score-val">${riskScore}</span>
              <span class="score-max">/10</span>
            </div>
            <div>
              <div class="score-badge" style="background:${riskColor}15; color:${riskColor};">${riskLabel}</div>
              <div class="score-sub">${isHi ? 'पशु चिकित्सा आपातकाल स्कोर' : 'Clinical Severity Rating'}</div>
            </div>
          </div>
          <div class="diag-powered-by">
            <span>⚡ ${d.powered_by || 'Groq LLaMA-3.3 (via .env)'}</span>
          </div>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">${isHi ? '📋 नैदानिक मूल्यांकन (Clinical Assessment)' : '📋 Clinical Assessment'}</h4>
          <p class="diag-sec-content">${d.assessment || ''}</p>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">${isHi ? '⚡ शेड परिचारक तत्काल कार्रवाई (Immediate Actions)' : '⚡ Immediate Caretaker Protocol'}</h4>
          <ul class="diag-action-list">
            ${actionsHtml}
          </ul>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">${isHi ? '💉 पशु चिकित्सा उपचार प्रोटोकॉल (Medical Protocol)' : '💉 Veterinary Medical Protocol'}</h4>
          <div class="diag-protocol-box">${d.medical_protocol || ''}</div>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">${isHi ? '📌 पर्यवेक्षक निर्देश (Shift Recommendation)' : '📌 Supervisor Shift Directive'}</h4>
          <p class="diag-sec-content">${d.shift_recommendation || ''}</p>
        </div>
      </div>
    `;
  },

  async handleGenerateShiftReport() {
    const outputBox = document.getElementById('ai-audit-output');
    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    if (outputBox) {
      outputBox.style.display = 'block';
      outputBox.innerHTML = `
        <div class="ai-loading-spinner">
          <div class="spinner"></div>
          <span>${isHi ? 'ग्रोक ए.आई. समग्र शिफ्ट ऑडिट रिपोर्ट तैयार कर रहा है...' : 'Generating Groq Shift Handover Audit Report...'}</span>
        </div>
      `;
    }

    try {
      const res = await apiRequest(`/api/ai/shift-report?lang=${lang}`);
      if (res.success && outputBox) {
        const r = res.report;
        const findingsHtml = (r.key_clinical_findings || []).map(f => `<li>${f}</li>`).join('');
        const tasksHtml = (r.supervisor_tasks || []).map(t => `<li>✓ ${t}</li>`).join('');

        outputBox.innerHTML = `
          <div class="report-result-card">
            <div class="report-header">
              <div>
                <h3 class="report-title">${r.title || 'Gaushala Shift Audit Report'}</h3>
                <span class="report-meta">${r.generated_at} | Shift: ${r.shift}</span>
              </div>
              <span class="report-powered">⚡ ${r.powered_by}</span>
            </div>

            <div class="report-stat-bar">
              <div class="rep-stat"><strong>${r.herd_census?.total_headcount || 48}</strong> ${isHi ? 'कुल गोवंश' : 'Total Cattle'}</div>
              <div class="rep-stat"><strong>${r.herd_census?.motion_nominal_percent || '85%'}</strong> ${isHi ? 'सक्रिय अनुपात' : 'Active Motion'}</div>
              <div class="rep-stat"><strong>${r.herd_census?.alerts_logged || 3}</strong> ${isHi ? 'सक्रिय अलर्ट' : 'Logged Alerts'}</div>
            </div>

            <div class="report-section">
              <h4>${isHi ? 'प्रमुख नैदानिक निष्कर्ष (Key Clinical Findings)' : 'Key Clinical Findings'}</h4>
              <ul class="report-list">${findingsHtml}</ul>
            </div>

            <div class="report-section">
              <h4>${isHi ? 'पर्यवेक्षक कार्य सूची (Supervisor Handover Checklist)' : 'Supervisor Handover Tasks'}</h4>
              <ul class="report-tasks">${tasksHtml}</ul>
            </div>
          </div>
        `;
      }
    } catch (err) {
      if (outputBox) outputBox.innerHTML = `<div class="ai-error-box">${err.message}</div>`;
    }
  },

  async handleSendChatMessage() {
    const input = document.getElementById('ai-chat-input');
    const history = document.getElementById('ai-chat-history');
    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    if (!input || !input.value.trim() || !history) return;
    const question = input.value.trim();
    input.value = '';

    // Append User Message
    const userMsg = document.createElement('div');
    userMsg.className = 'chat-bubble chat-bubble-user';
    userMsg.innerHTML = `
      <div class="chat-sender">${isHi ? 'आप (पर्यवेक्षक)' : 'You (Supervisor)'}</div>
      <div class="chat-text">${question}</div>
    `;
    history.appendChild(userMsg);
    history.scrollTop = history.scrollHeight;

    // Append AI Loading
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'chat-bubble chat-bubble-ai';
    loadingMsg.innerHTML = `
      <div class="chat-sender">Groq LLaMA-3.3</div>
      <div class="chat-text chat-loading">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>
    `;
    history.appendChild(loadingMsg);
    history.scrollTop = history.scrollHeight;

    try {
      const res = await apiRequest('/api/ai/chat', {
        method: 'POST',
        body: JSON.stringify({ question, lang })
      });

      if (res.success) {
        const textElem = loadingMsg.querySelector('.chat-text');
        if (textElem) {
          textElem.className = 'chat-text';
          textElem.textContent = res.response.answer;
        }
        const senderElem = loadingMsg.querySelector('.chat-sender');
        if (senderElem) {
          senderElem.textContent = `⚡ ${res.response.model || 'Groq Cloud AI'}`;
        }
      }
    } catch (err) {
      const textElem = loadingMsg.querySelector('.chat-text');
      if (textElem) {
        textElem.className = 'chat-text text-error';
        textElem.textContent = err.message;
      }
    }
    history.scrollTop = history.scrollHeight;
  }
};
