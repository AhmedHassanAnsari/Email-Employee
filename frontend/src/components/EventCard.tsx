// src/components/EventCard.tsx
import React from "react";
import { Event } from "../context/EventContext";

interface Props {
  event: Event;
  onAccept?: () => void;
  onReject?: () => void;
}

const EventCard: React.FC<Props> = ({ event, onAccept, onReject }) => {
  return (
    <div className="glass p-4 mb-4 shadow-md hover:shadow-lg transition-shadow">
      <h3 className="text-xl font-semibold mb-2">{event.title}</h3>
      <p className="text-gray-300 mb-4">{event.description}</p>
      {onAccept && onReject && (
        <div className="flex space-x-2">
          <button className="btn-primary" onClick={onAccept}>
            Accept
          </button>
          <button className="btn-secondary" onClick={onReject}>
            Reject
          </button>
        </div>
      )}
    </div>
  );
};

export default EventCard;
