const AiModule = {
  initialized: false,
  cachedAlerts: [],
  currentDiagnosis: null,
  isSpeaking: false,
  speechSynth: window.speechSynthesis || null,
  currentUtterance: null,
  recognition: null,
  isListening: false,
  triageMode: 'cctv', // 'cctv' or 'matrix'

  init() {
    if (this.initialized) return;
    this.initialized = true;
    this.bindEvents();
    this.initSpeechRecognition();
    this.checkStatus();
    this.refreshAlertSelect();
    this.updateTelemetrySnapshot();
  },

  /* --------------------------------------------------------------------------
     1. Event Listeners & Binding
     -------------------------------------------------------------------------- */
  bindEvents() {
    // A. Sub-Navigation Tabs
    const subtabs = document.querySelectorAll('.ai-subtab-btn');
    subtabs.forEach(btn => {
      btn.addEventListener('click', () => {
        const panelId = btn.getAttribute('data-subpanel');
        this.switchSubpanel(panelId);
      });
    });

    // B. Triage Mode Switcher (CCTV Live vs Symptom Matrix)
    const modeCctvBtn = document.getElementById('mode-cctv-trigger');
    const modeMatrixBtn = document.getElementById('mode-symptom-matrix');
    if (modeCctvBtn) modeCctvBtn.addEventListener('click', () => this.setTriageMode('cctv'));
    if (modeMatrixBtn) modeMatrixBtn.addEventListener('click', () => this.setTriageMode('matrix'));

    // C. Clickable Symptom Tag Multi-Select
    const symContainer = document.getElementById('symptom-tag-container');
    if (symContainer) {
      symContainer.addEventListener('click', (e) => {
        const tag = e.target.closest('.sym-tag');
        if (tag) {
          tag.classList.toggle('active');
        }
      });
    }

    // D. Vitals Sliders Interactive Display
    const tempSlider = document.getElementById('input-vital-temp');
    const dispTemp = document.getElementById('disp-temp-val');
    if (tempSlider && dispTemp) {
      tempSlider.addEventListener('input', () => {
        dispTemp.textContent = `${parseFloat(tempSlider.value).toFixed(1)}°F`;
        if (parseFloat(tempSlider.value) >= 103.5) {
          dispTemp.style.color = '#e11d48';
        } else {
          dispTemp.style.color = '#7c3aed';
        }
      });
    }

    const respSlider = document.getElementById('input-vital-resp');
    const dispResp = document.getElementById('disp-resp-val');
    if (respSlider && dispResp) {
      respSlider.addEventListener('input', () => {
        dispResp.textContent = `${respSlider.value}/min`;
        if (parseInt(respSlider.value, 10) >= 50) {
          dispResp.style.color = '#e11d48';
        } else {
          dispResp.style.color = '#7c3aed';
        }
      });
    }

    // E. Alert Select Change preview
    const alertSelect = document.getElementById('ai-diag-select');
    if (alertSelect) {
      alertSelect.addEventListener('change', () => this.updateAlertPreview());
    }

    // F. Refresh Alert Select
    const refAlertBtn = document.getElementById('refresh-alert-select-btn');
    if (refAlertBtn) {
      refAlertBtn.addEventListener('click', () => {
        this.refreshAlertSelect();
        showToast(AppState.lang === 'hi' ? 'अलर्ट सूची अद्यतन की गई।' : 'Distress alerts refreshed.', 'info');
      });
    }

    // G. Refresh Status Button
    const refStatusBtn = document.getElementById('refresh-ai-status-btn');
    if (refStatusBtn) {
      refStatusBtn.addEventListener('click', () => {
        this.checkStatus(true);
      });
    }

    // H. Run Diagnosis Button
    const diagBtn = document.getElementById('run-groq-diag-btn');
    if (diagBtn) {
      diagBtn.addEventListener('click', () => this.handleRunDiagnosis());
    }

    // I. Diagnosis Action Buttons (Speak, Copy, Print)
    const speakBtn = document.getElementById('btn-speak-diag');
    if (speakBtn) speakBtn.addEventListener('click', () => this.toggleSpeakDiagnosis());

    const copyBtn = document.getElementById('btn-copy-diag');
    if (copyBtn) copyBtn.addEventListener('click', () => this.copyDiagnosisContent());

    const printBtn = document.getElementById('btn-print-diag');
    if (printBtn) printBtn.addEventListener('click', () => this.printDiagnosisContent());

    // J. Interactive Chat Form
    const chatForm = document.getElementById('ai-chat-form');
    if (chatForm) {
      chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleSendChatMessage();
      });
    }

    // K. Clear Chat History
    const clearChatBtn = document.getElementById('btn-clear-chat-history');
    if (clearChatBtn) {
      clearChatBtn.addEventListener('click', () => {
        const history = document.getElementById('ai-chat-history');
        if (history) {
          const isHi = (AppState.lang === 'hi');
          history.innerHTML = `
            <div class="chat-bubble chat-bubble-ai">
              <div class="chat-bubble-header">
                <span class="chat-sender">⚡ Groq LLaMA-3.3-70B • Veterinary Copilot</span>
                <span class="chat-time">Just now</span>
              </div>
              <div class="chat-text">
                ${isHi ? 'चैट इतिहास साफ़ किया गया। आप नया पशु चिकित्सा अथवा बाड़ा टेलीमेट्री प्रश्न पूछ सकते हैं।' : 'Chat transcript cleared. Ask any clinical, feed, or shed telemetry inquiry.'}
              </div>
            </div>
          `;
          showToast(isHi ? 'चैट इतिहास साफ़ किया गया।' : 'Chat history cleared.', 'info');
        }
      });
    }

    // L. Quick Prompt Chips
    document.querySelectorAll('.prompt-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const prompt = chip.getAttribute('data-prompt');
        if (prompt) {
          const input = document.getElementById('ai-chat-input');
          if (input) input.value = prompt;
          this.handleSendChatMessage(prompt);
        }
      });
    });

    // M. Voice Mic Button
    const micBtn = document.getElementById('ai-chat-mic-btn');
    if (micBtn) {
      micBtn.addEventListener('click', () => this.toggleVoiceDictation());
    }

    // N. Generate Shift Report
    const reportBtn = document.getElementById('generate-shift-report-btn');
    if (reportBtn) {
      reportBtn.addEventListener('click', () => this.handleGenerateShiftReport());
    }

    // O. Formulary Search Filter
    const formSearch = document.getElementById('formulary-search-input');
    if (formSearch) {
      formSearch.addEventListener('input', () => this.filterFormularyCards(formSearch.value));
    }

    // P. Modal Close for Diagnosis
    const closeDiagBtn = document.getElementById('close-diag-modal-btn');
    const diagModal = document.getElementById('diagnosis-modal');
    if (closeDiagBtn && diagModal) {
      closeDiagBtn.addEventListener('click', () => {
        diagModal.classList.remove('active');
        if (this.isSpeaking) this.stopSpeaking();
      });
    }
  },

  /* --------------------------------------------------------------------------
     2. Subpanel & Mode Navigation
     -------------------------------------------------------------------------- */
  switchSubpanel(panelId) {
    // Update nav buttons
    document.querySelectorAll('.ai-subtab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-subpanel') === panelId);
    });

    // Update panels
    const panels = {
      triage: document.getElementById('ai-panel-triage'),
      chat: document.getElementById('ai-panel-chat'),
      report: document.getElementById('ai-panel-report'),
      formulary: document.getElementById('ai-panel-formulary')
    };

    Object.keys(panels).forEach(key => {
      if (panels[key]) {
        panels[key].classList.toggle('active', key === panelId);
      }
    });

    if (panelId === 'report') {
      this.updateTelemetrySnapshot();
    }
  },

  setTriageMode(mode) {
    this.triageMode = mode;
    const modeCctvBtn = document.getElementById('mode-cctv-trigger');
    const modeMatrixBtn = document.getElementById('mode-symptom-matrix');
    const sectionCctv = document.getElementById('section-cctv-mode');
    const sectionMatrix = document.getElementById('section-symptom-mode');

    if (mode === 'cctv') {
      if (modeCctvBtn) modeCctvBtn.classList.add('active');
      if (modeMatrixBtn) modeMatrixBtn.classList.remove('active');
      if (sectionCctv) sectionCctv.style.display = 'block';
      if (sectionMatrix) sectionMatrix.style.display = 'none';
    } else {
      if (modeCctvBtn) modeCctvBtn.classList.remove('active');
      if (modeMatrixBtn) modeMatrixBtn.classList.add('active');
      if (sectionCctv) sectionCctv.style.display = 'none';
      if (sectionMatrix) sectionMatrix.style.display = 'block';
    }
  },

  /* --------------------------------------------------------------------------
     3. Engine Health & Status
     -------------------------------------------------------------------------- */
  async checkStatus(showToastMsg = false) {
    try {
      const res = await apiRequest('/api/ai/status');
      const badgeText = document.getElementById('groq-model-status-text');
      const summaryText = document.getElementById('ai-status-summary');
      const latencyPill = document.getElementById('ai-latency-pill');

      if (res.groq_active) {
        if (badgeText) badgeText.textContent = `⚡ Groq Cloud LPU™ Active (${res.model})`;
        if (summaryText) summaryText.innerHTML = `<code>${res.model}</code> via Groq API Key`;
      } else {
        if (badgeText) badgeText.textContent = `⚡ Groq Intelligence Engine (.env Ready)`;
        if (summaryText) summaryText.innerHTML = `<code>${res.model}</code> (Clinical Hybrid)`;
      }

      if (latencyPill && res.inference_latency_ms) {
        latencyPill.innerHTML = `<span class="pulse-dot-green"></span><span>${res.inference_latency_ms}ms Latency</span>`;
      }

      if (showToastMsg) {
        showToast(AppState.lang === 'hi' 
          ? `ग्रोक इंजन तैयार: ${res.model}` 
          : `Groq LPU Engine Active: ${res.model}`, 'success');
      }
    } catch (e) {
      console.debug('AI Status check failed:', e);
    }
  },

  async updateTelemetrySnapshot() {
    try {
      const metrics = await apiRequest('/api/metrics/summary');
      const totalElem = document.getElementById('rep-preview-total');
      const activeElem = document.getElementById('rep-preview-active');
      const restElem = document.getElementById('rep-preview-resting');
      const alertElem = document.getElementById('rep-preview-alerts');

      if (totalElem) totalElem.textContent = metrics.total_cattle ?? 0;
      if (activeElem) activeElem.textContent = metrics.active_cattle ?? 0;
      if (restElem) restElem.textContent = metrics.resting_cattle ?? 0;
      if (alertElem) alertElem.textContent = metrics.logged_alerts ?? 0;
    } catch (e) {
      console.debug('Telemetry snapshot fetch error:', e);
    }
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
        const preview = document.getElementById('selected-alert-preview');
        if (preview) preview.style.display = 'none';
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

      // Auto-select first if available
      if (this.cachedAlerts.length > 0) {
        select.selectedIndex = 1;
        this.updateAlertPreview();
      }
    } catch (e) {
      console.debug('Failed to fetch alerts for AI select:', e);
    }
  },

  updateAlertPreview() {
    const select = document.getElementById('ai-diag-select');
    const preview = document.getElementById('selected-alert-preview');
    if (!select || !preview) return;

    const alertId = select.value;
    const alert = this.cachedAlerts.find(a => String(a.id) === String(alertId));
    if (!alert) {
      preview.style.display = 'none';
      return;
    }

    preview.style.display = 'flex';
    const tagElem = document.getElementById('preview-alert-type');
    const cowElem = document.getElementById('preview-alert-cow');
    const zoneElem = document.getElementById('preview-alert-zone');
    const timeElem = document.getElementById('preview-alert-time');

    if (tagElem) tagElem.textContent = alert.alert_type;
    if (cowElem) cowElem.textContent = `#${alert.entity_id || 'Livestock'}`;
    if (zoneElem) zoneElem.textContent = alert.zone_name || 'Enclosure';
    if (timeElem) timeElem.textContent = `Duration: ${Math.round(alert.duration_seconds || 60)}s`;
  },

  /* --------------------------------------------------------------------------
     4. Diagnosis Engine & Evaluation
     -------------------------------------------------------------------------- */
  async handleRunDiagnosis() {
    const outputBox = document.getElementById('ai-diag-output');
    const emptyBox = document.getElementById('triage-empty-box');
    const actionTools = document.getElementById('diag-card-actions');
    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    let payload = {};

    if (this.triageMode === 'cctv') {
      const select = document.getElementById('ai-diag-select');
      const alertId = select ? select.value : '';

      if (!alertId) {
        showToast(isHi 
          ? 'कृपया पहले सूची से कोई सक्रिय लाइव अलर्ट चुनें या लक्षण मैट्रिक्स मोड पर जाएं।' 
          : 'Please select an active live alert from the list first or switch to Symptom Matrix.', 'warning');
        return;
      }

      const alert = this.cachedAlerts.find(a => String(a.id) === String(alertId));
      if (!alert) {
        showToast(isHi ? 'चुना गया अलर्ट उपलब्ध नहीं है।' : 'Selected alert not found.', 'warning');
        return;
      }

      payload = {
        alert_type: alert.alert_type,
        message: alert.message,
        entity_id: String(alert.entity_id || 'Livestock'),
        duration: alert.duration_seconds || 60,
        zone_name: alert.zone_name,
        lang
      };
    } else {
      // Symptom Matrix Mode
      const cowIdInput = document.getElementById('triage-cow-id');
      const penSelect = document.getElementById('triage-pen-select');
      const activeTags = Array.from(document.querySelectorAll('#symptom-tag-container .sym-tag.active'))
        .map(el => el.getAttribute('data-symptom'));

      const tempVal = parseFloat(document.getElementById('input-vital-temp')?.value || 102.5);
      const respVal = parseInt(document.getElementById('input-vital-resp')?.value || 28, 10);

      if (activeTags.length === 0) {
        showToast(isHi 
          ? 'कृपया कम से कम एक नैदानिक लक्षण (Symptom Tag) चुनें।' 
          : 'Please select at least one clinical symptom tag.', 'warning');
        return;
      }

      payload = {
        alert_type: 'CLINICAL_SYMPTOM_EVAL',
        message: `Evaluation of ${activeTags.length} observed physical symptoms`,
        entity_id: cowIdInput ? cowIdInput.value.trim() : 'COW-104',
        duration: 0,
        zone_name: penSelect ? penSelect.value : 'Zone A - North Shed',
        symptoms: activeTags,
        vitals: {
          rectal_temperature_f: tempVal,
          respiration_rate_per_min: respVal
        },
        lang
      };
    }

    if (emptyBox) emptyBox.style.display = 'none';
    if (actionTools) actionTools.style.display = 'none';

    if (outputBox) {
      outputBox.style.display = 'block';
      outputBox.innerHTML = `
        <div class="ai-loading-spinner">
          <div class="spinner"></div>
          <span>${isHi ? '⚡ ग्रोक ए.आई. अल्ट्रा-फास्ट नैदानिक विश्लेषण लोड कर रहा है (<150ms)...' : '⚡ Running Groq Ultra-Fast LPU™ Clinical Inference (<150ms)...'}</span>
        </div>
      `;
    }

    try {
      const res = await apiRequest('/api/ai/diagnose', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (outputBox && res.success) {
        this.currentDiagnosis = res.diagnosis;
        outputBox.innerHTML = this.renderDiagnosisCard(res.diagnosis, lang);
        if (actionTools) actionTools.style.display = 'flex';
        showToast(isHi ? 'नैदानिक विश्लेषण पूर्ण।' : 'Clinical inference completed.', 'success');
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
    const isHi = (lang === 'hi');

    if (!diagModal || !modalBody) return;
    diagModal.classList.add('active');

    if (modalTitle) {
      modalTitle.textContent = isHi 
        ? `ग्रोक ए.आई. नैदानिक परामर्श: गोवंश #${alert.entity_id || 'Livestock'}` 
        : `Groq AI Clinical Diagnosis: Cattle #${alert.entity_id || 'Livestock'}`;
    }

    modalBody.innerHTML = `
      <div class="ai-loading-spinner">
        <div class="spinner"></div>
        <span>${isHi ? 'ग्रोक ए.आई. नैदानिक परामर्श तैयार कर रहा है...' : 'Groq LPU LLaMA-3.3 evaluating alert telemetry...'}</span>
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
        this.currentDiagnosis = res.diagnosis;
        modalBody.innerHTML = `
          <div style="display:flex; justify-content:flex-end; gap:0.5rem; margin-bottom:1rem;">
            <button class="btn-subtle-tool" onclick="AiModule.toggleSpeakDiagnosis()">
              <span>🔊 Listen</span>
            </button>
            <button class="btn-subtle-tool" onclick="AiModule.copyDiagnosisContent()">
              <span>📋 Copy</span>
            </button>
          </div>
          ${this.renderDiagnosisCard(res.diagnosis, lang)}
        `;
      }
    } catch (err) {
      modalBody.innerHTML = `<div class="ai-error-box">${err.message}</div>`;
    }
  },

  renderDiagnosisCard(d, lang) {
    const isHi = (lang === 'hi');
    const riskScore = d.risk_score || 7.5;
    const riskColor = riskScore >= 7.5 ? '#e11d48' : (riskScore >= 5 ? '#f59e0b' : '#10b981');
    const riskLabel = riskScore >= 7.5 
      ? (isHi ? 'उच्च जोखिम (HIGH RISK)' : 'HIGH RISK') 
      : (riskScore >= 5 ? (isHi ? 'मध्यम जोखिम (MODERATE)' : 'MODERATE') : (isHi ? 'न्यूनतम (LOW RISK)' : 'LOW RISK'));

    const actionsHtml = (d.immediate_actions || []).map((act, i) => `
      <li class="action-item">
        <input type="checkbox" class="action-checkbox" id="act-chk-${i}" onchange="this.parentElement.style.opacity = this.checked ? '0.6' : '1';" />
        <span class="action-num">${i + 1}</span>
        <label for="act-chk-${i}" class="action-text" style="cursor:pointer; flex:1;">${act}</label>
      </li>
    `).join('');

    return `
      <div class="diag-result-card" id="printable-diag-card">
        <div class="diag-top-banner">
          <div class="diag-score-wrap">
            <div class="diag-score-circle" style="border-color:${riskColor}; color:${riskColor};">
              <span class="score-val">${riskScore}</span>
              <span class="score-max">/10</span>
            </div>
            <div>
              <div class="score-badge" style="background:${riskColor}18; color:${riskColor};">${riskLabel}</div>
              <div class="score-sub">${isHi ? 'पशु चिकित्सा आपातकाल स्कोर' : 'Clinical Severity Rating'}</div>
            </div>
          </div>
          <div class="diag-powered-by">
            <span>⚡ ${d.powered_by || 'Groq Cloud LPU™ (LLaMA-3.3-70B)'}</span>
          </div>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">
            <span>📋</span>
            <span>${isHi ? 'नैदानिक मूल्यांकन एवं संभावित विकृति' : 'Primary Pathological Assessment'}</span>
          </h4>
          <p class="diag-sec-content">${d.assessment || ''}</p>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">
            <span>⚡</span>
            <span>${isHi ? 'शेड परिचारक तत्काल प्राथमिक उपचार चेकलिस्ट' : 'Immediate Caretaker Action Protocol'}</span>
          </h4>
          <ul class="diag-action-list">
            ${actionsHtml}
          </ul>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">
            <span>💉</span>
            <span>${isHi ? 'पशु चिकित्सा औषध एवं इंजेक्शन प्रोटोकॉल' : 'Veterinary Medical Formulation & Rx'}</span>
          </h4>
          <div class="diag-protocol-box">${d.medical_protocol || ''}</div>
        </div>

        <div class="diag-section">
          <h4 class="diag-sec-title">
            <span>📌</span>
            <span>${isHi ? 'पर्यवेक्षक बाड़ा निगरानी निर्देश' : 'Supervisor Enclosure Directive'}</span>
          </h4>
          <p class="diag-sec-content">${d.shift_recommendation || ''}</p>
        </div>
      </div>
    `;
  },

  /* --------------------------------------------------------------------------
     5. Speech Synthesis (Audio Readout - TTS) & Dictation (STT)
     -------------------------------------------------------------------------- */
  toggleSpeakDiagnosis() {
    if (this.isSpeaking) {
      this.stopSpeaking();
      return;
    }
    if (!this.currentDiagnosis) return;

    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');
    const d = this.currentDiagnosis;

    const speechText = isHi
      ? `नैदानिक मूल्यांकन: ${d.assessment}. आपातकालीन स्कोर: ${d.risk_score} में से 10. प्राथमिक उपचार: ${(d.immediate_actions || []).join('. ')}. चिकित्सा प्रोटोकॉल: ${d.medical_protocol}.`
      : `Clinical Assessment: ${d.assessment}. Severity rating: ${d.risk_score} out of 10. Immediate actions: ${(d.immediate_actions || []).join('. ')}. Medical protocol: ${d.medical_protocol}.`;

    this.speakText(speechText, lang);
  },

  speakText(text, lang = 'en') {
    if (!this.speechSynth) {
      showToast('Speech synthesis not supported in this browser.', 'warning');
      return;
    }

    this.stopSpeaking();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === 'hi' ? 'hi-IN' : 'en-US';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    const speakBtn = document.getElementById('btn-speak-diag');
    const speakTextElem = document.getElementById('speak-diag-text');

    utterance.onstart = () => {
      this.isSpeaking = true;
      if (speakTextElem) speakTextElem.textContent = 'Stop Audio';
      if (speakBtn) speakBtn.style.color = '#e11d48';
    };

    utterance.onend = () => {
      this.isSpeaking = false;
      if (speakTextElem) speakTextElem.textContent = 'Listen';
      if (speakBtn) speakBtn.style.color = '';
    };

    utterance.onerror = () => {
      this.isSpeaking = false;
      if (speakTextElem) speakTextElem.textContent = 'Listen';
      if (speakBtn) speakBtn.style.color = '';
    };

    this.currentUtterance = utterance;
    this.speechSynth.speak(utterance);
  },

  stopSpeaking() {
    if (this.speechSynth && this.isSpeaking) {
      this.speechSynth.cancel();
      this.isSpeaking = false;
      const speakTextElem = document.getElementById('speak-diag-text');
      const speakBtn = document.getElementById('btn-speak-diag');
      if (speakTextElem) speakTextElem.textContent = 'Listen';
      if (speakBtn) speakBtn.style.color = '';
    }
  },

  initSpeechRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      console.debug('Web Speech Recognition API not available.');
      return;
    }

    this.recognition = new SpeechRec();
    this.recognition.continuous = false;
    this.recognition.interimResults = false;

    this.recognition.onstart = () => {
      this.isListening = true;
      const micBtn = document.getElementById('ai-chat-mic-btn');
      if (micBtn) micBtn.classList.add('listening');
      showToast(AppState.lang === 'hi' ? 'बोलिए, सुन रहा हूँ...' : 'Listening... Speak now', 'info');
    };

    this.recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      const input = document.getElementById('ai-chat-input');
      if (input && transcript) {
        input.value = transcript;
        this.handleSendChatMessage(transcript);
      }
    };

    this.recognition.onerror = (e) => {
      console.debug('Speech recognition error:', e);
      this.stopVoiceDictation();
    };

    this.recognition.onend = () => {
      this.stopVoiceDictation();
    };
  },

  toggleVoiceDictation() {
    if (!this.recognition) {
      showToast('Speech recognition not supported in this browser.', 'warning');
      return;
    }

    if (this.isListening) {
      this.recognition.stop();
      this.stopVoiceDictation();
    } else {
      this.recognition.lang = AppState.lang === 'hi' ? 'hi-IN' : 'en-US';
      try {
        this.recognition.start();
      } catch (e) {
        console.debug('Speech recognition start failed:', e);
      }
    }
  },

  stopVoiceDictation() {
    this.isListening = false;
    const micBtn = document.getElementById('ai-chat-mic-btn');
    if (micBtn) micBtn.classList.remove('listening');
  },

  /* --------------------------------------------------------------------------
     6. Copy & Print Actions
     -------------------------------------------------------------------------- */
  copyDiagnosisContent() {
    if (!this.currentDiagnosis) return;
    const d = this.currentDiagnosis;
    const isHi = (AppState.lang === 'hi');

    const formatted = `[GROQ VETERINARY CLINICAL DIAGNOSIS]
Score: ${d.risk_score}/10
Assessment: ${d.assessment}

Immediate Caretaker Protocol:
${(d.immediate_actions || []).map((a, i) => `${i + 1}. ${a}`).join('\n')}

Medical Rx Formulation:
${d.medical_protocol}

Shift Recommendation:
${d.shift_recommendation}
Generated via: ${d.powered_by}`;

    navigator.clipboard.writeText(formatted).then(() => {
      showToast(isHi ? 'नैदानिक रिपोर्ट क्लिपबोर्ड में कॉपी की गई।' : 'Diagnosis report copied to clipboard.', 'success');
    });
  },

  printDiagnosisContent() {
    window.print();
  },

  /* --------------------------------------------------------------------------
     7. Shift Handover Audit Report
     -------------------------------------------------------------------------- */
  async handleGenerateShiftReport() {
    const outputBox = document.getElementById('ai-audit-output');
    const shiftSelect = document.getElementById('report-shift-select');
    const shiftVal = shiftSelect ? shiftSelect.value : 'Morning Duty Shift (05:00 - 13:00 IST)';
    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    if (outputBox) {
      outputBox.style.display = 'block';
      outputBox.innerHTML = `
        <div class="ai-loading-spinner">
          <div class="spinner"></div>
          <span>${isHi ? '⚡ ग्रोक ए.आई. व्यापक शिफ्ट ऑडिट रिपोर्ट तैयार कर रहा है...' : '⚡ Groq LPU™ Generating Comprehensive Veterinary Shift Handover Audit...'}</span>
        </div>
      `;
    }

    try {
      const res = await apiRequest(`/api/ai/shift-report?lang=${lang}&shift=${encodeURIComponent(shiftVal)}`);
      if (res.success && outputBox) {
        const r = res.report;
        const findingsHtml = (r.key_clinical_findings || []).map(f => `<li>• ${f}</li>`).join('');
        const tasksHtml = (r.supervisor_tasks || []).map(t => `<li>✓ ${t}</li>`).join('');

        outputBox.innerHTML = `
          <div class="report-result-card" id="printable-shift-report">
            <div class="report-header">
              <div>
                <h3 class="report-title">${r.title || 'Gaushala Shift Audit Report'}</h3>
                <span class="report-meta">${r.generated_at} | Shift: <strong>${r.shift}</strong></span>
              </div>
              <div style="display:flex; gap:0.5rem; align-items:center;">
                <button class="btn-subtle-tool" onclick="window.print()">
                  <span>🖨️ Print Report</span>
                </button>
                <span class="ai-badge-chip">⚡ ${r.powered_by}</span>
              </div>
            </div>

            <div class="report-stat-bar">
              <div class="rep-stat">
                <strong>${r.herd_census?.total_headcount || 48}</strong>
                <div>${isHi ? 'कुल गोवंश गणना' : 'Total Cattle Headcount'}</div>
              </div>
              <div class="rep-stat">
                <strong style="color:#10b981;">${r.herd_census?.motion_nominal_percent || '85%'}</strong>
                <div>${isHi ? 'सक्रिय चारागाह अनुपात' : 'Active Motion Ratio'}</div>
              </div>
              <div class="rep-stat">
                <strong style="color:#e11d48;">${r.herd_census?.alerts_logged || 0}</strong>
                <div>${isHi ? 'सक्रिय अलर्ट दर्ज' : 'Active Distress Events'}</div>
              </div>
            </div>

            <div class="report-section">
              <h4>${isHi ? '📋 प्रमुख नैदानिक एवं बाड़ा टेलीमेट्री निष्कर्ष' : 'Key Clinical & Enclosure Findings'}</h4>
              <ul class="report-list">${findingsHtml}</ul>
            </div>

            <div class="report-section">
              <h4>${isHi ? '✅ अगली शिफ्ट हेतु पर्यवेक्षक कार्य चेकलिस्ट' : 'Supervisor Handover Task Checklist'}</h4>
              <ul class="report-tasks">${tasksHtml}</ul>
            </div>
          </div>
        `;
        showToast(isHi ? 'शिफ्ट ऑडिट रिपोर्ट तैयार।' : 'Shift audit report ready.', 'success');
      }
    } catch (err) {
      if (outputBox) outputBox.innerHTML = `<div class="ai-error-box">${err.message}</div>`;
    }
  },

  /* --------------------------------------------------------------------------
     8. Interactive AI Copilot Chat
     -------------------------------------------------------------------------- */
  async handleSendChatMessage(overrideText = null) {
    const input = document.getElementById('ai-chat-input');
    const history = document.getElementById('ai-chat-history');
    const lang = AppState.lang || 'en';
    const isHi = (lang === 'hi');

    const question = overrideText || (input ? input.value.trim() : '');
    if (!question || !history) return;
    if (input) input.value = '';

    // Append User Message
    const userMsg = document.createElement('div');
    userMsg.className = 'chat-bubble chat-bubble-user';
    userMsg.innerHTML = `
      <div class="chat-bubble-header">
        <span class="chat-sender">${isHi ? 'आप (पर्यवेक्षक)' : 'You (Supervisor)'}</span>
        <span class="chat-time">Now</span>
      </div>
      <div class="chat-text">${this.escapeHtml(question)}</div>
    `;
    history.appendChild(userMsg);
    history.scrollTop = history.scrollHeight;

    // Append AI Loading Bubble
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'chat-bubble chat-bubble-ai';
    loadingMsg.innerHTML = `
      <div class="chat-bubble-header">
        <span class="chat-sender">⚡ Groq LLaMA-3.3-70B</span>
        <span class="chat-time">Inferring...</span>
      </div>
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
        const answer = res.response.answer;
        if (textElem) {
          textElem.className = 'chat-text';
          textElem.innerHTML = this.formatChatMessage(answer);
        }

        const senderElem = loadingMsg.querySelector('.chat-sender');
        if (senderElem) {
          senderElem.textContent = `⚡ ${res.response.model || 'Groq Cloud AI'}`;
        }

        const timeElem = loadingMsg.querySelector('.chat-time');
        if (timeElem) timeElem.textContent = 'Ready';

        // Add tools bar (Listen & Copy)
        const toolsDiv = document.createElement('div');
        toolsDiv.className = 'chat-bubble-tools';
        toolsDiv.innerHTML = `
          <button class="chat-tool-btn" onclick="AiModule.speakText(${JSON.stringify(answer)}, '${lang}')">
            <span>🔊 Speak</span>
          </button>
          <button class="chat-tool-btn" onclick="navigator.clipboard.writeText(${JSON.stringify(answer)}); showToast('${isHi ? 'कॉपी किया गया।' : 'Copied.'}', 'info');">
            <span>📋 Copy</span>
          </button>
        `;
        loadingMsg.appendChild(toolsDiv);
      }
    } catch (err) {
      const textElem = loadingMsg.querySelector('.chat-text');
      if (textElem) {
        textElem.className = 'chat-text text-error';
        textElem.textContent = err.message;
      }
    }
    history.scrollTop = history.scrollHeight;
  },

  formatChatMessage(text) {
    if (!text) return '';
    // Format bolding and bullet points
    let formatted = this.escapeHtml(text);
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\n\s*[-*]\s*(.*?)/g, '<br/>• $1');
    formatted = formatted.replace(/\n\s*(\d+)\.\s*(.*?)/g, '<br/><strong>$1.</strong> $2');
    formatted = formatted.replace(/\n\n/g, '<br/><br/>');
    return formatted;
  },

  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  /* --------------------------------------------------------------------------
     9. Formulary Disease Lookup
     -------------------------------------------------------------------------- */
  askFormularyCopilot(diseaseName) {
    this.switchSubpanel('chat');
    const prompt = AppState.lang === 'hi'
      ? `कृपया मुझे ${diseaseName} के लिए आपातकालीन प्राथमिक उपचार, दवाइयों के नाम (Dosage), एवं शेड प्रबंधन के विस्तृत निर्देश दें।`
      : `Provide urgent clinical treatment protocol, first-aid procedures, and exact veterinary drug dosages for ${diseaseName}.`;

    const input = document.getElementById('ai-chat-input');
    if (input) input.value = prompt;
    this.handleSendChatMessage(prompt);
  },

  filterFormularyCards(query) {
    const q = (query || '').toLowerCase().trim();
    const cards = document.querySelectorAll('#formulary-cards-grid .formulary-card');
    cards.forEach(c => {
      const text = (c.getAttribute('data-disease') || '') + ' ' + c.innerText.toLowerCase();
      c.style.display = text.includes(q) ? 'flex' : 'none';
    });
  }
};
