// src/context/EventContext.tsx
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import {
  EmailEvent,
  fetchEmails,
  approveEmail,
  rejectEmail,
} from "../api/client";
import { useAuth } from "./AuthContext";

export type Event = EmailEvent;

interface EventContextProps {
  inbox: Event[];
  approval: Event[];
  done: Event[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  accept: (id: string) => Promise<void>;
  reject: (id: string, feedback: string) => Promise<void>;
}

const EventContext = createContext<EventContextProps | undefined>(undefined);

export const EventProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { userEmail, isAuthenticated } = useAuth();
  const [inbox, setInbox] = useState<Event[]>([]);
  const [approval, setApproval] = useState<Event[]>([]);
  const [done, setDone] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!userEmail) return;
    setLoading(true);
    setError(null);
    try {
      const buckets = await fetchEmails(userEmail);
      setInbox(buckets.inbox);
      setApproval(buckets.approval);
      setDone(buckets.done);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load emails");
    } finally {
      setLoading(false);
    }
  }, [userEmail]);

  useEffect(() => {
    if (isAuthenticated) refresh();
  }, [isAuthenticated, refresh]);

  const accept = useCallback(
    async (id: string) => {
      await approveEmail(id);
      await refresh();
    },
    [refresh]
  );

  const reject = useCallback(
    async (id: string, feedback: string) => {
      await rejectEmail(id, feedback);
      await refresh();
    },
    [refresh]
  );

  return (
    <EventContext.Provider
      value={{ inbox, approval, done, loading, error, refresh, accept, reject }}
    >
      {children}
    </EventContext.Provider>
  );
};

export const useEvent = (): EventContextProps => {
  const ctx = useContext(EventContext);
  if (!ctx) throw new Error("useEvent must be used within EventProvider");
  return ctx;
};
