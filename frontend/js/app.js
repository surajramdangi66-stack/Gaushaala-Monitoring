const TRANSLATIONS = {
  en: {
    brand_subtitle: "Smart Vision & Cattle Welfare Intelligence",
    auth_mission_tag: "★ National Gaushala Vision & Welfare Intelligence",
    auth_visual_title: "Protecting & Nurturing Gomata with Vision AI",
    auth_visual_desc: "Continuous 24x7 computer vision surveillance, non-invasive behavioral telemetry, and ultra-fast Groq LLaMA-3.3 clinical livestock healthcare automation.",
    hl_yolo: "YOLOv8 Detection",
    hl_distress: "Distress Mitigation",
    hl_cctv: "Continuous Rec",
    
    btn_signin_tab: "Sign In",
    btn_signup_tab: "Create Account",
    login_lbl_user: "Username",
    login_lbl_pass: "Password",
    demo_creds: "Demo Credentials:",
    demo_click_fill: "click to autofill",
    btn_login: "Sign In to Dashboard",
    
    signup_lbl_name: "Full Name",
    signup_lbl_user: "Desired Username",
    signup_lbl_pass: "Create Password",
    signup_lbl_role: "Assign Role",
    btn_signup: "Create Account & Enter",
    
    lbl_language: "Language:",
    btn_connect_cctv_side: "Connect Live CCTV",
    btn_connect_feed: "Connect Live CCTV",
    
    nav_dashboard: "Dashboard",
    nav_cctv: "Live CCTV Feeds",
    nav_alerts: "AI Alerts",
    nav_groq: "Groq AI Automation",
    role_supervisor: "Supervisor",
    
    // Dashboard KPIs
    metric_total_title: "Total Live Cattle Census",
    metric_cattle_unit: "Heads",
    metric_total_sub: "Across all active pens",
    
    metric_active_title: "Active & Grazing",
    metric_active_unit: "Active",
    metric_active_sub: "Nominal roaming & feeding",
    
    metric_resting_title: "Resting / Idle",
    metric_resting_unit: "Resting",
    metric_resting_sub: "Monitored rumination & rest",
    
    metric_system_title: "Surveillance Nodes",
    metric_system_sub: "Configured RTSP camera feeds",
    
    // Dashboard Sections
    sec_cctv_matrix_title: "Live CCTV Optical Matrix",
    sec_cctv_matrix_desc: "Real-time surveillance feeds across Gaushala pens",
    btn_full_quad: "Open Full Quad Monitor",
    sec_enclosures_title: "Enclosure Operations & Herd Telemetry",
    sec_enclosures_desc: "Live headcount, motion ratio, bunk capacity, and geofence safety register",
    
    // Table Headers
    th_enclosure: "Enclosure / Pen",
    th_camera_id: "Camera Node",
    th_live_census: "Live Census",
    th_motion_ratio: "Motion Ratio (Active / Rest)",
    th_feeder: "Feeder Trough",
    th_perimeter: "Perimeter Safety",
    th_action: "Action",
    
    // Side Widgets
    sec_incidents_title: "Live Distress & Alerts",
    btn_view_alerts_log: "View Full Alerts Log →",
    sec_engine_status_title: "AI Engine Telemetry",
    btn_quick_shift_report: "Generate Shift Report",
    
    // Monitor Tab
    lbl_layout: "LAYOUT:",
    btn_overlay_on: "AI Overlays ON",
    btn_overlay_off: "AI Overlays OFF",
    
    // Alerts Tab
    lbl_severity: "FILTER:",
    chip_all: "All Alerts",
    chip_critical: "Critical",
    chip_warning: "Warning",
    chip_info: "Info",
    btn_clear_log: "Clear Log",
    
    // Groq AI Tab
    ai_hero_title: "Livestock Health Automation & Diagnostic AI",
    ai_hero_desc: "Harness ultra-fast LLaMA-3.3 reasoning powered by Groq to diagnose cattle distress, generate veterinary shift handover audit reports, and provide immediate caretaker action protocols.",
    ai_diag_title: "Clinical Distress Diagnosis",
    ai_diag_sub: "Instant clinical diagnosis & caretaker action protocol",
    ai_select_alert: "Select Distress Trigger:",
    btn_run_diag: "Run Groq Diagnosis",
    ai_audit_title: "AI Shift Audit Report",
    ai_audit_sub: "Automated veterinary handover summary",
    ai_audit_desc: "Generates a structured clinical inspection and shift audit report summarizing cattle herd count, active alerts, prostration events, and recommended supervisor tasks.",
    btn_gen_report: "Generate Shift Report",
    ai_chat_title: "Interactive Livestock Intelligence Assistant",
    ai_chat_sub: "Ask clinical, nutrition, or telemetry questions to Groq LLaMA-3.3",
    ai_chat_welcome: "Hello! I am your 24/7 Groq Veterinary and Telemetry Intelligence Assistant. Ask me about cow recumbency protocols, heat stress, feed ratios, or perimeter security.",
    ai_chat_placeholder: "Ask a question (e.g., 'What are the first symptoms of milk fever?')...",
    btn_ask: "Ask AI",
    
    // Add Camera Modal
    modal_add_cam_title: "Connect & Monitor Live CCTV Feed",
    modal_add_cam_subtitle: "Directly ingest RTSP, HTTP IP cameras, or USB webcams into live AI tracking",
    modal_lbl_feed_type: "Camera Feed Protocol / Type",
    modal_lbl_cam_name: "Enclosure / Barn Name",
    modal_lbl_cam_rtsp: "Stream URL or Webcam Device Index",
    btn_probe_stream: "Probe / Test Feed Connection",
    btn_connect_and_monitor: "Connect & Start Live Monitoring"
  },
  hi: {
    brand_subtitle: "स्मार्ट विज़न एवं गोवंश कल्याण बुद्धिमत्ता",
    auth_mission_tag: "★ राष्ट्रीय गोकुल मिशन एवं गोवंश कल्याण ए.आई.",
    auth_visual_title: "गोवंश संरक्षण एवं संवर्धन हेतु कृत्रिम बुद्धिमत्ता",
    auth_visual_desc: "24x7 कंप्यूटर विज़न सीसीटीवी निगरानी, व्यवहारिक टेलीमेट्री एवं त्वरित ग्रोक ए.आई. पशु चिकित्सा स्वचालन।",
    hl_yolo: "YOLOv8 पहचान",
    hl_distress: "संकट त्वरित निवारण",
    hl_cctv: "24x7 निरंतर रिकॉर्ड",
    
    btn_signin_tab: "साइन इन",
    btn_signup_tab: "नया खाता बनाएं",
    login_lbl_user: "उपयोगकर्ता नाम",
    login_lbl_pass: "पासवर्ड",
    demo_creds: "डेमो क्रेडेंशियल्स:",
    demo_click_fill: "स्वतः भरने के लिए क्लिक करें",
    btn_login: "डैशबोर्ड में प्रवेश करें",
    
    signup_lbl_name: "पूरा नाम",
    signup_lbl_user: "वांछित उपयोगकर्ता नाम",
    signup_lbl_pass: "पासवर्ड बनाएं",
    signup_lbl_role: "पद / दायित्व चुनें",
    btn_signup: "खाता बनाएं एवं प्रवेश करें",
    
    lbl_language: "भाषा:",
    btn_connect_cctv_side: "लाइव सीसीटीवी कनेक्ट करें",
    btn_connect_feed: "सीसीटीवी जोड़ें",
    
    nav_dashboard: "डैशबोर्ड",
    nav_cctv: "लाइव सीसीटीवी",
    nav_alerts: "ए.आई. अलर्ट",
    nav_groq: "ग्रोक ए.आई. स्वचालन",
    role_supervisor: "पर्यवेक्षक",
    
    // Dashboard KPIs
    metric_total_title: "कुल जीवित गोवंश संख्या",
    metric_cattle_unit: "गोवंश",
    metric_total_sub: "सभी सक्रिय बाड़ों में",
    
    metric_active_title: "सक्रिय एवं विचरणरत गोवंश",
    metric_active_unit: "सक्रिय",
    metric_active_sub: "चारागाह व शेड में सामान्य विचरण",
    
    metric_resting_title: "विश्रामरत गोवंश संख्या",
    metric_resting_unit: "विश्रामरत",
    metric_resting_sub: "निरीक्षित जुगाली एवं विश्राम",
    
    metric_system_title: "सीसीटीवी निगरानी नोड्स",
    metric_system_sub: "सक्रिय सीसीटीवी एवं आरटीएसपी स्ट्रीम्स",
    
    // Dashboard Sections
    sec_cctv_matrix_title: "लाइव सीसीटीवी ऑप्टिकल मैट्रिक्स",
    sec_cctv_matrix_desc: "गौशाला के बाड़ों से वास्तविक समय सीसीटीवी फीड",
    btn_full_quad: "संपूर्ण क्वाड मॉनिटर खोलें",
    sec_enclosures_title: "बाड़ा संचालन एवं गोवंश टेलीमेट्री",
    sec_enclosures_desc: "लाइव गणना, गतिविधि अनुपात, चारा गर्त क्षमता एवं परिधि सुरक्षा रजिस्टर",
    
    // Table Headers
    th_enclosure: "बाड़ा / परिसर नाम",
    th_camera_id: "कैमरा नोड",
    th_live_census: "जीवित गणना",
    th_motion_ratio: "गतिविधि अनुपात (सक्रिय / विश्राम)",
    th_feeder: "चारागाह गर्त",
    th_perimeter: "परिधि सुरक्षा",
    th_action: "कार्रवाई",
    
    // Side Widgets
    sec_incidents_title: "सक्रिय संकट एवं विसंगतियां",
    btn_view_alerts_log: "सम्पूर्ण अलर्ट लॉग देखें →",
    sec_engine_status_title: "ए.आई. इंजन टेलीमेट्री",
    btn_quick_shift_report: "शिफ्ट रिपोर्ट बनाएं",
    
    // Monitor Tab
    lbl_layout: "लेआउट:",
    btn_overlay_on: "ए.आई. ओवरले चालू",
    btn_overlay_off: "ए.आई. ओवरले बंद",
    
    // Alerts Tab
    lbl_severity: "वर्गीकरण:",
    chip_all: "सभी अलर्ट",
    chip_critical: "अत्यंत गंभीर",
    chip_warning: "चेतावनी",
    chip_info: "सूचना",
    btn_clear_log: "रजिस्टर साफ़ करें",
    
    // Groq AI Tab
    ai_hero_title: "गोवंश स्वास्थ्य स्वचालन एवं नैदानिक ए.आई.",
    ai_hero_desc: "ग्रोक द्वारा संचालित अल्ट्रा-फास्ट LLaMA-3.3 के माध्यम से गोवंश संकट का निदान, शिफ्ट हैंडओवर ऑडिट रिपोर्ट और तत्काल परिचारक कार्य प्रोटोकॉल प्राप्त करें।",
    ai_diag_title: "नैदानिक संकट विश्लेषण",
    ai_diag_sub: "तत्काल पशु चिकित्सा परामर्श एवं परिचारक प्रोटोकॉल",
    ai_select_alert: "संकट स्थिति का चयन करें:",
    btn_run_diag: "ग्रोक निदान चलाएं",
    ai_audit_title: "ए.आई. शिफ्ट ऑडिट रिपोर्ट",
    ai_audit_sub: "स्वचालित पशु चिकित्सा हैंडओवर सारांश",
    ai_audit_desc: "गोवंश संख्या, सक्रिय अलर्ट, सुस्ती की घटनाओं और पर्यवेक्षक निर्देशों का संपूर्ण डिजिटल ऑडिट सारांश तैयार करता है।",
    btn_gen_report: "शिफ्ट रिपोर्ट बनाएं",
    ai_chat_title: "संवादात्मक गोवंश कल्याण सहायक",
    ai_chat_sub: "ग्रोक LLaMA-3.3 से चिकित्सा, पोषण या टेलीमेट्री संबंधी प्रश्न पूछें",
    ai_chat_welcome: "नमस्ते! मैं आपका 24/7 ग्रोक पशु चिकित्सा एवं निगरानी सहायक हूँ। मुझसे गोवंश प्रोलैप्स/रोग, हीट स्ट्रेस, आहार अनुपात या परिधि सुरक्षा के बारे में पूछें।",
    ai_chat_placeholder: "प्रश्न पूछें (उदा. 'मिल्क फीवर या हाइपोकैल्सीमिया के प्राथमिक लक्षण क्या हैं?')...",
    btn_ask: "प्रश्न पूछें",
    
    // Add Camera Modal
    modal_add_cam_title: "लाइव सीसीटीवी फीड कनेक्ट करें",
    modal_add_cam_subtitle: "आरटीएसपी, आईपी कैमरा अथवा वेबकैम को सीधे लाइव ए.आई. ट्रैकिंग में जोड़ें",
    modal_lbl_feed_type: "कैमरा फीड प्रोटोकॉल / प्रकार",
    modal_lbl_cam_name: "परिसर / बाड़ा नाम",
    modal_lbl_cam_rtsp: "स्ट्रीम यूआरएल अथवा वेबकैम इंडेक्स",
    modal_lbl_cam_sim: "यदि नेटवर्क कैमरा ऑफलाइन हो तो गौशाला सिमुलेशन फीड सक्रिय रखें",
    btn_probe_stream: "कैमरा कनेक्शन जांचें (Probe Stream)",
    btn_connect_and_monitor: "कनेक्ट करें एवं लाइव निगरानी शुरू करें"
  }
};

const AppState = {
  token: localStorage.getItem('gaushala_jwt_token') || null,
  user: JSON.parse(localStorage.getItem('gaushala_user') || 'null'),
  activeTab: 'dashboard',
  lang: localStorage.getItem('gaushala_lang') || 'en',
  cameras: [],
  telemetryWs: null,
  unreadAlertsCount: 0
};

// Language Switcher Function
function setLanguage(lang) {
  if (lang !== 'en' && lang !== 'hi') lang = 'en';
  AppState.lang = lang;
  localStorage.setItem('gaushala_lang', lang);

  // Update Buttons
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === lang);
  });

  // Update HTML Lang attribute
  document.documentElement.lang = lang;

  // Translate all elements with data-i18n
  const dict = TRANSLATIONS[lang] || TRANSLATIONS.en;
  document.querySelectorAll('[data-i18n]').forEach(elem => {
    const key = elem.getAttribute('data-i18n');
    if (dict[key]) {
      elem.textContent = dict[key];
    }
  });

  // Translate placeholders with data-i18n-ph
  document.querySelectorAll('[data-i18n-ph]').forEach(elem => {
    const key = elem.getAttribute('data-i18n-ph');
    if (dict[key]) {
      elem.placeholder = dict[key];
    }
  });

  // Update Top Bar titles
  updateTopBarTitle(AppState.activeTab);

  // Refresh active modules to re-render in chosen language
  if (DashboardModule.initialized) {
    DashboardModule.refreshDashboard();
  }
  if (AlertsModule.initialized) {
    AlertsModule.renderAlerts();
  }
}

// API Helper with automatic JWT Bearer header
async function apiRequest(endpoint, options = {}) {
  const headers = options.headers || {};
  if (AppState.token) {
    headers['Authorization'] = `Bearer ${AppState.token}`;
  }
  headers['Content-Type'] = 'application/json';

  const res = await fetch(endpoint, { ...options, headers });
  if (res.status === 401) {
    logout();
    throw new Error('Authentication required');
  }
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// Authentication Actions: Login
async function login(username, password) {
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }
    const data = await res.json();
    AppState.token = data.access_token;
    AppState.user = data.user;
    localStorage.setItem('gaushala_jwt_token', data.access_token);
    localStorage.setItem('gaushala_user', JSON.stringify(data.user));

    hideAuthGateway();
    updateUserUI();
    initAppSession();
    showToast(AppState.lang === 'hi' ? 'सफलतापूर्वक लॉग इन हुए' : `Authenticated as ${data.user.full_name}`, 'info');
  } catch (err) {
    showToast(err.message, 'critical');
    throw err;
  }
}

// Authentication Actions: Register (Sign Up)
async function register(username, password, full_name, role) {
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, full_name, role })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Sign up failed');
    }
    const data = await res.json();
    AppState.token = data.access_token;
    AppState.user = data.user;
    localStorage.setItem('gaushala_jwt_token', data.access_token);
    localStorage.setItem('gaushala_user', JSON.stringify(data.user));

    hideAuthGateway();
    updateUserUI();
    initAppSession();
    showToast(AppState.lang === 'hi' ? 'खाता सफलतापूर्वक बनाया गया' : `Welcome, ${data.user.full_name}! Account created.`, 'info');
  } catch (err) {
    showToast(err.message, 'critical');
    throw err;
  }
}

function logout() {
  AppState.token = null;
  AppState.user = null;
  localStorage.removeItem('gaushala_jwt_token');
  localStorage.removeItem('gaushala_user');
  if (AppState.telemetryWs) {
    AppState.telemetryWs.close();
    AppState.telemetryWs = null;
  }
  MonitorModule.stopAllStreams();
  showAuthGateway();
}

function updateUserUI() {
  const userElem = document.getElementById('user-name-display');
  const userAvatar = document.getElementById('user-avatar');
  const userRole = document.getElementById('user-role-display');
  if (AppState.user) {
    if (userElem) userElem.textContent = AppState.user.username;
    if (userAvatar) userAvatar.textContent = (AppState.user.username[0] || 'A').toUpperCase();
    if (userRole) userRole.textContent = AppState.user.role ? AppState.user.role.toUpperCase() : 'SUPERVISOR';
  }
}

function showAuthGateway() {
  const gateway = document.getElementById('auth-gateway');
  const workspace = document.getElementById('app-workspace');
  if (gateway) gateway.style.display = 'flex';
  if (workspace) workspace.style.display = 'none';
}

function hideAuthGateway() {
  const gateway = document.getElementById('auth-gateway');
  const workspace = document.getElementById('app-workspace');
  if (gateway) gateway.style.display = 'none';
  if (workspace) workspace.style.display = 'flex';
}

// Tab Switching
function switchTab(tabId) {
  AppState.activeTab = tabId;
  
  // Update Left Vertical Sidebar buttons
  document.querySelectorAll('.nav-item-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });

  // Update View panels
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `${tabId}-view`);
  });

  // Update Top Bar titles
  updateTopBarTitle(tabId);

  // Action per tab
  if (tabId === 'alerts') {
    AppState.unreadAlertsCount = 0;
    updateAlertBadge();
    AlertsModule.loadAlerts();
  } else if (tabId === 'monitor') {
    MonitorModule.startVisibleStreams();
  } else if (tabId === 'dashboard') {
    DashboardModule.refreshDashboard();
  } else if (tabId === 'ai') {
    AiModule.checkStatus();
  }
}

function updateTopBarTitle(tabId) {
  const titleElem = document.getElementById('active-tab-title');
  const descElem = document.getElementById('active-tab-desc');
  const isHi = (AppState.lang === 'hi');

  const titles = {
    dashboard: {
      en: { title: "Dashboard Overview", desc: "Real-time cattle census and facility monitoring" },
      hi: { title: "गौशाला डैशबोर्ड सारांश", desc: "वास्तविक समय गोवंश जनगणना एवं बाड़ा टेलीमेट्री" }
    },
    monitor: {
      en: { title: "Live CCTV Surveillance", desc: "Optical multi-camera AI ingestion and activity grid" },
      hi: { title: "लाइव सीसीटीवी निगरानी", desc: "ऑप्टिकल मल्टी-कैमरा ए.आई. विज़न ग्रिड" }
    },
    alerts: {
      en: { title: "AI Alerts & Distress Registry", desc: "Active behavioural anomalies and clinical logs" },
      hi: { title: "ए.आई. सतर्कता एवं संकट रजिस्टर", desc: "सक्रिय व्यवहारिक विसंगतियां एवं पशु चिकित्सा रिकॉर्ड" }
    },
    ai: {
      en: { title: "Groq AI Health Intelligence", desc: "Ultra-fast LLaMA-3.3 livestock clinical reasoning" },
      hi: { title: "ग्रोक ए.आई. स्वास्थ्य बुद्धिमत्ता", desc: "अल्ट्रा-फास्ट LLaMA-3.3 पशु चिकित्सा स्वचालन" }
    }
  };

  const current = titles[tabId] || titles.dashboard;
  const langKey = isHi ? 'hi' : 'en';
  if (titleElem) titleElem.textContent = current[langKey].title;
  if (descElem) descElem.textContent = current[langKey].desc;
}

function updateAlertBadge() {
  const badge = document.getElementById('alert-tab-badge');
  if (badge) {
    if (AppState.unreadAlertsCount > 0) {
      badge.textContent = AppState.unreadAlertsCount;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }
}

// Live Clock
function updateClock() {
  const clockElem = document.getElementById('utc-clock-display');
  if (clockElem) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-IN', { hour12: false });
    clockElem.textContent = `${timeStr} IST`;
  }
}
setInterval(updateClock, 1000);
updateClock();

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const typeKey = type.toLowerCase();
  toast.className = `toast toast-${typeKey}`;
  
  let iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>';
  if (typeKey === 'critical') {
    iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
  } else if (typeKey === 'warning') {
    iconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
  }

  toast.innerHTML = `
    ${iconSvg}
    <span>${message}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    setTimeout(() => toast.remove(), 250);
  }, 4500);
}

// Initialize Active Session
function initAppSession() {
  const wsUrl = `/ws/telemetry?token=${AppState.token || ''}`;
  AppState.telemetryWs = new GaushalaWebSocket(
    wsUrl,
    (data) => {
      if (data.type === 'telemetry') {
        DashboardModule.updateTelemetry(data.metrics);
        if (data.latest_alert) {
          AppState.unreadAlertsCount++;
          updateAlertBadge();
          showToast(`[${data.latest_alert.severity}] ${data.latest_alert.message}`, data.latest_alert.severity.toLowerCase());
          if (AppState.activeTab === 'alerts') {
            AlertsModule.prependAlert(data.latest_alert);
          }
        }
      }
    },
    (err) => console.debug('Telemetry WS err', err),
    () => console.log('Telemetry WS Connected')
  );
  AppState.telemetryWs.connect();

  // Load Initial Data
  DashboardModule.init();
  MonitorModule.init();
  AlertsModule.init();
  AiModule.init();
}

// App DOM Bootstrap
document.addEventListener('DOMContentLoaded', () => {
  updateClock();

  // Setup Language Switcher Listeners
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setLanguage(btn.dataset.lang);
    });
  });

  // Apply saved language
  setLanguage(AppState.lang);

  // Setup Vertical Sidebar Navigation listeners
  document.querySelectorAll('.nav-item-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Setup Auth Tab Toggle: Sign In vs Sign Up
  const signinTabBtn = document.getElementById('tab-signin-toggle');
  const signupTabBtn = document.getElementById('tab-signup-toggle');
  const signinForm = document.getElementById('signin-form');
  const signupForm = document.getElementById('signup-form');

  if (signinTabBtn && signupTabBtn && signinForm && signupForm) {
    signinTabBtn.addEventListener('click', () => {
      signinTabBtn.classList.add('active');
      signupTabBtn.classList.remove('active');
      signinForm.classList.add('active');
      signupForm.classList.remove('active');
    });

    signupTabBtn.addEventListener('click', () => {
      signupTabBtn.classList.add('active');
      signinTabBtn.classList.remove('active');
      signupForm.classList.add('active');
      signinForm.classList.remove('active');
    });
  }

  // Setup Sign In Form Submit
  if (signinForm) {
    signinForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const user = document.getElementById('signin-username').value.trim();
      const pass = document.getElementById('signin-password').value.trim();
      if (!user || !pass) return;
      try {
        await login(user, pass);
      } catch (err) {}
    });
  }

  // Setup Sign Up Form Submit
  if (signupForm) {
    signupForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('signup-fullname').value.trim();
      const user = document.getElementById('signup-username').value.trim();
      const pass = document.getElementById('signup-password').value.trim();
      const role = document.getElementById('signup-role').value;
      if (!user || !pass || !name) return;
      try {
        await register(user, pass, name, role);
      } catch (err) {}
    });
  }

  // Demo Credentials click-to-fill
  const demoFill = document.getElementById('demo-credentials-btn');
  if (demoFill) {
    demoFill.addEventListener('click', () => {
      document.getElementById('signin-username').value = 'admin';
      document.getElementById('signin-password').value = 'gaushala2026';
    });
  }

  // Setup Logout button
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', logout);

  // Dedicated "Connect Live CCTV" Trigger Handlers
  const addCamModal = document.getElementById('add-camera-modal');
  const closeCamModalBtn = document.getElementById('close-add-camera-modal');
  const sideConnectBtn = document.getElementById('sidebar-connect-cctv-btn');
  const topConnectBtn = document.getElementById('topbar-connect-cctv-btn');
  const monitorConnectBtn = document.getElementById('add-camera-btn');

  const openCamModal = () => {
    if (addCamModal) addCamModal.classList.add('active');
  };

  if (sideConnectBtn) sideConnectBtn.addEventListener('click', openCamModal);
  if (topConnectBtn) topConnectBtn.addEventListener('click', openCamModal);
  if (monitorConnectBtn) monitorConnectBtn.addEventListener('click', openCamModal);

  if (closeCamModalBtn && addCamModal) {
    closeCamModalBtn.addEventListener('click', () => {
      addCamModal.classList.remove('active');
    });
  }

  // Presets Quick-Fill for Stream Connect
  document.querySelectorAll('.preset-btn').forEach(pBtn => {
    pBtn.addEventListener('click', () => {
      const urlInput = document.getElementById('cam-input-rtsp');
      const nameInput = document.getElementById('cam-input-name');
      if (urlInput) urlInput.value = pBtn.dataset.url;
      if (nameInput && pBtn.dataset.name) nameInput.value = pBtn.dataset.name;
    });
  });

  // Probe Stream Connection Button
  const probeBtn = document.getElementById('btn-probe-stream');
  const probeStatus = document.getElementById('probe-status-msg');
  if (probeBtn && probeStatus) {
    probeBtn.addEventListener('click', async () => {
      const urlInput = document.getElementById('cam-input-rtsp');
      const rtspUrl = urlInput ? urlInput.value.trim() : '';
      if (!rtspUrl) {
        showToast('Please enter a stream URL or device index', 'warning');
        return;
      }

      probeStatus.style.display = 'block';
      probeStatus.className = 'probe-result-status';
      probeStatus.textContent = 'Probing stream socket & latency...';

      try {
        const res = await apiRequest('/api/cameras/probe', {
          method: 'POST',
          body: JSON.stringify({ rtsp_url: rtspUrl })
        });
        if (res.online) {
          probeStatus.className = 'probe-result-status probe-success';
          probeStatus.textContent = `✓ ${res.message || 'Stream reachable'}`;
        } else {
          probeStatus.className = 'probe-result-status probe-failed';
          probeStatus.textContent = `✗ ${res.message || 'Connection failed'}`;
        }
      } catch (e) {
        probeStatus.className = 'probe-result-status probe-failed';
        probeStatus.textContent = `✗ ${e.message}`;
      }
    });
  }

  // Add / Connect Camera Form Submission
  const addCamForm = document.getElementById('add-camera-form');
  if (addCamForm) {
    addCamForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('cam-input-name').value.trim();
      const rtsp = document.getElementById('cam-input-rtsp').value.trim();
      if (!name || !rtsp) return;

      try {
        await apiRequest('/api/cameras', {
          method: 'POST',
          body: JSON.stringify({ name, rtsp_url: rtsp })
        });
        showToast(AppState.lang === 'hi' ? `कैमरा '${name}' सफलतापूर्वक जोड़ा गया` : `Camera '${name}' connected & monitoring started!`, 'info');
        if (addCamModal) addCamModal.classList.remove('active');
        addCamForm.reset();
        
        // Reload cameras in monitor and switch to Monitor tab
        await MonitorModule.loadCameras();
        switchTab('monitor');
      } catch (err) {
        showToast(err.message, 'critical');
      }
    });
  }

  // Check existing session
  if (AppState.token) {
    hideAuthGateway();
    updateUserUI();
    initAppSession();
  } else {
    showAuthGateway();
  }
});
