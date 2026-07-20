// src/context/EventContext.tsx
import React, { createContext, useContext, useState, ReactNode } from "react";
import { v4 as uuidv4 } from "uuid";

export interface Event {
  id: string;
  title: string;
  description: string;
  status: "inbox" | "approval" | "done";
}

interface EventContextProps {
  inbox: Event[];
  approval: Event[];
  done: Event[];
  accept: (id: string) => void;
  reject: (id: string, feedback: string) => void;
}

const EventContext = createContext<EventContextProps | undefined>(undefined);

const mockEvents: Event[] = [
  { id: uuidv4(), title: "Welcome Email", description: "Send welcome email to new hire.", status: "inbox" },
  { id: uuidv4(), title: "Policy Update", description: "Review updated HR policy.", status: "approval" },
  { id: uuidv4(), title: "Monthly Report", description: "Compile monthly performance report.", status: "done" },
];

export const EventProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [inbox, setInbox] = useState<Event[]>(mockEvents.filter((e) => e.status === "inbox"));
  const [approval, setApproval] = useState<Event[]>(mockEvents.filter((e) => e.status === "approval"));
  const [done, setDone] = useState<Event[]>(mockEvents.filter((e) => e.status === "done"));

  const accept = (id: string) => {
    // move from approval to done
    setApproval((prev) => prev.filter((e) => e.id !== id));
    const moved = approval.find((e) => e.id === id);
    if (moved) setDone((prev) => [...prev, { ...moved, status: "done" }]);
  };

  const reject = (id: string, feedback: string) => {
    // keep in approval but could log feedback (for now just console)
    console.log(`Event ${id} rejected with feedback: ${feedback}`);
    // Optionally move back to inbox
    setApproval((prev) => prev.filter((e) => e.id !== id));
    const moved = approval.find((e) => e.id === id);
    if (moved) setInbox((prev) => [...prev, { ...moved, status: "inbox" }]);
  };

  return (
    <EventContext.Provider value={{ inbox, approval, done, accept, reject }}>
      {children}
    </EventContext.Provider>
  );
};

export const useEvent = (): EventContextProps => {
  const ctx = useContext(EventContext);
  if (!ctx) throw new Error("useEvent must be used within EventProvider");
  return ctx;
};
