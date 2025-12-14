import { useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export function useSocket() {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // NOTE: WebSocket connection is intentionally disabled as the backend endpoint is not yet implemented.
    // This prevents "Lost Connection" errors in the UI and console spam.
    // To re-enable, uncomment the block below.
    console.log('[Socket] Connection disabled pending backend implementation.');
    
    /*
    const socketInstance = io(SOCKET_URL, {
      transports: ['websocket'],
      autoConnect: true,
    });

    socketInstance.on('connect', () => {
      setIsConnected(true);
      console.log('[Socket] Connected to', SOCKET_URL);
    });

    socketInstance.on('disconnect', () => {
      setIsConnected(false);
      console.log('[Socket] Disconnected');
    });

    socketInstance.on('connect_error', (error) => {
      console.warn('[Socket] Connection error:', error.message);
    });

    setSocket(socketInstance);

    return () => {
      socketInstance.disconnect();
    };
    */
  }, []);

  return { socket, isConnected };
}

// Hook for live trends updates
export function useLiveTrends() {
  const { socket, isConnected } = useSocket();
  const [trends, setTrends] = useState<any[]>([]);

  useEffect(() => {
    if (!socket) return;

    socket.on('trends:update', (data) => {
      console.log('[Trends] Received update:', data);
      setTrends(data);
    });

    // Request initial data
    socket.emit('trends:subscribe');

    return () => {
      socket.off('trends:update');
      socket.emit('trends:unsubscribe');
    };
  }, [socket]);

  return { trends, isConnected };
}

// Hook for real-time product updates
export function useProductUpdates() {
  const { socket, isConnected } = useSocket();
  const [update, setUpdate] = useState<any>(null);

  useEffect(() => {
    if (!socket) return;

    socket.on('product:deployed', (data) => {
      console.log('[Product] Deployed:', data);
      setUpdate({ type: 'deployed', data });
    });

    socket.on('product:analyzed', (data) => {
      console.log('[Product] Analyzed:', data);
      setUpdate({ type: 'analyzed', data });
    });

    return () => {
      socket.off('product:deployed');
      socket.off('product:analyzed');
    };
  }, [socket]);

  return { update, isConnected };
}
