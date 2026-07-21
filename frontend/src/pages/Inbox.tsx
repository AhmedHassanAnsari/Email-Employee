// src/pages/Inbox.tsx
import React from "react";
import { useEvent } from "../context/EventContext";
import EventCard from "../components/EventCard";

const Inbox: React.FC = () => {
  const { inbox, loading, error } = useEvent();

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold mb-4 text-white">Inbox</h2>
      {error && <p className="text-red-400">{error}</p>}
      {loading && inbox.length === 0 ? (
        <p className="text-gray-400">Loading…</p>
      ) : inbox.length === 0 ? (
        <p className="text-gray-400">No inbox items.</p>
      ) : (
        inbox.map((event) => <EventCard key={event.id} event={event} />)
      )}
    </div>
  );
};

export default Inbox;
