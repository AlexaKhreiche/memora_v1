"""Patient-specific visibility timer; no startup alerts before identification."""
from agent.perception.vision.presence_detector import PresenceResult


class PatientPresence:
    def __init__(self, absence_threshold_s=8.0):
        self.threshold = absence_threshold_s
        self.last_seen = None

    def update(self, status, now):
        if status == 'patient_identified':
            self.last_seen = now
            return PresenceResult(True, False, 0.0, 0.0, [])
        if status not in ('patient_not_visible', 'identity_uncertain'):
            # Camera/model failures are not evidence of wandering. Require a fresh
            # identification before restarting the absence timer after an outage.
            self.last_seen = None
            return PresenceResult(False, False, 0.0, 0.0, [status])
        if self.last_seen is None:
            return PresenceResult(False, False, 0.0, 0.0, ['Waiting to identify patient'])
        elapsed = max(0.0, now - self.last_seen)
        active = elapsed >= self.threshold
        confidence = min(1.0, 0.7 + 0.3 * (elapsed - self.threshold) / 15) if active else 0.0
        return PresenceResult(False, active, confidence, elapsed,
                              [f'Enrolled patient not verified in view for {elapsed:.1f}s', status])
