"""Enroll a local patient reference. Called by the caregiver upload route."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.runtime.patient_identity import enroll

if __name__ == '__main__':
    try:
        enroll(sys.argv[1], sys.argv[2])
    except Exception:
        print('Enrollment failed: use one clear face and check model availability.', file=sys.stderr)
        raise SystemExit(1)
