// src/components/EventCard.tsx
import React from "react";
import { Event } from "../context/EventContext";

interface Props {
  event: Event;
  onAccept?: () => void;
  onReject?: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  pending: "New",
  drafted: "Pending Approval",
  approved: "Pending Approval",
  sent: "Completed",
  failed: "Failed",
};

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-blue-500/20 text-blue-300",
  drafted: "bg-yellow-500/20 text-yellow-300",
  approved: "bg-yellow-500/20 text-yellow-300",
  sent: "bg-green-500/20 text-green-300",
  failed: "bg-red-500/20 text-red-300",
};

const EventCard: React.FC<Props> = ({ event, onAccept, onReject }) => {
  const label = STATUS_LABEL[event.db_status] ?? event.db_status;
  const badgeClass = STATUS_CLASS[event.db_status] ?? "bg-gray-500/20 text-gray-300";

  return (
    <div className="glass p-4 mb-4 shadow-md hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xl font-semibold">{event.title}</h3>
        <span className={`text-xs px-2 py-1 rounded-full ${badgeClass}`}>
          {label}
        </span>
      </div>
      {event.from && (
        <p className="text-sm text-gray-400 mb-2">From: {event.from}</p>
      )}
      <p className="text-gray-300 mb-2 whitespace-pre-line">
        {event.description}
      </p>
      {(event.db_status === "drafted" || event.db_status === "approved") &&
        event.draft_response && (
          <div className="mb-4 pl-3 border-l-2 border-yellow-500/40">
            <p className="text-xs uppercase tracking-wide text-yellow-400 mb-1">
              Draft Reply
            </p>
            <p className="text-gray-300 whitespace-pre-line">
              {event.draft_response}
            </p>
          </div>
        )}
      {event.db_status === "sent" && (event.summary || event.final_response) && (
        <div className="mb-4 pl-3 border-l-2 border-green-500/40">
          <p className="text-xs uppercase tracking-wide text-green-400 mb-1">
            Summary
          </p>
          <p className="text-gray-300 whitespace-pre-line">
            {event.summary || event.final_response}
          </p>
        </div>
      )}
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