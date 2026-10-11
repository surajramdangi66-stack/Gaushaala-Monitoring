class GaushalaWebSocket {
  constructor(url, onMessage, onError, onOpen, onClose) {
    this.url = url;
    this.onMessage = onMessage;
    this.onError = onError;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.ws = null;
    this.reconnectTimer = null;
    this.isClosedManually = false;
  }

  connect() {
    this.isClosedManually = false;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    let fullUrl = this.url;
    if (!this.url.startsWith('ws://') && !this.url.startsWith('wss://')) {
      fullUrl = `${protocol}//${host}${this.url.startsWith('/') ? '' : '/'}${this.url}`;
    }

    try {
      this.ws = new WebSocket(fullUrl);
      this.ws.onopen = (e) => {
        if (this.onOpen) this.onOpen(e);
      };

      this.ws.onmessage = (e) => {
        if (this.onMessage) {
          try {
            const data = JSON.parse(e.data);
            this.onMessage(data);
          } catch (err) {
            this.onMessage(e.data);
          }
        }
      };

      this.ws.onerror = (e) => {
        if (this.onError) this.onError(e);
      };

      this.ws.onclose = (e) => {
        if (this.onClose) this.onClose(e);
        if (!this.isClosedManually) {
          this.reconnectTimer = setTimeout(() => this.connect(), 2000);
        }
      };
    } catch (err) {
      if (!this.isClosedManually) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000);
      }
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }

  close() {
    this.isClosedManually = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close();
    }
  }
}
