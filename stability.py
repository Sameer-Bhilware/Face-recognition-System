from collections import deque, Counter


class RecognitionStabilizer:

    def __init__(self, buffer_size=10, min_votes_to_confirm=5):
        self.buffer_size          = buffer_size
        self.min_votes_to_confirm = min_votes_to_confirm
        self._buffers: dict[int, deque] = {}

    def update(self, face_id: int, name: str, confidence: float):
        if face_id not in self._buffers:
            self._buffers[face_id] = deque(maxlen=self.buffer_size)
        self._buffers[face_id].append((name, confidence))

    def is_ready(self, face_id: int) -> bool:
        """
        Returns True only when the buffer has collected enough frames
        to make a reliable decision. Use this to gate unknown face logging —
        prevents logging a registered person who hasn't been confirmed yet.
        """
        return (
            face_id in self._buffers and
            len(self._buffers[face_id]) >= self.min_votes_to_confirm
        )

    def get_stable_result(self, face_id: int):
        if face_id not in self._buffers or len(self._buffers[face_id]) == 0:
            return "UNKNOWN", 0.0

        buffer     = self._buffers[face_id]
        name_votes = Counter(name for name, _ in buffer)
        top_name, top_count = name_votes.most_common(1)[0]

        if top_count < self.min_votes_to_confirm:
            return "UNKNOWN", 0.0

        avg_confidence = sum(
            conf for name, conf in buffer if name == top_name
        ) / top_count

        return top_name, avg_confidence

    def remove_face(self, face_id: int):
        self._buffers.pop(face_id, None)

    def cleanup_stale_faces(self, active_ids: set):
        stale = [fid for fid in self._buffers if fid not in active_ids]
        for fid in stale:
            del self._buffers[fid]

    def reset(self):
        self._buffers.clear()