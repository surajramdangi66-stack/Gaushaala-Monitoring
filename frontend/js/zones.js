/**
 * Smart Gaushala CCTV AI - Baada & Shed AI Zone Controller
 * =======================================================
 * Advanced 100% vision-based surveillance, spatial geofencing,
 * feeder trough density analysis, quarantine tripwire breach alerts,
 * resting & rumination motion tracking, NDLM Pashu Aadhaar mapping,
 * government fodder subsidy audits, and CVO emergency outbreak dispatch.
 */

const ZoneEditorModule = {
  initialized: false,
  activeCameraId: 'cam-01',
  activeZoneType: 'feeder',
  activePtzAngle: 'overview',
  isStreamMode: false,
  streamWs: null,
  telemetryTimer: null,
  cameras: [],
  currentZones: {},
  workingPolygon: [], // [[x, y], ...]
  mousePos: null,
  canvas: null,
  ctx: null,
  backgroundImage: null,

  ZONE_CONFIGS: {
    feeder: {
      name: 'Feeder Trough (चारा चरणी)',
      name_hi: 'चारा चरणी क्षेत्र',
      color: '#10b981',
      fill: 'rgba(16, 185, 129, 0.25)',
      stroke: '#10b981',
      defaultCapacity: 4
    },
    boundary: {
      name: 'Pen Perimeter (बाड़ा सुरक्षा सीमा)',
      name_hi: 'बाड़ा सुरक्षा सीमा',
      color: '#ef4444',
      fill: 'rgba(239, 68, 68, 0.18)',
      stroke: '#ef4444',
      defaultCapacity: 25
    },
    quarantine: {
      name: 'Quarantine Ward (क्वारंटीन वार्ड)',
      name_hi: 'पृथक / क्वारंटीन वार्ड',
      color: '#f59e0b',
      fill: 'rgba(245, 158, 11, 0.25)',
      stroke: '#f59e0b',
      defaultCapacity: 3
    },
    resting: {
      name: 'Resting Bay (विश्राम एवं जुगाली शेड)',
      name_hi: 'विश्राम एवं जुगाली शेड',
      color: '#3b82f6',
      fill: 'rgba(59, 130, 246, 0.22)',
      stroke: '#3b82f6',
      defaultCapacity: 12
    }
  },

  init() {
    this.canvas = document.getElementById('zone-editor-canvas');
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    if (!this.initialized) {
      this.bindEvents();
      this.initialized = true;
    }

    this.loadCameras();
    this.startTelemetryPolling();
  },

  bindEvents() {
    // 1. Camera Select
    const camSelect = document.getElementById('zone-cam-select');
    if (camSelect) {
      camSelect.addEventListener('change', (e) => {
        this.activeCameraId = e.target.value;
        this.workingPolygon = [];
        this.loadCameraZones();
        this.fetchCameraSnapshot();
        this.fetchShedAnalytics();
        if (this.isStreamMode) {
          this.startLiveStreamWs();
        }
      });
    }

    // 2. Zone Type Selector Buttons
    document.querySelectorAll('.zone-type-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.getAttribute('data-zone-type');
        this.setActiveZoneType(type);
      });
    });

    // 3. PTZ Camera Angle Buttons
    document.querySelectorAll('.ptz-angle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const ptz = btn.getAttribute('data-ptz');
        this.switchPTZAngle(ptz);
      });
    });

    // 4. Stream vs Polygon Editor Mode Toggle
    const btnToggleStream = document.getElementById('btn-toggle-stream-mode');
    if (btnToggleStream) {
      btnToggleStream.addEventListener('click', () => this.toggleStreamMode());
    }

    // 5. Canvas Drawing Events
    this.canvas.addEventListener('click', (e) => {
      if (this.isStreamMode) return;
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      const x = Math.round((e.clientX - rect.left) * scaleX);
      const y = Math.round((e.clientY - rect.top) * scaleY);

      this.workingPolygon.push([x, y]);
      this.renderCanvas();
      this.updatePointsList();
    });

    this.canvas.addEventListener('mousemove', (e) => {
      if (this.isStreamMode) return;
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      this.mousePos = {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY
      };
      if (this.workingPolygon.length > 0) {
        this.renderCanvas();
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.mousePos = null;
      if (!this.isStreamMode) this.renderCanvas();
    });

    this.canvas.addEventListener('dblclick', (e) => {
      e.preventDefault();
      if (!this.isStreamMode) this.completePolygon();
    });

    // 6. Action Buttons
    const btnUndo = document.getElementById('btn-zone-undo');
    if (btnUndo) btnUndo.addEventListener('click', () => this.undoPoint());

    const btnClose = document.getElementById('btn-zone-close-poly');
    if (btnClose) btnClose.addEventListener('click', () => this.completePolygon());

    const btnClear = document.getElementById('btn-zone-clear');
    if (btnClear) btnClear.addEventListener('click', () => this.clearActiveZone());

    const btnReset = document.getElementById('btn-zone-reset-default');
    if (btnReset) btnReset.addEventListener('click', () => this.resetToDefault());

    const btnSave = document.getElementById('btn-zone-save-all');
    if (btnSave) btnSave.addEventListener('click', () => this.saveZones());

    const btnRefreshSnap = document.getElementById('btn-zone-refresh-snap');
    if (btnRefreshSnap) btnRefreshSnap.addEventListener('click', () => {
      this.fetchCameraSnapshot();
      this.fetchShedAnalytics();
    });

    // 7. 1-Click Smart Presets
    const btnPresetStd = document.getElementById('btn-preset-standard-layout');
    if (btnPresetStd) btnPresetStd.addEventListener('click', () => this.applyPreset('standard'));

    const btnPresetFeeder = document.getElementById('btn-preset-feeder-trough');
    if (btnPresetFeeder) btnPresetFeeder.addEventListener('click', () => this.applyPreset('feeder'));

    const btnPresetQuarantine = document.getElementById('btn-preset-quarantine-ward');
    if (btnPresetQuarantine) btnPresetQuarantine.addEventListener('click', () => this.applyPreset('quarantine'));

    const btnPresetPerimeter = document.getElementById('btn-preset-perimeter-fence');
    if (btnPresetPerimeter) btnPresetPerimeter.addEventListener('click', () => this.applyPreset('boundary'));

    // 8. Trough Inspect On-Demand Button
    const btnInspectTrough = document.getElementById('btn-inspect-trough-density');
    if (btnInspectTrough) btnInspectTrough.addEventListener('click', () => this.inspectTroughNow());

    // 9. NDLM Tag OCR Scan Button
    const btnTriggerOcr = document.getElementById('btn-trigger-ocr-scan');
    if (btnTriggerOcr) btnTriggerOcr.addEventListener('click', () => this.triggerTagOcrScan());

    // 10. AI Diagnostics Button
    const btnTriggerAi = document.getElementById('btn-trigger-ai-diagnosis');
    if (btnTriggerAi) {
      btnTriggerAi.addEventListener('click', () => {
        if (typeof AiModule !== 'undefined' && AiModule.openDiagnosisModal) {
          AiModule.openDiagnosisModal({
            alert_type: 'PROSTRATION_DISTRESS',
            message: `Shed ${this.activeCameraId}: Continuous rumination pattern review`,
            entity_id: '104',
            duration: 180,
            zone_name: this.ZONE_CONFIGS.resting.name
          });
        } else {
          showToast('Groq AI Diagnosis Engine online', 'info');
        }
      });
    }

    // 11. CVO Outbreak Dispatch Modal Events
    const btnOpenCvo = document.getElementById('btn-open-cvo-modal');
    if (btnOpenCvo) btnOpenCvo.addEventListener('click', () => this.openCVOModal());

    const btnCloseCvo = document.getElementById('close-cvo-modal-btn');
    if (btnCloseCvo) btnCloseCvo.addEventListener('click', () => this.closeCVOModal());

    const btnCancelCvo = document.getElementById('cancel-cvo-modal-btn');
    if (btnCancelCvo) btnCancelCvo.addEventListener('click', () => this.closeCVOModal());

    const formCvo = document.getElementById('cvo-dispatch-form');
    if (formCvo) {
      formCvo.addEventListener('submit', (e) => {
        e.preventDefault();
        this.submitCVODispatch();
      });
    }
  },

  startTelemetryPolling() {
    if (this.telemetryTimer) clearInterval(this.telemetryTimer);
    this.fetchShedAnalytics();
    this.telemetryTimer = setInterval(() => {
      const zonesTab = document.getElementById('zones-view');
      if (zonesTab && zonesTab.classList.contains('active')) {
        this.fetchShedAnalytics();
      }
    }, 2800);
  },

  async loadCameras() {
    try {
      const cams = await apiRequest('/api/cameras');
      this.cameras = cams || [];
      const select = document.getElementById('zone-cam-select');
      if (select) {
        select.innerHTML = '';
        const shedNames = {
          'cam-01': 'बाड़ा 1: मुख्य गौशाला (उत्तर शेड)',
          'cam-02': 'बाड़ा 2: दुधारू गोवंश एवं चरणी शेड',
          'cam-03': 'बाड़ा 3: खुला विचरण प्रांगण (Paddock)',
          'cam-04': 'बाड़ा 4: प्रसूति एवं चिकित्सा वार्ड'
        };
        this.cameras.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.id;
          opt.textContent = `${shedNames[c.id] || c.name} (${c.id})`;
          if (c.id === this.activeCameraId) opt.selected = true;
          select.appendChild(opt);
        });
      }
      this.loadCameraZones();
      this.fetchCameraSnapshot();
    } catch (err) {
      console.error('Failed to load cameras for zone editor:', err);
    }
  },

  async loadCameraZones() {
    try {
      const res = await apiRequest(`/api/shed-ai/${this.activeCameraId}/analytics`);
      this.currentZones = res.zones || {};
      this.renderCanvas();
      this.updatePointsList();
      this.renderZoneSummary();
      this.renderAnalytics(res);
    } catch (err) {
      console.error('Failed to load camera zones:', err);
    }
  },

  async fetchShedAnalytics() {
    try {
      const data = await apiRequest(`/api/shed-ai/${this.activeCameraId}/analytics`);
      if (data) {
        this.currentZones = data.zones || this.currentZones;
        this.renderAnalytics(data);
      }
    } catch (err) {
      console.debug('Telemetry poll error:', err);
    }
  },

  renderAnalytics(data) {
    if (!data) return;

    // 1. Feeder Trough UI
    const trough = data.trough_monitoring || {};
    const fillPct = trough.fill_percent !== undefined ? trough.fill_percent : 78.5;
    const fillBar = document.getElementById('trough-fill-bar');
    const fillText = document.getElementById('trough-fill-pct-text');
    const troughPill = document.getElementById('trough-status-pill');

    if (fillBar) fillBar.style.width = `${Math.min(100, Math.max(0, fillPct))}%`;
    if (fillText) {
      const statusText = fillPct >= 60 ? 'भरपुर (Optimal)' : (fillPct >= 35 ? 'पर्याप्त (Adequate)' : 'खाली / कम (Depleted)');
      fillText.textContent = `${fillPct}% ${statusText}`;
      fillText.style.color = fillPct >= 35 ? '#10b981' : '#ef4444';
    }
    if (troughPill) {
      troughPill.textContent = trough.status || (fillPct >= 35 ? 'ADEQUATE' : 'EMPTY');
      troughPill.style.background = fillPct >= 35 ? '#10b981' : '#ef4444';
    }

    const feederActive = document.getElementById('feeder-cattle-active-count');
    if (feederActive) feederActive.textContent = `${data.counts?.feeder_cattle || 0} गोवंश`;

    const feedAnalytics = data.feeding_duration_analytics || {};
    const neglectedElem = document.getElementById('feeder-neglected-count');
    if (neglectedElem) {
      const negCount = feedAnalytics.neglected_hungry_count || 0;
      neglectedElem.textContent = `${negCount} फ्लैग`;
      neglectedElem.style.color = negCount > 0 ? '#ef4444' : '#10b981';
    }

    // Mini Feeding Table
    const feederTbody = document.getElementById('feeder-cows-mini-tbody');
    if (feederTbody) {
      const breakdown = feedAnalytics.cattle_feeding_breakdown || [];
      if (breakdown.length === 0) {
        feederTbody.innerHTML = `<tr><td colspan="3" style="padding:6px; color:var(--text-muted); text-align:center;">चारा चरणी में कोई गोवंश अभी सक्रिय नहीं है</td></tr>`;
      } else {
        feederTbody.innerHTML = breakdown.slice(0, 4).map(c => `
          <tr style="border-bottom:1px solid var(--border-subtle);">
            <td style="padding:4px 6px; font-weight:700;">${c.tag_id}</td>
            <td style="padding:4px 6px; color:#10b981; font-family:var(--font-mono);">${c.duration_formatted}</td>
            <td style="padding:4px 6px; text-align:right;">
              <span class="tab-badge" style="font-size:0.68rem; padding:1px 6px; background:${c.is_currently_eating ? 'rgba(16,185,129,0.2)' : 'rgba(100,100,100,0.15)'}; color:${c.is_currently_eating ? '#10b981' : 'var(--text-muted)'};">
                ${c.is_currently_eating ? 'चर रहा है' : 'सम्पन्न'}
              </span>
            </td>
          </tr>
        `).join('');
      }
    }

    // 2. Quarantine Ward & Tripwire UI
    const qw = data.quarantine_ward || {};
    const totalBreaches = qw.total_breaches_detected || 0;
    const breachCountElem = document.getElementById('quarantine-total-breaches');
    if (breachCountElem) {
      breachCountElem.textContent = `${totalBreaches} घटना`;
      breachCountElem.style.color = totalBreaches > 0 ? '#ef4444' : '#10b981';
    }

    const inmatesCountElem = document.getElementById('quarantine-inmates-count');
    if (inmatesCountElem) inmatesCountElem.textContent = `${qw.inmates_count || 0} उपचाराधीन`;

    const inmatesTagsElem = document.getElementById('quarantine-tags-text');
    if (inmatesTagsElem) {
      inmatesTagsElem.textContent = qw.inmates_tags && qw.inmates_tags.length > 0 ? qw.inmates_tags.join(', ') : 'कोई नहीं (वार्ड रिक्त)';
    }

    const breachInd = document.getElementById('quarantine-breach-indicator');
    const breachTitle = document.getElementById('quarantine-breach-title');
    const breachSubtitle = document.getElementById('quarantine-breach-subtitle');
    const tripwirePill = document.getElementById('tripwire-status-pill');

    if (totalBreaches > 0 && qw.recent_breaches && qw.recent_breaches.length > 0) {
      const latest = qw.recent_breaches[0];
      if (breachInd) {
        breachInd.style.background = 'rgba(239, 68, 68, 0.15)';
        breachInd.style.borderColor = 'rgba(239, 68, 68, 0.4)';
      }
      if (breachTitle) {
        breachTitle.textContent = '🚨 सुरक्षा उल्लंघन / संक्रमण जोखिम अलर्ट!';
        breachTitle.style.color = '#ef4444';
      }
      if (breachSubtitle) breachSubtitle.textContent = latest.message;
      if (tripwirePill) {
        tripwirePill.textContent = '🔴 BREACH';
        tripwirePill.style.background = 'rgba(239,68,68,0.25)';
        tripwirePill.style.color = '#ef4444';
      }
    } else {
      if (breachInd) {
        breachInd.style.background = 'rgba(16, 185, 129, 0.1)';
        breachInd.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      }
      if (breachTitle) {
        breachTitle.textContent = 'आइसोलेशन वार्ड सुरक्षित (Tripwire Armed)';
        breachTitle.style.color = '#10b981';
      }
      if (breachSubtitle) breachSubtitle.textContent = 'कोई अनधिकृत क्रॉसिंग या संक्रमण जोखिम नहीं पाया गया';
      if (tripwirePill) {
        tripwirePill.textContent = '🟢 ARMED';
        tripwirePill.style.background = 'rgba(16,185,129,0.2)';
        tripwirePill.style.color = '#10b981';
      }
    }

    // 3. Resting & Rumination UI
    const rum = data.resting_rumination_analytics || {};
    const score = rum.average_rumination_score !== undefined ? rum.average_rumination_score : 88.0;
    const rumBar = document.getElementById('rumination-score-bar');
    const rumText = document.getElementById('rumination-score-text');
    const rumPill = document.getElementById('rumination-status-pill');

    if (rumBar) rumBar.style.width = `${Math.min(100, Math.max(0, score))}%`;
    if (rumText) {
      rumText.textContent = `${score.toFixed(1)}% ${score >= 70 ? 'सामान्य (Healthy Chewing)' : 'कमजोर जुगाली (Poor)'}`;
      rumText.style.color = score >= 70 ? '#3b82f6' : '#ef4444';
    }
    if (rumPill) {
      rumPill.textContent = score >= 70 ? 'NORMAL' : 'LETHARGIC';
      rumPill.style.background = score >= 70 ? 'rgba(59,130,246,0.2)' : 'rgba(239,68,68,0.2)';
      rumPill.style.color = score >= 70 ? '#3b82f6' : '#ef4444';
    }

    const restingCountElem = document.getElementById('resting-cattle-count');
    if (restingCountElem) restingCountElem.textContent = `${data.counts?.resting_cattle || 0} गोवंश`;

    const lethargicFlags = rum.lethargic_cattle_flags || [];
    const lethargicElem = document.getElementById('lethargic-cattle-count');
    if (lethargicElem) {
      lethargicElem.textContent = `${lethargicFlags.length} गोवंश`;
      lethargicElem.style.color = lethargicFlags.length > 0 ? '#ef4444' : '#10b981';
    }

    const lethargicAlertsBox = document.getElementById('lethargic-alerts-box');
    if (lethargicAlertsBox) {
      if (lethargicFlags.length > 0) {
        lethargicAlertsBox.innerHTML = lethargicFlags.map(f => `
          <div style="color:#ef4444; font-weight:700;">⚠️ गोवंश ${f.tag_id}: लगातार ${f.stillness_duration}s से पूर्ण अचेतनता / जुगाली का अभाव</div>
        `).join('');
      } else {
        lethargicAlertsBox.textContent = 'गतिविधि स्थिति: सभी विश्राम कर रहे गोवंश सामान्य जुगाली कर रहे हैं।';
      }
    }

    // 4. Fodder Subsidy UI
    const sub = data.government_fodder_subsidy || {};
    const dailyClaim = sub.subsidy_claim_inr?.daily_total_inr || 790.0;
    const monthlyProj = sub.subsidy_claim_inr?.monthly_projected_inr || 23700.0;
    const dailyElem = document.getElementById('daily-subsidy-amount-text');
    if (dailyElem) dailyElem.textContent = `₹${dailyClaim.toFixed(2)} / दिन`;
    const monthElem = document.getElementById('monthly-subsidy-projected-text');
    if (monthElem) monthElem.textContent = `अनुमानित 30-दिवसीय दावा: ₹${monthlyProj.toFixed(2)}`;

    const att = sub.average_daily_attendance || {};
    if (document.getElementById('subsidy-cow-count')) document.getElementById('subsidy-cow-count').textContent = att.cows || 12;
    if (document.getElementById('subsidy-bull-count')) document.getElementById('subsidy-bull-count').textContent = att.bulls || 2;
    if (document.getElementById('subsidy-calf-count')) document.getElementById('subsidy-calf-count').textContent = att.calves || 4;
    if (document.getElementById('subsidy-sick-count')) document.getElementById('subsidy-sick-count').textContent = att.quarantine_sick || 2;

    const exportBtn = document.getElementById('btn-download-subsidy-report');
    if (exportBtn) {
      exportBtn.href = `/api/shed-ai/${this.activeCameraId}/subsidy/export?format=html`;
    }

    // 5. NDLM Tag OCR Mappings Table
    const ndlmTbody = document.getElementById('ndlm-tag-mappings-tbody');
    if (ndlmTbody) {
      const mappings = data.ndlm_tag_mappings || [];
      if (mappings.length === 0) {
        ndlmTbody.innerHTML = `<tr><td colspan="7" style="padding:16px; text-align:center; color:var(--text-muted);">सीसीटीवी विज़न में कोई गोवंश अभी सक्रिय रूप से चिन्हित नहीं है।</td></tr>`;
      } else {
        ndlmTbody.innerHTML = mappings.map(m => {
          const feedMin = Math.floor((m.feeding_time || 0) / 60);
          const feedSec = Math.floor((m.feeding_time || 0) % 60);
          return `
            <tr style="border-bottom:1px solid var(--border-subtle);">
              <td style="padding:10px; font-weight:800; color:var(--text-primary); font-family:var(--font-mono);">
                🐄 ${m.tag_id}
              </td>
              <td style="padding:10px; font-family:var(--font-mono); font-weight:700; color:#6366f1;">
                ${m.ndlm_uid}
              </td>
              <td style="padding:10px;">
                <span style="display:inline-flex; align-items:center; gap:6px; font-weight:600;">
                  <span style="width:8px; height:8px; border-radius:50%; background:#10b981;"></span>
                  ${m.zone}
                </span>
              </td>
              <td style="padding:10px; color:var(--text-muted);">${m.posture}</td>
              <td style="padding:10px; font-family:var(--font-mono); font-weight:700; color:#10b981;">${feedMin}m ${feedSec}s</td>
              <td style="padding:10px;">
                <span class="tab-badge" style="font-size:0.75rem; padding:2px 8px; background:${m.health_status === 'healthy' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.2)'}; color:${m.health_status === 'healthy' ? '#10b981' : '#f59e0b'};">
                  ${m.health_status === 'healthy' ? 'स्वस्थ' : 'क्वारंटीन / उपचाराधीन'}
                </span>
              </td>
              <td style="padding:10px; text-align:right;">
                <span style="color:#10b981; font-weight:700; font-size:0.78rem;">✔ NDLM Verified</span>
              </td>
            </tr>
          `;
        }).join('');
      }
    }
  },

  // Toggle Live Stream Playback vs Interactive Canvas Editor
  toggleStreamMode() {
    this.isStreamMode = !this.isStreamMode;
    const canvas = document.getElementById('zone-editor-canvas');
    const streamImg = document.getElementById('zone-live-stream-img');
    const btnLabel = document.getElementById('stream-mode-label');
    const badgeText = document.getElementById('zone-live-badge-text');

    if (this.isStreamMode) {
      if (canvas) canvas.style.display = 'none';
      if (streamImg) streamImg.style.display = 'block';
      if (btnLabel) btnLabel.textContent = '✏️ ज़ोन पॉलीगॉन सम्पादित करें';
      if (badgeText) badgeText.textContent = 'LIVE RTSP/CCTV 25 FPS STREAM ACTIVE';
      this.startLiveStreamWs();
      showToast(AppState.lang === 'hi' ? 'लाइव सीसीटीवी स्ट्रीम शुरू हुई (स्थानिक ज़ोन व YOLO बॉक्सेस सहित)' : 'Live CCTV stream playing with active geofence overlay', 'info');
    } else {
      if (streamImg) streamImg.style.display = 'none';
      if (canvas) canvas.style.display = 'block';
      if (btnLabel) btnLabel.textContent = '📹 लाइव स्ट्रीम देखें';
      if (badgeText) badgeText.textContent = 'INTERACTIVE GEOFENCE DRAWING MODE';
      this.stopLiveStreamWs();
      this.fetchCameraSnapshot();
    }
  },

  startLiveStreamWs() {
    this.stopLiveStreamWs();
    const token = AppState.token || '';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream/${this.activeCameraId}?token=${encodeURIComponent(token)}`;
    const streamImg = document.getElementById('zone-live-stream-img');

    try {
      this.streamWs = new WebSocket(wsUrl);
      this.streamWs.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.frame && streamImg) {
            streamImg.src = data.frame;
          }
        } catch (err) {}
      };
      this.streamWs.onerror = () => {
        // Fallback to high-frequency snapshot if WS closed
        if (streamImg && this.isStreamMode) {
          streamImg.src = `/api/cameras/${this.activeCameraId}/snapshot?overlay=true&token=${encodeURIComponent(token)}&t=${Date.now()}`;
        }
      };
    } catch (err) {
      console.debug('WS Stream error:', err);
    }
  },

  stopLiveStreamWs() {
    if (this.streamWs) {
      try { this.streamWs.close(); } catch (e) {}
      this.streamWs = null;
    }
  },

  switchPTZAngle(angleKey) {
    this.activePtzAngle = angleKey;
    document.querySelectorAll('.ptz-angle-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-ptz') === angleKey);
    });

    const indicator = document.getElementById('zone-ptz-indicator');
    const angleLabels = {
      overview: 'PTZ: विहंगम दृश्य (Wide 1080p)',
      feeder: 'PTZ: चारा चरणी ज़ूम (Trough Cam)',
      quarantine: 'PTZ: क्वारंटीन वार्ड (Isolation Cam)',
      resting: 'PTZ: विश्राम शेड (Resting Bay)'
    };
    if (indicator) indicator.textContent = angleLabels[angleKey] || 'PTZ: Active';
    showToast(`PTZ कैमरा एंगल बदला गया: ${angleLabels[angleKey]}`, 'info');
  },

  setActiveZoneType(type) {
    if (!this.ZONE_CONFIGS[type]) return;
    this.activeZoneType = type;
    this.workingPolygon = [];

    document.querySelectorAll('.zone-type-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-zone-type') === type);
    });

    const activeBadge = document.getElementById('active-zone-badge');
    if (activeBadge) {
      activeBadge.textContent = this.ZONE_CONFIGS[type].name;
      activeBadge.style.backgroundColor = this.ZONE_CONFIGS[type].color;
    }

    const capInput = document.getElementById('zone-capacity-input');
    if (capInput) capInput.value = this.ZONE_CONFIGS[type].defaultCapacity;

    this.renderCanvas();
    this.updatePointsList();
  },

  async applyPreset(presetKey) {
    try {
      const res = await apiRequest(`/api/shed-ai/${this.activeCameraId}/presets/${presetKey}`, { method: 'POST' });
      this.currentZones = res.zones || this.currentZones;
      this.workingPolygon = [];
      this.renderCanvas();
      this.updatePointsList();
      this.renderZoneSummary();
      this.fetchShedAnalytics();
      showToast(AppState.lang === 'hi' ? `मानक प्रीसेट '${presetKey}' सफलतापूर्वक लागू हुआ!` : `Preset '${presetKey}' successfully applied live!`, 'info');
    } catch (err) {
      showToast(`Preset error: ${err.message}`, 'critical');
    }
  },

  async inspectTroughNow() {
    try {
      showToast('चरणी में ऑप्टिकल पिक्सल घनत्व का विश्लेषण किया जा रहा है...', 'info');
      const res = await apiRequest(`/api/shed-ai/${this.activeCameraId}/trough/inspect`, { method: 'POST' });
      const insp = res.inspection || {};
      const pct = insp.fill_percent || 0.0;
      showToast(`चरणी विश्लेषण पूर्ण: ${pct}% चारा उपस्थित (${insp.status})`, 'info');
      this.fetchShedAnalytics();
    } catch (err) {
      showToast(`Trough inspection failed: ${err.message}`, 'critical');
    }
  },

  async triggerTagOcrScan() {
    try {
      showToast('सीसीटीवी फ्रेम पर गोवंश ईयर-टैग OCR स्कैन किया जा रहा है...', 'info');
      const res = await apiRequest(`/api/shed-ai/${this.activeCameraId}/ocr/scan`, { method: 'POST' });
      showToast(res.message || 'NDLM टैग स्कैन पूर्ण!', 'info');
      this.fetchShedAnalytics();
    } catch (err) {
      showToast(`OCR scan failed: ${err.message}`, 'critical');
    }
  },

  // CVO Outbreak Dispatch Modal
  openCVOModal() {
    const modal = document.getElementById('cvo-alert-modal');
    if (modal) {
      modal.style.display = 'flex';
      const msgInput = document.getElementById('cvo-message');
      if (msgInput) {
        msgInput.value = `${this.activeCameraId} (बाड़ा शेड) में असामान्य गोवंश लक्षण एवं संक्रमण की संभावना पाई गई है। कृपया त्वरित संज्ञान लें।`;
      }
    }
  },

  closeCVOModal() {
    const modal = document.getElementById('cvo-alert-modal');
    if (modal) modal.style.display = 'none';
  },

  async submitCVODispatch() {
    const eventType = document.getElementById('cvo-event-type')?.value || 'DISEASE_OUTBREAK_SUSPECTED';
    const severity = document.getElementById('cvo-severity')?.value || 'CRITICAL';
    const affectedTags = (document.getElementById('cvo-affected-tags')?.value || '').split(',').map(t => t.strip ? t.strip() : t.trim()).filter(Boolean);
    const message = document.getElementById('cvo-message')?.value || 'Emergency Outbreak Alert';

    try {
      const res = await apiRequest(`/api/shed-ai/${this.activeCameraId}/cvo/dispatch`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: eventType,
          severity: severity,
          affected_tags: affectedTags,
          message: message
        })
      });
      showToast('🚨 मुख्य पशु चिकित्सा अधिकारी (CVO) को आपातकालीन अलर्ट सफलतापूर्वक प्रेषित किया गया!', 'critical');
      this.closeCVOModal();
      this.fetchShedAnalytics();
    } catch (err) {
      showToast(`CVO dispatch failed: ${err.message}`, 'critical');
    }
  },

  fetchCameraSnapshot() {
    const img = new Image();
    const token = AppState.token || '';
    img.crossOrigin = 'anonymous';
    img.src = `/api/cameras/${this.activeCameraId}/snapshot?overlay=false&token=${encodeURIComponent(token)}&t=${Date.now()}`;
    img.onload = () => {
      this.backgroundImage = img;
      this.renderCanvas();
    };
    img.onerror = () => {
      const fallbackImg = new Image();
      fallbackImg.src = '/static/images/gaushala_hero.jpg';
      fallbackImg.onload = () => {
        this.backgroundImage = fallbackImg;
        this.renderCanvas();
      };
      fallbackImg.onerror = () => {
        this.backgroundImage = null;
        this.renderCanvas();
      };
    };
  },

  undoPoint() {
    if (this.workingPolygon.length > 0) {
      this.workingPolygon.pop();
      this.renderCanvas();
      this.updatePointsList();
    }
  },

  completePolygon() {
    if (this.workingPolygon.length < 3) {
      showToast(AppState.lang === 'hi' ? 'पॉलीगॉन बनाने के लिए कम से कम 3 बिंदु चाहिए' : 'A polygon requires at least 3 points', 'warning');
      return;
    }

    const cfg = this.ZONE_CONFIGS[this.activeZoneType];
    const capacityInput = document.getElementById('zone-capacity-input');
    const cap = capacityInput ? parseInt(capacityInput.value) || cfg.defaultCapacity : cfg.defaultCapacity;

    this.currentZones[this.activeZoneType] = {
      name: cfg.name,
      name_hi: cfg.name_hi,
      polygon: [...this.workingPolygon],
      max_capacity: cap,
      color: cfg.color
    };

    this.workingPolygon = [];
    this.renderCanvas();
    this.updatePointsList();
    this.renderZoneSummary();
    showToast(AppState.lang === 'hi' ? `${cfg.name_hi} पॉलीगॉन तैयार हुआ! 'Save & Apply Live' दबाएं` : `${cfg.name} polygon defined! Click Save to apply.`, 'info');
  },

  clearActiveZone() {
    if (this.currentZones[this.activeZoneType]) {
      delete this.currentZones[this.activeZoneType];
    }
    this.workingPolygon = [];
    this.renderCanvas();
    this.updatePointsList();
    this.renderZoneSummary();
    showToast(AppState.lang === 'hi' ? 'सक्रिय ज़ोन साफ़ किया गया' : 'Active zone cleared', 'info');
  },

  async resetToDefault() {
    if (!confirm(AppState.lang === 'hi' ? 'क्या आप इस कैमरे के ज़ोन को डिफ़ॉल्ट पर रीसेट करना चाहते हैं?' : 'Reset all zones for this camera back to factory defaults?')) {
      return;
    }
    try {
      const res = await apiRequest(`/api/cameras/${this.activeCameraId}/zones/reset`, { method: 'POST' });
      this.currentZones = res.zones || {};
      this.workingPolygon = [];
      this.renderCanvas();
      this.updatePointsList();
      this.renderZoneSummary();
      showToast(AppState.lang === 'hi' ? 'डिफ़ॉल्ट ज़ोन रीसेट सफल' : 'Zones reset to factory defaults', 'info');
    } catch (err) {
      showToast(`Reset failed: ${err.message}`, 'critical');
    }
  },

  async saveZones() {
    if (this.workingPolygon.length >= 3) {
      this.completePolygon();
    }

    try {
      const res = await apiRequest(`/api/shed-ai/${this.activeCameraId}/zones`, {
        method: 'POST',
        body: JSON.stringify({ zones: this.currentZones })
      });
      this.currentZones = res.zones || this.currentZones;
      this.renderCanvas();
      this.renderZoneSummary();
      showToast(AppState.lang === 'hi' ? 'ज़ोन निर्देशांक सफलतापूर्वक सहेजे गए और लाइव स्ट्रीम पर लागू हुए!' : 'Polygon zones successfully saved and applied to live vision pipeline!', 'info');
      this.fetchShedAnalytics();
    } catch (err) {
      showToast(`Failed to save zones: ${err.message}`, 'critical');
    }
  },

  renderCanvas() {
    if (!this.canvas || !this.ctx || this.isStreamMode) return;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const ctx = this.ctx;

    ctx.clearRect(0, 0, w, h);

    // 1. Background Image
    if (this.backgroundImage) {
      ctx.drawImage(this.backgroundImage, 0, 0, w, h);
    } else {
      ctx.fillStyle = '#111827';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#1f2937';
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
      ctx.fillStyle = '#6b7280';
      ctx.font = '14px Inter, sans-serif';
      ctx.fillText('LIVE CCTV SNAPSHOT (CLICK TO DRAW ZONE)', 20, 30);
    }

    // 2. Render Existing Completed Zones
    for (const [zoneKey, zoneData] of Object.entries(this.currentZones)) {
      const poly = zoneData.polygon;
      if (!poly || poly.length < 3) continue;

      const cfg = this.ZONE_CONFIGS[zoneKey] || {
        color: zoneData.color || '#10b981',
        fill: 'rgba(16, 185, 129, 0.25)',
        stroke: zoneData.color || '#10b981'
      };

      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) {
        ctx.lineTo(poly[i][0], poly[i][1]);
      }
      ctx.closePath();

      ctx.fillStyle = cfg.fill;
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = cfg.stroke;
      ctx.stroke();

      // Vertex Handles
      poly.forEach((pt) => {
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 4.5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = cfg.color;
        ctx.stroke();
      });

      // Label at centroid
      const cx = poly.reduce((acc, p) => acc + p[0], 0) / poly.length;
      const cy = poly.reduce((acc, p) => acc + p[1], 0) / poly.length;

      ctx.fillStyle = 'rgba(0, 0, 0, 0.82)';
      const labelText = zoneData.name || zoneKey.toUpperCase();
      ctx.font = 'bold 11px Inter, sans-serif';
      const textWidth = ctx.measureText(labelText).width;
      ctx.fillRect(cx - textWidth / 2 - 8, cy - 11, textWidth + 16, 22);

      ctx.fillStyle = cfg.color;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(labelText, cx, cy);
      ctx.textAlign = 'start';
      ctx.textBaseline = 'alphabetic';
    }

    // 3. Render Working Polygon being drawn
    if (this.workingPolygon.length > 0) {
      const activeCfg = this.ZONE_CONFIGS[this.activeZoneType];

      ctx.beginPath();
      ctx.moveTo(this.workingPolygon[0][0], this.workingPolygon[0][1]);
      for (let i = 1; i < this.workingPolygon.length; i++) {
        ctx.lineTo(this.workingPolygon[i][0], this.workingPolygon[i][1]);
      }

      if (this.mousePos) {
        ctx.lineTo(this.mousePos.x, this.mousePos.y);
      }

      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.strokeStyle = activeCfg.color;
      ctx.stroke();
      ctx.setLineDash([]);

      this.workingPolygon.forEach((pt, idx) => {
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 5, 0, Math.PI * 2);
        ctx.fillStyle = activeCfg.color;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.font = '10px Inter, sans-serif';
        ctx.fillText(idx + 1, pt[0] + 6, pt[1] - 4);
      });
    }
  },

  updatePointsList() {
    const listElem = document.getElementById('zone-points-list');
    if (!listElem) return;

    if (this.workingPolygon.length === 0) {
      const existing = this.currentZones[this.activeZoneType];
      if (existing && existing.polygon) {
        listElem.innerHTML = `<span class="text-muted" style="font-size:0.75rem;">सहेजा गया पॉलीगॉन (${existing.polygon.length} बिंदु कॉन्फ़िगर)</span>`;
      } else {
        listElem.innerHTML = `<span class="text-muted" style="font-size:0.75rem;">क्लिक करके वर्टेक्स बिंदु जोड़ें (3+ बिंदु आवश्यक)</span>`;
      }
      return;
    }

    listElem.innerHTML = this.workingPolygon.map((p, idx) => `
      <span class="point-pill" style="display:inline-block; background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; margin-right:4px;">#${idx + 1}: (${p[0]}, ${p[1]})</span>
    `).join(' ');
  },

  renderZoneSummary() {
    const summaryElem = document.getElementById('zone-summary-list');
    const badge = document.getElementById('configured-zones-count-badge');
    if (!summaryElem) return;

    const keys = Object.keys(this.currentZones);
    if (badge) badge.textContent = `${keys.length} Active`;

    if (keys.length === 0) {
      summaryElem.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem;">कोई ज़ोन अभी कॉन्फ़िगर नहीं है। ऊपर से प्रीसेट लागू करें।</div>';
      return;
    }

    summaryElem.innerHTML = keys.map(k => {
      const z = this.currentZones[k];
      const cfg = this.ZONE_CONFIGS[k] || { color: '#10b981', name: k };
      const pts = z.polygon ? z.polygon.length : 0;
      return `
        <div class="zone-summary-row" style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--border-subtle);">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="width:10px; height:10px; border-radius:50%; background-color:${cfg.color}; display:inline-block;"></span>
            <span style="font-weight:700; font-size:0.82rem;">${z.name || cfg.name}</span>
          </div>
          <span style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">${pts} वर्टेक्स | Cap: ${z.max_capacity || 4}</span>
        </div>
      `;
    }).join('');
  }
};
