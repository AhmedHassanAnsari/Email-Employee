// src/pages/Approval.tsx
import React, { useState } from "react";
import { useEvent } from "../context/EventContext";
import EventCard from "../components/EventCard";
import RejectModal from "../components/RejectModal";

const Approval: React.FC = () => {
  const { approval, accept, reject } = useEvent();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const handleAccept = (id: string) => {
    accept(id);
  };

  const handleReject = (id: string) => {
    setSelectedId(id);
    setModalOpen(true);
  };

  const submitFeedback = (feedback: string) => {
    if (selectedId) {
      reject(selectedId, feedback);
    }
    setModalOpen(false);
    setSelectedId(null);
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold mb-4 text-white">Approval</h2>
      {approval.length === 0 ? (
        <p className="text-gray-400">No items pending approval.</p>
      ) : (
        approval.map((event) => (
          <EventCard
            key={event.id}
            event={event}
            onAccept={() => handleAccept(event.id)}
            onReject={() => handleReject(event.id)}
          />
        ))
      )}

      <RejectModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={submitFeedback}
      />
    </div>
  );
};

export default Approval;
