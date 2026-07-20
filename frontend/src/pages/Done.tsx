// src/pages/Done.tsx
import React from "react";
import { useEvent } from "../context/EventContext";
import EventCard from "../components/EventCard";

const Done: React.FC = () => {
  const { done } = useEvent();

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold mb-4 text-white">Done</h2>
      {done.length === 0 ? (
        <p className="text-gray-400">No completed items.</p>
      ) : (
        done.map((event) => (
          <EventCard key={event.id} event={event} />
        ))
      )}
    </div>
  );
};

export default Done;
