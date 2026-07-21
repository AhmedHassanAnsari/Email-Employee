// src/pages/Approval.tsx
import React, { useState } from "react";
import { useEvent } from "../context/EventContext";
import EventCard from "../components/EventCard";
import RejectModal from "../components/RejectModal";

const Approval: React.FC = () => {
  const { approval, accept, reject, loading, error } = useEvent();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleAccept = async (id: string) => {
    setBusy(true);
    setActionError(null);
    try {
      await accept(id);
    } catch (e: any) {
      setActionError(e?.message ?? "Failed to approve");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = (id: string) => {
    setSelectedId(id);
    setModalOpen(true);
  };

  const submitFeedback = async (feedback: string) => {
    setModalOpen(false);
    if (!selectedId) return;
    setBusy(true);
    setActionError(null);
    try {
      await reject(selectedId, feedback);
    } catch (e: any) {
      setActionError(e?.message ?? "Failed to reject");
    } finally {
      setBusy(false);
      setSelectedId(null);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold mb-4 text-white">Approval</h2>
      {(error || actionError) && (
        <p className="text-red-400">{actionError ?? error}</p>
      )}
      {busy && <p className="text-gray-400">Working…</p>}
      {loading && approval.length === 0 ? (
        <p className="text-gray-400">Loading…</p>
      ) : approval.length === 0 ? (
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
