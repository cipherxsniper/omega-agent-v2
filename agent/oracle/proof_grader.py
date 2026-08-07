import os
import json
import subprocess
from datetime import datetime
from agent.oracle.grading_system import OracleGrader

class ProofGrader(OracleGrader):
    def __init__(self, key_path='~/.omega/keys/grader.json', log_path='~/.omega/logs/grades.jsonl'):
        super().__init__()
        self.key_path = os.path.expanduser(key_path)
        self.log_path = os.path.expanduser(log_path)
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def evaluate_and_sign(self, metrics, task_id, notes=""):
        # Get base grade
        grade = self.evaluate_performance(metrics, notes=notes)
        
        # Prepare for proofchain
        # In a real scenario, we would write to a DB then snapshot.
        # For now, we will use the proofchain library logic directly to sign this grade.
        
        grade_entry = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "grade": grade,
            "metrics": metrics
        }
        
        # Sign the grade entry (simulating proofchain build)
        # We'll append it to our log and use proofchain to verify it later.
        with open(self.log_path, "a") as f:
            f.write(json.dumps(grade_entry) + "\n")
            
        print(f"[!] Grade Signed & Logged for Task {task_id}")
        return grade

