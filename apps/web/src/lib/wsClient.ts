/**
 * Production WebSocket Client for Debate Room Transport
 * 
 * Features:
 * - Auto-reconnect with exponential backoff
 * - Heartbeat/ping every 30s
 * - Auth token integration with refresh
 * - Event deduplication by event_id
 * - Command dispatch with ACK/ERROR tracking
 * - TypeScript strict event contracts
 */

export type WSEventType =
  | 'agent_message'
  | 'intervention'
  | 'presence_update'
  | 'typing'
  | 'state_update'
  | 'strategic_action'
  | 'agent_thinking'
  | 'ack'
  | 'error';

export type WSCommandType =
  | 'join_presence'
  | 'leave_presence'
  | 'typing'
  | 'control.pause'
  | 'control.resume'
  | 'control.next_turn'
  | 'control.end'
  | 'intervene';

export interface WSEventEnvelope {
  type: WSEventType;
  debate_id: string;
  sequence_number: number;
  event_id: string;
  occurred_at: string;
  sender_type: 'system' | 'user' | 'agent';
  sender_id: string | null;
  payload: Record<string, any>;
  request_id?: string;
}

export interface WSCommandMessage {
  command: WSCommandType;
  debate_id: string;
  request_id: string;
  payload?: Record<string, any>;
}

export interface WSAckMessage {
  type: 'ack';
  request_id: string;
  command: string;
  timestamp: string;
}

export interface WSErrorMessage {
  type: 'error';
  request_id: string;
  command: string;
  error: string;
  timestamp: string;
}

type WSControlMessage = WSAckMessage | WSErrorMessage;

type WSMessage = WSEventEnvelope | WSAckMessage | WSErrorMessage;

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

export interface WSClientConfig {
  debateId: string;
  getAuthToken: () => Promise<string>;
  onEvent: (event: WSEventEnvelope) => void;
  onConnectionChange: (status: ConnectionStatus) => void;
  onError?: (error: Error) => void;
  baseUrl?: string;
  sinceSequence?: number;
  heartbeatInterval?: number; // ms, default 30000
  reconnectDelays?: number[]; // ms, default [1000, 2000, 4000, 8000, 16000, 30000]
}

export class WSClient {
  private ws: WebSocket | null = null;
  private config: Required<WSClientConfig>;
  private status: ConnectionStatus = 'disconnected';
  private seenEventIds: Set<string> = new Set();
  private reconnectAttempt = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private pendingCommands: Map<string, {
    resolve: (ack: WSAckMessage) => void;
    reject: (error: WSErrorMessage | Error) => void;
    timeout: NodeJS.Timeout;
  }> = new Map();
  // 8 minutes — the constitutional AI pipeline (3 LLM stages × retries) can take 5–7 min.
  // With non-blocking ACK, this only fires if the server itself crashes mid-turn.
  private commandTimeout = 480000;
  private isManualDisconnect = false;

  constructor(config: WSClientConfig) {
    this.config = {
      baseUrl: config.baseUrl || 'ws://localhost:8000',
      debateId: config.debateId,
      getAuthToken: config.getAuthToken,
      onEvent: config.onEvent,
      onConnectionChange: config.onConnectionChange,
      sinceSequence: config.sinceSequence ?? 0,
      heartbeatInterval: config.heartbeatInterval ?? 20000, // Ping every 20s (more frequent to keep alive)
      reconnectDelays: config.reconnectDelays ?? [1000, 2000, 4000, 8000, 16000, 30000],
      onError: config.onError ?? ((err) => console.error('[WSClient]', err)),
    };
  }

  async connect(): Promise<void> {
    if (this.status === 'connected' || this.status === 'connecting') {
      return;
    }

    this.isManualDisconnect = false;
    this.updateStatus('connecting');

    try {
      const token = await this.config.getAuthToken();
      const url = new URL(`${this.config.baseUrl}/ws/debates/${this.config.debateId}`);
      url.searchParams.set('token', token);
      if (this.config.sinceSequence !== undefined) {
        url.searchParams.set('since', String(this.config.sinceSequence));
      }

      this.ws = new WebSocket(url.toString());

      this.ws.onopen = () => {
        this.handleOpen();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event);
      };

      this.ws.onerror = (event) => {
        this.handleError(new Error('WebSocket error'));
      };

      this.ws.onclose = (event) => {
        this.handleClose(event);
      };
    } catch (error) {
      this.config.onError(error as Error);
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.isManualDisconnect = true;
    this.cleanup();
  }

  sendCommand(command: WSCommandType, payload?: Record<string, any>): Promise<WSAckMessage> {
    return new Promise((resolve, reject) => {
      if (this.status !== 'connected' || !this.ws) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      const request_id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const message: WSCommandMessage = {
        command,
        debate_id: this.config.debateId,
        request_id,
        payload: payload || {},
      };

      try {
        this.ws.send(JSON.stringify(message));

        // Set timeout for command response
        const timeout = setTimeout(() => {
          this.pendingCommands.delete(request_id);
          reject(new Error(`Command timeout: ${command}`));
        }, this.commandTimeout);

        this.pendingCommands.set(request_id, { resolve, reject, timeout });
      } catch (error) {
        reject(error);
      }
    });
  }

  private handleOpen(): void {
    this.reconnectAttempt = 0;
    this.updateStatus('connected');
    this.startHeartbeat();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WSMessage = JSON.parse(event.data);

      // Handle ACK messages
      if (message.type === 'ack' && 'request_id' in message) {
        const ackMsg = message as WSAckMessage;
        const pending = this.pendingCommands.get(ackMsg.request_id);
        if (pending) {
          clearTimeout(pending.timeout);
          pending.resolve(ackMsg);
          this.pendingCommands.delete(ackMsg.request_id);
        }
        return;
      }

      // Handle ERROR messages
      if (message.type === 'error' && 'request_id' in message) {
        const errorMsg = message as WSErrorMessage;
        const pending = this.pendingCommands.get(errorMsg.request_id);
        if (pending) {
          clearTimeout(pending.timeout);
          pending.reject(errorMsg);
          this.pendingCommands.delete(errorMsg.request_id);
        }
        return;
      }

      // Handle event messages
      const envelope = message as WSEventEnvelope;
      
      // Deduplicate by event_id
      if (envelope.event_id) {
        if (this.seenEventIds.has(envelope.event_id)) {
          return; // Skip duplicate
        }
        this.seenEventIds.add(envelope.event_id);
        
        // Limit set size (keep last 1000)
        if (this.seenEventIds.size > 1000) {
          const firstId = Array.from(this.seenEventIds)[0];
          this.seenEventIds.delete(firstId);
        }
      }

      // Deliver event to handler
      this.config.onEvent(envelope);
    } catch (error) {
      this.config.onError(error as Error);
    }
  }

  private handleError(error: Error): void {
    this.config.onError(error);
  }

  private handleClose(event: CloseEvent): void {
    this.cleanup();
    
    if (!this.isManualDisconnect) {
      this.scheduleReconnect();
    }
  }

  private cleanup(): void {
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;
      
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      
      this.ws = null;
    }
    
    // Reject all pending commands
    for (const [requestId, pending] of this.pendingCommands.entries()) {
      clearTimeout(pending.timeout);
      pending.reject(new Error('WebSocket disconnected'));
    }
    this.pendingCommands.clear();
    
    this.updateStatus('disconnected');
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = this.config.reconnectDelays[
      Math.min(this.reconnectAttempt, this.config.reconnectDelays.length - 1)
    ];

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempt++;
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // Send ping as typing command with empty payload (ephemeral, won't persist)
        try {
          this.ws.send(JSON.stringify({
            command: 'typing',
            debate_id: this.config.debateId,
            request_id: `ping-${Date.now()}`,
            payload: { ping: true }
          }));
        } catch (error) {
          // Heartbeat send failed, connection likely dead
          this.config.onError(error as Error);
        }
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private updateStatus(status: ConnectionStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.config.onConnectionChange(status);
    }
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }
}
