import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

import { getWsUrl } from '../utils/env';
import { authStore } from '../store/authStore';

interface UseSocketReturn {
  socket: Socket | null;
  connected: boolean;
}

export const useSocket = (): UseSocketReturn => {
  const socketRef = useRef<Socket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = authStore.getAccessToken();

    const socket = io(getWsUrl(), {
      auth: { token },
      transports: ['websocket'],
      reconnectionAttempts: 5,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setConnected(true);
      console.info('[Socket.IO] connected', socket.id);
    });

    socket.on('disconnect', (reason) => {
      setConnected(false);
      console.info('[Socket.IO] disconnected', reason);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
      setConnected(false);
    };
  }, []);

  return { socket: socketRef.current, connected };
};
