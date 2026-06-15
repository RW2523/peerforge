/**
 * Auth-Safe SSE Client (TICKET-14)
 * 
 * Uses fetch() with Authorization header instead of EventSource
 * which cannot send custom headers.
 * 
 * Parses SSE protocol (data:, event:, id:, retry:) and emits events.
 */

export interface SSEMessage {
  id?: string;
  event: string;
  data: string;
}

export interface SSEClientOptions {
  onMessage: (message: SSEMessage) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  headers?: Record<string, string>;
}

export class SSEClient {
  private controller: AbortController | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  
  constructor(
    private url: string,
    private options: SSEClientOptions
  ) {}

  connect(): void {
    if (this.controller) {
      console.log('[SSEClient] Already connected to:', this.url);
      return; // Already connected
    }

    console.log('[SSEClient] Connecting to:', this.url, 'at', new Date().toISOString());
    this.controller = new AbortController();
    
    fetch(this.url, {
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
        ...this.options.headers
      },
      signal: this.controller.signal
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`SSE connection failed: ${response.status} ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error('Response body is null');
        }

        console.log('[SSEClient] Connected successfully to:', this.url);
        this.options.onOpen?.();
        this.reconnectDelay = 1000; // Reset on successful connection

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentMessage: Partial<SSEMessage> = { event: 'message' };

        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.trim() === '') {
              // Empty line = end of message
              if (currentMessage.data !== undefined) {
                this.options.onMessage({
                  id: currentMessage.id,
                  event: currentMessage.event || 'message',
                  data: currentMessage.data
                });
              }
              currentMessage = { event: 'message' };
              continue;
            }

            if (line.startsWith(':')) {
              // Comment line, ignore
              continue;
            }

            const colonIndex = line.indexOf(':');
            if (colonIndex === -1) {
              continue;
            }

            const field = line.substring(0, colonIndex);
            let value = line.substring(colonIndex + 1);
            if (value.startsWith(' ')) {
              value = value.substring(1);
            }

            switch (field) {
              case 'event':
                currentMessage.event = value;
                break;
              case 'data':
                currentMessage.data = (currentMessage.data || '') + value;
                break;
              case 'id':
                currentMessage.id = value;
                break;
              case 'retry':
                const retryMs = parseInt(value, 10);
                if (!isNaN(retryMs)) {
                  this.reconnectDelay = retryMs;
                }
                break;
            }
          }
        }
      })
      .catch((error) => {
        if (error.name === 'AbortError') {
          console.log('[SSEClient] Disconnected (intentional):', this.url);
          return; // Intentional disconnect
        }

        console.error('[SSEClient] Error:', error.message, 'URL:', this.url);
        this.options.onError?.(error);
        this.scheduleReconnect();
      });
  }

  disconnect(): void {
    console.log('[SSEClient] Disconnecting from:', this.url);
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.controller) {
      this.controller.abort();
      this.controller = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      console.log('[SSEClient] Reconnect already scheduled');
      return;
    }

    console.log('[SSEClient] Scheduling reconnect in', this.reconnectDelay, 'ms');
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.controller = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      console.log('[SSEClient] Reconnecting now...');
      this.connect();
    }, this.reconnectDelay);
  }
}
