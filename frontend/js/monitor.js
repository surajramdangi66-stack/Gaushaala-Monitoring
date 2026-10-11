const MonitorModule = {
  activeStreams: {}, // camera_id -> GaushalaWebSocket
  streamStates: {},  // camera_id -> { paused: false, overlay: true }
  currentGrid: '2x2',
  globalOverlay: true,
  cameras: [],

  async init() {
    this.setupGridControls();
    this.setupOverlayControls();
    this.setupAddCameraModal();
    await this.loadCameras();
  },

  setupGridControls() {
    document.querySelectorAll('.grid-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.grid-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.currentGrid = btn.dataset.grid;
        
        const grid = document.getElementById('cctv-grid-container');
        if (grid) {
          grid.className = `cctv-grid grid-${this.currentGrid}`;
        }
      });
    });
  },

  setupOverlayControls() {
    const toggleBtn = document.getElementById('global-overlay-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        this.globalOverlay = !this.globalOverlay;
        toggleBtn.classList.toggle('off', !this.globalOverlay);
        toggleBtn.querySelector('.overlay-status-text').textContent = this.globalOverlay ? 'AI Overlays ON' : 'AI Overlays OFF';

        // Notify all active stream WebSockets
        Object.keys(this.activeStreams).forEach(camId => {
          this.setCameraOverlay(camId, this.globalOverlay);
        });
      });
    }
  },

  setupAddCameraModal() {
    const openBtn = document.getElementById('add-camera-btn');
    const modal = document.getElementById('add-camera-modal');
    const closeBtn = document.getElementById('close-add-camera-modal');
    const form = document.getElementById('add-camera-form');

    if (openBtn && modal) {
      openBtn.addEventListener('click', () => modal.classList.add('active'));
    }
    if (closeBtn && modal) {
      closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    }
    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('cam-input-name').value.trim();
        const rtsp = document.getElementById('cam-input-rtsp').value.trim();
        if (!name || !rtsp) return;

        try {
          await apiRequest('/api/cameras', {
            method: 'POST',
            body: JSON.stringify({ name, rtsp_url: rtsp })
          });
          showToast(`Camera '${name}' added successfully`, 'info');
          modal.classList.remove('active');
          form.reset();
          await this.loadCameras();
        } catch (err) {
          showToast(err.message, 'critical');
        }
      });
    }
  },

  async loadCameras() {
    try {
      this.cameras = await apiRequest('/api/cameras');
      this.renderCameraGrid();
      this.startVisibleStreams();
    } catch (err) {
      console.debug('Failed to load cameras:', err);
    }
  },

  renderCameraGrid() {
    const container = document.getElementById('cctv-grid-container');
    if (!container) return;

    container.innerHTML = '';
    this.cameras.forEach(cam => {
      if (!this.streamStates[cam.id]) {
        this.streamStates[cam.id] = { paused: false, overlay: this.globalOverlay };
      }

      const card = document.createElement('div');
      card.className = `camera-feed-card ${cam.has_breach || cam.has_prostration ? 'has-alert' : ''}`;
      card.id = `cam-card-${cam.id}`;
      card.innerHTML = `
        <div class="camera-card-header">
          <div class="cam-title-group">
            <span style="color:var(--gov-gold); font-family:var(--font-mono); font-weight:800; font-size:0.78rem;">DL-GAU-${(cam.id || 'CAM').toUpperCase()}</span>
            <h3>${cam.name}</h3>
            <span class="hud-pill" style="font-size:0.65rem; color:var(--text-muted);">${cam.location || 'परिसर'}</span>
          </div>
          <div class="cam-health-badge">
            <span class="${cam.status === 'online' ? 'pulse-dot-green' : 'pulse-dot-amber'}" style="${cam.status === 'online' ? '' : 'background:#94a3b8; box-shadow:none;'}"></span>
            <span id="cam-status-${cam.id}">${cam.status === 'online' ? 'सक्रिय (ONLINE)' : 'स्टैंडबाय (STANDBY / PAUSED)'}</span>
          </div>
        </div>

        <div class="video-viewport" id="viewport-${cam.id}">
          <div class="video-loading-placeholder" id="placeholder-${cam.id}">
            <div class="spinner"></div>
            <span>सरकारी वीडियो फीड लोड हो रही है... (Connecting Node)</span>
          </div>
          <img class="stream-frame" id="frame-${cam.id}" style="display:none;" alt="${cam.name}" />
          
          <div class="video-hud-overlay">
            <span class="hud-pill" style="display:inline-flex; align-items:center; gap:5px;"><span class="pulse-dot-green" style="width:6px; height:6px;"></span> 24x7 REC // DL-GAU-${(cam.id || 'CAM').toUpperCase()}</span>
            <span class="hud-pill" id="hud-cattle-${cam.id}" style="color:#10b981;">गोवंश: --</span>
            <span class="hud-pill" id="hud-worker-${cam.id}" style="color:#f59e0b; border-color:rgba(245,158,11,0.4);">स्टाफ: --</span>
            <span class="hud-pill" id="hud-fps-${cam.id}">FPS: --</span>
          </div>
        </div>

        <div class="camera-card-footer">
          <div class="cam-counts-preview">
            <span>गोवंश: <strong id="footer-total-${cam.id}">--</strong></span>
            <span>स्टाफ: <strong id="footer-worker-${cam.id}" style="color:#f59e0b;">--</strong></span>
            <span>सक्रिय: <strong id="footer-active-${cam.id}" style="color:#ffffff;">--</strong></span>
            <span>विश्रामरत: <strong id="footer-resting-${cam.id}" style="color:var(--text-secondary);">--</strong></span>
          </div>
          <div class="cam-controls">
            <button class="ctrl-btn" title="Toggle AI Overlay" onclick="MonitorModule.toggleCameraOverlay('${cam.id}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            </button>
            <button class="ctrl-btn" title="Take Full-Res Snapshot" onclick="MonitorModule.takeSnapshot('${cam.id}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            </button>
            <button class="ctrl-btn" title="Pause/Play Stream" onclick="MonitorModule.togglePause('${cam.id}')">
              <svg id="play-icon-${cam.id}" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
            </button>
            <button class="ctrl-btn" title="Fullscreen" onclick="MonitorModule.toggleFullscreen('${cam.id}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
            </button>
          </div>
        </div>
      `;
      container.appendChild(card);
    });
  },

  startVisibleStreams() {
    this.cameras.forEach(cam => {
      this.startCameraStream(cam.id);
    });
  },

  startCameraStream(camId) {
    if (this.activeStreams[camId]) return;

    const streamUrl = `/ws/stream/${camId}?token=${AppState.token || ''}`;
    const frameImg = document.getElementById(`frame-${camId}`);
    const placeholder = document.getElementById(`placeholder-${camId}`);
    const hudFps = document.getElementById(`hud-fps-${camId}`);
    const hudCattle = document.getElementById(`hud-cattle-${camId}`);
    const hudWorker = document.getElementById(`hud-worker-${camId}`);
    const footerTotal = document.getElementById(`footer-total-${camId}`);
    const footerWorker = document.getElementById(`footer-worker-${camId}`);
    const footerActive = document.getElementById(`footer-active-${camId}`);
    const footerResting = document.getElementById(`footer-resting-${camId}`);

    const ws = new GaushalaWebSocket(
      streamUrl,
      (data) => {
        if (this.streamStates[camId]?.paused) return;

        if (data.frame && frameImg) {
          frameImg.src = data.frame;
          if (frameImg.style.display === 'none') {
            frameImg.style.display = 'block';
            if (placeholder) placeholder.style.display = 'none';
          }
        }
        
        const statusElem = document.getElementById(`cam-status-${camId}`);
        if (statusElem && data.status) {
          statusElem.textContent = (data.status === 'online') ? 'सक्रिय (ONLINE)' : 'स्टैंडबाय (STANDBY / PAUSED)';
        }

        const isOnline = (data.status === 'online');
        if (hudFps) hudFps.textContent = `FPS: ${data.fps || 0}`;
        if (hudCattle) hudCattle.textContent = isOnline ? `गोवंश (CATTLE): ${data.total}` : 'NODE STANDBY';
        if (hudWorker) hudWorker.textContent = isOnline ? `स्टाफ (WORKER): ${data.workers ?? 0}` : 'स्टाफ: 0';
        if (footerTotal) footerTotal.textContent = data.total;
        if (footerWorker) footerWorker.textContent = data.workers ?? 0;
        if (footerActive) footerActive.textContent = data.active;
        if (footerResting) footerResting.textContent = data.resting;
      },
      (err) => console.debug(`Stream WS err ${camId}:`, err),
      () => {
        // Send initial overlay state
        ws.send({ overlay: this.streamStates[camId]?.overlay ?? this.globalOverlay });
      }
    );

    this.activeStreams[camId] = ws;
    ws.connect();
  },

  setCameraOverlay(camId, isOverlayOn) {
    if (this.streamStates[camId]) {
      this.streamStates[camId].overlay = isOverlayOn;
    }
    const ws = this.activeStreams[camId];
    if (ws) {
      ws.send({ overlay: isOverlayOn });
    }
  },

  toggleCameraOverlay(camId) {
    const currentState = this.streamStates[camId]?.overlay ?? true;
    this.setCameraOverlay(camId, !currentState);
    showToast(`Overlay for ${camId} ${!currentState ? 'enabled' : 'disabled'}`, 'info');
  },

  togglePause(camId) {
    const state = this.streamStates[camId];
    if (!state) return;
    state.paused = !state.paused;
    const icon = document.getElementById(`play-icon-${camId}`);
    if (icon) {
      icon.innerHTML = state.paused
        ? '<polygon points="5 3 19 12 5 21 5 3"/>'
        : '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
    }
    showToast(`Stream ${camId} ${state.paused ? 'Paused' : 'Resumed'}`, 'info');
  },

  toggleFullscreen(camId) {
    const viewport = document.getElementById(`viewport-${camId}`);
    if (!viewport) return;
    if (!document.fullscreenElement) {
      viewport.requestFullscreen().catch(err => console.debug(err));
    } else {
      document.exitFullscreen();
    }
  },

  async takeSnapshot(camId) {
    try {
      const isOverlay = this.streamStates[camId]?.overlay ?? true;
      const url = `/api/cameras/${camId}/snapshot?overlay=${isOverlay}&token=${AppState.token || ''}`;
      const headers = {};
      if (AppState.token) {
        headers['Authorization'] = `Bearer ${AppState.token}`;
      }
      const res = await fetch(url, { headers });
      if (!res.ok) {
        throw new Error(`Snapshot request failed (${res.status})`);
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      const timeStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.download = `GAUSHALA_${camId.toUpperCase()}_${timeStr}.jpg`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
      showToast(`HD Snapshot exported for ${camId.toUpperCase()}`, 'info');
    } catch (err) {
      showToast('Failed to capture snapshot: ' + err.message, 'critical');
    }
  },

  stopAllStreams() {
    Object.values(this.activeStreams).forEach(ws => ws.close());
    this.activeStreams = {};
  }
};
