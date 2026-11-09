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
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = authStore.getAccessToken();

    const instance = io(getWsUrl(), {
      auth: { token },
      transports: ['websocket'],
      reconnectionAttempts: 5,
    });

    socketRef.current = instance;
    setSocket(instance);

    instance.on('connect', () => {
      setConnected(true);
      console.info('[Socket.IO] connected', instance.id);
    });

    instance.on('disconnect', (reason) => {
      setConnected(false);
      console.info('[Socket.IO] disconnected', reason);
    });

    instance.on('reconnect', () => {
      setConnected(true);
      console.info('[Socket.IO] reconnected');
    });

    return () => {
      instance.off('connect');
      instance.off('disconnect');
      instance.off('reconnect');
      instance.disconnect();
      socketRef.current = null;
      setSocket(null);
      setConnected(false);
    };
  }, []);

  return { socket, connected };
};
