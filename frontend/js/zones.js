/**
 * Gaushala AI CCTV - Interactive Polygon Zone Editor (ROI)
 * ========================================================
 * Allows operators to visually draw, edit, and configure:
 * - 🟢 Feeder Zones (Safe Feeding Area & Trough)
 * - 🔴 Geofence Boundary (Pen Perimeter)
 * - 🟡 Quarantine Wards (Medical Isolation)
 * - 🔵 Resting Bays (Rest & Rumination Area)
 *
 * Real-time synchronization with FastAPI backend.
 */

const ZoneEditorModule = {
  initialized: false,
  activeCameraId: 'cam-01',
  activeZoneType: 'feeder',
  cameras: [],
  currentZones: {},
  workingPolygon: [], // points currently being drawn: [[x, y], ...]
  mousePos: null,
  canvas: null,
  ctx: null,
  backgroundImage: null,
  refreshTimer: null,

  ZONE_CONFIGS: {
    feeder: {
      name: 'Safe Feeding Zone',
      name_hi: 'चारा चरणी क्षेत्र',
      color: '#10b981',
      fill: 'rgba(16, 185, 129, 0.25)',
      stroke: '#10b981'
    },
    boundary: {
      name: 'Geofence Boundary',
      name_hi: 'बाड़ा सुरक्षा सीमा',
      color: '#ef4444',
      fill: 'rgba(239, 68, 68, 0.20)',
      stroke: '#ef4444'
    },
    quarantine: {
      name: 'Quarantine Ward',
      name_hi: 'पृथक / चिकित्सा वार्ड',
      color: '#f59e0b',
      fill: 'rgba(245, 158, 11, 0.25)',
      stroke: '#f59e0b'
    },
    resting: {
      name: 'Resting Bay',
      name_hi: 'विश्राम क्षेत्र',
      color: '#3b82f6',
      fill: 'rgba(59, 130, 246, 0.22)',
      stroke: '#3b82f6'
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
  },

  bindEvents() {
    // Camera Select
    const camSelect = document.getElementById('zone-cam-select');
    if (camSelect) {
      camSelect.addEventListener('change', (e) => {
        this.activeCameraId = e.target.value;
        this.workingPolygon = [];
        this.loadCameraZones();
        this.fetchCameraSnapshot();
      });
    }

    // Zone Type Buttons
    document.querySelectorAll('.zone-type-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const type = btn.getAttribute('data-zone-type');
        this.setActiveZoneType(type);
      });
    });

    // Canvas Mouse Click: Add Vertex
    this.canvas.addEventListener('click', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      const x = Math.round((e.clientX - rect.left) * scaleX);
      const y = Math.round((e.clientY - rect.top) * scaleY);

      this.workingPolygon.push([x, y]);
      this.renderCanvas();
      this.updatePointsList();
    });

    // Canvas Mouse Move: Rubber-band guideline
    this.canvas.addEventListener('mousemove', (e) => {
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
      this.renderCanvas();
    });

    // Double-click: Complete polygon
    this.canvas.addEventListener('dblclick', (e) => {
      e.preventDefault();
      this.completePolygon();
    });

    // Buttons
    const btnClose = document.getElementById('btn-zone-close-poly');
    if (btnClose) btnClose.addEventListener('click', () => this.completePolygon());

    const btnUndo = document.getElementById('btn-zone-undo');
    if (btnUndo) btnUndo.addEventListener('click', () => this.undoPoint());

    const btnClear = document.getElementById('btn-zone-clear');
    if (btnClear) btnClear.addEventListener('click', () => this.clearActiveZone());

    const btnReset = document.getElementById('btn-zone-reset-default');
    if (btnReset) btnReset.addEventListener('click', () => this.resetToDefault());

    const btnSave = document.getElementById('btn-zone-save-all');
    if (btnSave) btnSave.addEventListener('click', () => this.saveZones());

    const btnRefreshSnap = document.getElementById('btn-zone-refresh-snap');
    if (btnRefreshSnap) btnRefreshSnap.addEventListener('click', () => this.fetchCameraSnapshot());

    // 1-Click Smart Gaushala Presets
    const btnPresetStd = document.getElementById('btn-preset-standard-layout');
    if (btnPresetStd) btnPresetStd.addEventListener('click', () => this.applyStandardLayout());

    const btnPresetFeeder = document.getElementById('btn-preset-feeder-trough');
    if (btnPresetFeeder) btnPresetFeeder.addEventListener('click', () => this.applyFeederPreset());

    const btnPresetPerimeter = document.getElementById('btn-preset-perimeter-fence');
    if (btnPresetPerimeter) btnPresetPerimeter.addEventListener('click', () => this.applyPerimeterPreset());

    // Toggle Sidebar Nav Tab Visibility
    const btnToggleSidebar = document.getElementById('btn-toggle-zones-sidebar');
    if (btnToggleSidebar) {
      btnToggleSidebar.addEventListener('click', () => this.toggleSidebarNav());
      this.syncSidebarNavToggleLabel();
    }
  },

  toggleSidebarNav() {
    const navBtn = document.getElementById('tab-zones-btn');
    const toggleLabel = document.getElementById('zones-sidebar-toggle-text');
    if (!navBtn) return;

    const isHidden = navBtn.style.display === 'none';
    if (isHidden) {
      navBtn.style.display = 'flex';
      localStorage.setItem('gaushala_hide_zones_nav', 'false');
      if (toggleLabel) toggleLabel.textContent = '👁️ साइडबार से छिपाएं';
      showToast(AppState.lang === 'hi' ? 'ज़ोन टैब साइडबार नेविगेशन में दिखाई देगा' : 'Zones tab shown in sidebar', 'info');
    } else {
      navBtn.style.display = 'none';
      localStorage.setItem('gaushala_hide_zones_nav', 'true');
      if (toggleLabel) toggleLabel.textContent = '👁️ साइडबार में दिखाएं';
      showToast(AppState.lang === 'hi' ? 'ज़ोन टैब साइडबार से छिपा दिया गया' : 'Zones tab hidden from sidebar', 'info');
    }
  },

  syncSidebarNavToggleLabel() {
    const navBtn = document.getElementById('tab-zones-btn');
    const toggleLabel = document.getElementById('zones-sidebar-toggle-text');
    const shouldHide = localStorage.getItem('gaushala_hide_zones_nav') === 'true';
    if (navBtn && shouldHide) {
      navBtn.style.display = 'none';
    }
    if (toggleLabel) {
      toggleLabel.textContent = (navBtn && navBtn.style.display === 'none') ? '👁️ साइडबार में दिखाएं' : '👁️ साइडबार से छिपाएं';
    }
  },

  applyStandardLayout() {
    this.currentZones = {
      feeder: {
        name: 'Safe Feeding Zone (चारा चरणी)',
        name_hi: 'चारा चरणी क्षेत्र',
        polygon: [[100, 330], [540, 330], [540, 440], [100, 440]],
        max_capacity: 4,
        color: '#10b981'
      },
      resting: {
        name: 'Resting Bay (विश्राम क्षेत्र)',
        name_hi: 'विश्राम एवं जुगाली शेड',
        polygon: [[50, 90], [360, 90], [360, 300], [50, 300]],
        max_capacity: 10,
        color: '#3b82f6'
      },
      quarantine: {
        name: 'Quarantine Ward (चिकित्सा वार्ड)',
        name_hi: 'पृथक / चिकित्सा वार्ड',
        polygon: [[400, 70], [590, 70], [590, 230], [400, 230]],
        max_capacity: 2,
        color: '#f59e0b'
      },
      boundary: {
        name: 'Pen Perimeter (बाड़ा सुरक्षा बाउंड्री)',
        name_hi: 'बाड़ा सुरक्षा सीमा',
        polygon: [[30, 40], [610, 40], [610, 460], [30, 460]],
        color: '#ef4444'
      }
    };
    this.workingPolygon = [];
    this.renderCanvas();
    this.updatePointsList();
    this.renderZoneSummary();
    showToast(AppState.lang === 'hi' ? 'मानक गौशाला शेड लेआउट लागू हुआ! लाइव लागू करने के लिए "Save & Apply Live" दबाएं' : 'Standard Gaushala shed layout applied! Click "Save & Apply Live" to commit.', 'info');
  },

  applyFeederPreset() {
    this.currentZones['feeder'] = {
      name: 'Safe Feeding Zone (चारा चरणी)',
      name_hi: 'चारा चरणी क्षेत्र',
      polygon: [[120, 340], [520, 340], [520, 440], [120, 440]],
      max_capacity: 4,
      color: '#10b981'
    };
    this.renderCanvas();
    this.updatePointsList();
    this.renderZoneSummary();
    showToast(AppState.lang === 'hi' ? 'चारा चरणी ज़ोन सेट हुआ! सहेजने के लिए Save दबाएं' : 'Feeder trough zone set! Click Save to apply.', 'info');
  },

  applyPerimeterPreset() {
    this.currentZones['boundary'] = {
      name: 'Pen Perimeter (बाड़ा सुरक्षा बाउंड्री)',
      name_hi: 'बाड़ा सुरक्षा सीमा',
      polygon: [[30, 45], [610, 45], [610, 455], [30, 455]],
      color: '#ef4444'
    };
    this.renderCanvas();
    this.updatePointsList();
    this.renderZoneSummary();
    showToast(AppState.lang === 'hi' ? 'बाड़ा सुरक्षा बाउंड्री सेट हुई! सहेजने के लिए Save दबाएं' : 'Pen perimeter boundary set! Click Save to apply.', 'info');
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

    this.renderCanvas();
    this.updatePointsList();
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
      const res = await apiRequest(`/api/cameras/${this.activeCameraId}/zones`);
      this.currentZones = res.zones || {};
      this.renderCanvas();
      this.updatePointsList();
      this.renderZoneSummary();
    } catch (err) {
      console.error('Failed to load camera zones:', err);
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
      // Use authentic Gaushala sanctuary fallback photo
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
    const cap = capacityInput ? parseInt(capacityInput.value) || 4 : 4;

    this.currentZones[this.activeZoneType] = {
      name: cfg.name,
      polygon: [...this.workingPolygon],
      max_capacity: cap,
      color: cfg.color
    };

    this.workingPolygon = [];
    this.renderCanvas();
    this.updatePointsList();
    this.renderZoneSummary();
    showToast(AppState.lang === 'hi' ? `${cfg.name_hi} पॉलीगॉन तैयार हुआ! सहेजने के लिए 'Save' दबाएं` : `${cfg.name} polygon defined! Click 'Save & Apply' to commit.`, 'info');
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
    // If working polygon is still open with 3+ points, commit it
    if (this.workingPolygon.length >= 3) {
      this.completePolygon();
    }

    try {
      const res = await apiRequest(`/api/cameras/${this.activeCameraId}/zones`, {
        method: 'POST',
        body: JSON.stringify({ zones: this.currentZones })
      });
      this.currentZones = res.zones || this.currentZones;
      this.renderCanvas();
      this.renderZoneSummary();
      showToast(AppState.lang === 'hi' ? 'ज़ोन निर्देशांक सफलतापूर्वक सहेजे गए और लाइव स्ट्रीम पर लागू हुए!' : 'Polygon zones successfully saved and applied to live vision pipeline!', 'info');
    } catch (err) {
      showToast(`Failed to save zones: ${err.message}`, 'critical');
    }
  },

  renderCanvas() {
    if (!this.canvas || !this.ctx) return;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const ctx = this.ctx;

    ctx.clearRect(0, 0, w, h);

    // 1. Draw Background Image or Fallback
    if (this.backgroundImage) {
      ctx.drawImage(this.backgroundImage, 0, 0, w, h);
    } else {
      // Dark CCTV grid
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

      // Fill & Stroke
      ctx.fillStyle = cfg.fill;
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = cfg.stroke;
      ctx.stroke();

      // Draw Vertex Handles
      poly.forEach((pt, idx) => {
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 4, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = cfg.color;
        ctx.stroke();
      });

      // Label at centroid
      const cx = poly.reduce((acc, p) => acc + p[0], 0) / poly.length;
      const cy = poly.reduce((acc, p) => acc + p[1], 0) / poly.length;

      ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
      const labelText = zoneData.name || zoneKey.toUpperCase();
      ctx.font = 'bold 12px Inter, sans-serif';
      const textWidth = ctx.measureText(labelText).width;
      ctx.fillRect(cx - textWidth / 2 - 6, cy - 10, textWidth + 12, 20);

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

      // Rubberband to mouse position
      if (this.mousePos) {
        ctx.lineTo(this.mousePos.x, this.mousePos.y);
      }

      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = activeCfg.color;
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw Vertices
      this.workingPolygon.forEach((pt, idx) => {
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 5, 0, Math.PI * 2);
        ctx.fillStyle = activeCfg.color;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();

        // Index label
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
        listElem.innerHTML = `<span class="text-muted" style="font-size:0.8rem;">Existing saved polygon (${existing.polygon.length} points)</span>`;
      } else {
        listElem.innerHTML = `<span class="text-muted" style="font-size:0.8rem;">Click canvas to draw vertices (3+ required)</span>`;
      }
      return;
    }

    listElem.innerHTML = this.workingPolygon.map((p, idx) => `
      <span class="point-pill">#${idx + 1}: (${p[0]}, ${p[1]})</span>
    `).join(' ');
  },

  renderZoneSummary() {
    const summaryElem = document.getElementById('zone-summary-list');
    if (!summaryElem) return;

    const keys = Object.keys(this.currentZones);
    if (keys.length === 0) {
      summaryElem.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">No zones configured yet for this camera.</div>';
      return;
    }

    summaryElem.innerHTML = keys.map(k => {
      const z = this.currentZones[k];
      const cfg = this.ZONE_CONFIGS[k] || { color: '#10b981' };
      const pts = z.polygon ? z.polygon.length : 0;
      return `
        <div class="zone-summary-row" style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--border-subtle);">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="width:10px; height:10px; border-radius:50%; background-color:${cfg.color}; display:inline-block;"></span>
            <span style="font-weight:600; font-size:0.85rem;">${z.name || k}</span>
          </div>
          <span style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">${pts} vertices</span>
        </div>
      `;
    }).join('');
  }
};
