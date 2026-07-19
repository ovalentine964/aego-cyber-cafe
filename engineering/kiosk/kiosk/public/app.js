/**
 * Aego Cyber Cafe — Kiosk Frontend Logic
 * Vanilla JS — no frameworks, optimized for slow devices
 */

(function() {
  'use strict';

  // === CONFIG ===
  const CONFIG = {
    API_BASE: '/api',
    WS_URL: (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws',
    RETRY_DELAY: 3000,
    MAX_RETRIES: 5,
    SESSION_KEY: 'aego_session',
    PHONE_KEY: 'aego_phone',
    LANG_KEY: 'aego_lang'
  };

  // === SESSION MANAGEMENT ===
  const Session = {
    id: null,
    startTime: null,

    init() {
      let session = this.load();
      if (!session || this.isExpired(session)) {
        session = this.create();
      }
      this.id = session.id;
      this.startTime = session.startTime;
      return session;
    },

    create() {
      const session = {
        id: 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 8),
        startTime: Date.now(),
        lastActivity: Date.now()
      };
      localStorage.setItem(CONFIG.SESSION_KEY, JSON.stringify(session));
      return session;
    },

    load() {
      try {
        return JSON.parse(localStorage.getItem(CONFIG.SESSION_KEY));
      } catch {
        return null;
      }
    },

    isExpired(session) {
      // Session expires after 2 hours of inactivity
      return Date.now() - (session.lastActivity || 0) > 2 * 60 * 60 * 1000;
    },

    touch() {
      const session = this.load();
      if (session) {
        session.lastActivity = Date.now();
        localStorage.setItem(CONFIG.SESSION_KEY, JSON.stringify(session));
      }
    },

    clear() {
      localStorage.removeItem(CONFIG.SESSION_KEY);
    }
  };

  // === LANGUAGE / i18n ===
  const I18N = {
    en: {
      svc_cv: 'CV Writing',
      svc_gov: 'Gov Services',
      svc_translate: 'Translation',
      svc_print: 'Printing',
      svc_data: 'Data Bundles',
      svc_typing: 'Typing / Forms',
      need_help: 'Need Help?',
      select_service: 'Choose a Service',
      system_ready: 'System Ready',
      processing: 'Processing...',
      error: 'Error',
      success: 'Success',
      pay_with_mpesa: 'Pay with M-Pesa',
      amount_due: 'Amount Due',
      cancel: 'Cancel',
      confirm: 'Confirm',
      back: 'Back',
      home: 'Home',
      print: 'Print',
      submit: 'Submit'
    },
    sw: {
      svc_cv: 'Kuandika CV',
      svc_gov: 'Huduma za Serikali',
      svc_translate: 'Tafsiri',
      svc_print: 'Kuchapisha',
      svc_data: 'Vifurushi vya Data',
      svc_typing: 'Kuchapa / Fomu',
      need_help: 'Unahitaji Msaada?',
      select_service: 'Chagua Huduma',
      system_ready: 'Mfumo Uko Tayari',
      processing: 'Inachakata...',
      error: 'Hitilafu',
      success: 'Imefanikiwa',
      pay_with_mpesa: 'Lipa kwa M-Pesa',
      amount_due: 'Kiasi',
      cancel: 'Ghairi',
      confirm: 'Thibitisha',
      back: 'Rudi',
      home: 'Nyumbani',
      print: 'Chapisha',
      submit: 'Wasilisha'
    },
    lu: {
      svc_cv: 'Ng'eyo CV',
      svc_gov: 'Tich mar Serosa',
      svc_translate: 'Winjo',
      svc_print: 'Goyo',
      svc_data: 'Data Bundles',
      svc_typing: 'Type / Formu',
      need_help: 'In yudo kony?',
      select_service: 'Yer tich',
      system_ready: 'Nywaong\'e ok en',
      processing: 'Ng\'ato e tiyo...',
      error: 'Sethi',
      success: 'Oselo',
      pay_with_mpesa: 'Chul ki M-Pesa',
      amount_due: 'Ng\'eno',
      cancel: 'Chul',
      confirm: 'Mok',
      back: 'Dok',
      home: 'Dala',
      print: 'Goyo',
      submit: 'Oro'
    }
  };

  let currentLang = localStorage.getItem(CONFIG.LANG_KEY) || 'en';

  function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem(CONFIG.LANG_KEY, lang);
    // Update all language buttons
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });
    // Update all i18n elements
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (I18N[lang] && I18N[lang][key]) {
        el.textContent = I18N[lang][key];
      }
    });
  }

  // Make setLanguage global
  window.setLanguage = setLanguage;
  window.currentLang = currentLang;

  // === WEBSOCKET ===
  let ws = null;
  let wsRetries = 0;
  let wsCallbacks = {};

  function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    try {
      ws = new WebSocket(CONFIG.WS_URL);

      ws.onopen = () => {
        wsRetries = 0;
        console.log('[WS] Connected');
        // Send session info
        ws.send(JSON.stringify({ type: 'auth', sessionId: Session.id }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWSMessage(data);
        } catch (e) {
          console.warn('[WS] Invalid message:', event.data);
        }
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected');
        if (wsRetries < CONFIG.MAX_RETRIES) {
          wsRetries++;
          setTimeout(connectWebSocket, CONFIG.RETRY_DELAY * wsRetries);
        }
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
      };
    } catch (e) {
      console.warn('[WS] Connection failed:', e);
    }
  }

  function handleWSMessage(data) {
    switch (data.type) {
      case 'transcription':
        if (wsCallbacks.transcription) wsCallbacks.transcription(data.text);
        break;
      case 'cv_result':
        if (wsCallbacks.cv_result) wsCallbacks.cv_result(data.content);
        break;
      case 'payment_status':
        if (wsCallbacks.payment_status) wsCallbacks.payment_status(data);
        break;
      case 'service_update':
        if (wsCallbacks.service_update) wsCallbacks.service_update(data);
        break;
      case 'notification':
        showToast(data.message, data.level || 'info');
        break;
      default:
        console.log('[WS] Unknown message type:', data.type);
    }
  }

  function sendWS(type, payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, ...payload, sessionId: Session.id }));
    }
  }

  // === TOAST NOTIFICATIONS ===
  function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span>${icons[type] || 'ℹ️'}</span>
      <span style="flex:1">${escapeHtml(message)}</span>
      <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  window.showToast = showToast;

  // === API HELPERS ===
  async function apiGet(path) {
    const res = await fetch(CONFIG.API_BASE + path, {
      headers: { 'X-Session-Id': Session.id }
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(CONFIG.API_BASE + path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Id': Session.id
      },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  }

  // === VOICE RECORDING (shared) ===
  let mediaRecorder = null;
  let audioChunks = [];

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000
        }
      });
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm'
      });
      audioChunks = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };
      mediaRecorder.start(100); // Collect data every 100ms
      return true;
    } catch (err) {
      console.error('Recording failed:', err);
      showToast('Microphone access denied', 'error');
      return false;
    }
  }

  function stopRecording() {
    return new Promise((resolve) => {
      if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        resolve(null);
        return;
      }
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        mediaRecorder.stream.getTracks().forEach(t => t.stop());
        resolve(blob);
      };
      mediaRecorder.stop();
    });
  }

  async function transcribeAudio(audioBlob, lang) {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    formData.append('lang', lang || currentLang);

    const res = await fetch(CONFIG.API_BASE + '/transcribe', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) throw new Error('Transcription failed');
    return res.json();
  }

  // === M-PESA INTEGRATION ===
  async function initiateSTKPush(phone, amount, service, accountRef) {
    const res = await fetch(CONFIG.API_BASE + '/mpesa/stkpush', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: phone,
        amount: amount,
        service: service,
        account_ref: accountRef || `AEGO-${service}-${Date.now()}`
      })
    });
    return res.json();
  }

  async function checkPaymentStatus(checkoutRequestId) {
    const res = await fetch(CONFIG.API_BASE + `/mpesa/status/${checkoutRequestId}`);
    return res.json();
  }

  // === PRINT INTEGRATION ===
  function printContent(content, title) {
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>${escapeHtml(title || 'Aego Print')}</title>
        <style>
          body { font-family: 'Courier New', monospace; padding: 20px; font-size: 14px; line-height: 1.6; }
          h1 { font-size: 18px; text-align: center; }
          pre { white-space: pre-wrap; }
          .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
        </style>
      </head>
      <body>
        <h1>Aego Cyber Cafe — Nyatike, Migori</h1>
        <hr>
        <pre>${escapeHtml(content)}</pre>
        <hr>
        <div class="footer">Printed: ${new Date().toLocaleString('en-KE')} | Thank you!</div>
      </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.print();
  }

  window.printContent = printContent;

  // === OFFLINE QUEUE ===
  const OfflineQueue = {
    KEY: 'aego_offline_queue',

    add(request) {
      const queue = this.load();
      queue.push({ ...request, queuedAt: Date.now() });
      localStorage.setItem(this.KEY, JSON.stringify(queue));
    },

    load() {
      try {
        return JSON.parse(localStorage.getItem(this.KEY)) || [];
      } catch {
        return [];
      }
    },

    async flush() {
      const queue = this.load();
      if (!queue.length) return;

      const remaining = [];
      for (const item of queue) {
        try {
          await fetch(CONFIG.API_BASE + item.path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item.body)
          });
        } catch {
          remaining.push(item);
        }
      }

      localStorage.setItem(this.KEY, JSON.stringify(remaining));
      if (queue.length > remaining.length) {
        showToast(`Synced ${queue.length - remaining.length} queued requests`, 'success');
      }
    },

    clear() {
      localStorage.removeItem(this.KEY);
    }
  };

  // Flush offline queue when back online
  window.addEventListener('online', () => {
    OfflineQueue.flush();
  });

  // === UTILITY ===
  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function formatPhone(phone) {
    phone = phone.replace(/\D/g, '');
    if (phone.startsWith('0')) phone = '254' + phone.substring(1);
    if (!phone.startsWith('254')) phone = '254' + phone;
    return phone;
  }

  function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 6);
  }

  // === INIT ===
  Session.init();
  setLanguage(currentLang);

  // Try WebSocket (non-blocking)
  setTimeout(connectWebSocket, 1000);

  // Export for other scripts
  window.AegoApp = {
    CONFIG,
    Session,
    I18N,
    setLanguage,
    showToast,
    apiGet,
    apiPost,
    startRecording,
    stopRecording,
    transcribeAudio,
    initiateSTKPush,
    checkPaymentStatus,
    printContent,
    OfflineQueue,
    sendWS,
    wsCallbacks,
    formatPhone,
    generateId
  };

})();
