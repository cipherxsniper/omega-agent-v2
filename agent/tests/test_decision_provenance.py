import unittest

from agent.decision_provenance import build_decision_provenance


class DecisionProvenanceTests(unittest.TestCase):
    def test_records_observable_choice_and_parent(self):
        first = build_decision_provenance(
            action="read_file",
            arguments={"path": "src/app.py"},
            step=1,
            available_alternatives=["read_file", "write_file", "run_bash"],
            parent_id=None,
            observed_context=[]
        )
        second = build_decision_provenance(
            action="compile_code",
            arguments={"path": "src/app.py"},
            step=2,
            available_alternatives=["read_file", "write_file", "compile_code"],
            parent_id=first["decision_id"],
            observed_context=[first]
        )
        self.assertEqual(first["causal_parent_id"], None)
        self.assertEqual(second["causal_parent_id"], first["decision_id"])
        self.assertIn("write_file", first["available_alternatives"])
        self.assertEqual(first["selection_basis"], "The model emitted this tool call after the observable transcript context.")
        self.assertEqual(len(first["context_hash"]), 24)
        self.assertNotEqual(first["decision_id"], second["decision_id"])

    def test_context_hash_is_stable_for_same_observable_context(self):
        args = {"path": "src/app.py"}
        first = build_decision_provenance(
            action="read_file", arguments=args, step=1,
            available_alternatives=["read_file"], parent_id=None,
            observed_context=[{"role": "user", "content": "inspect"}]
        )
        second = build_decision_provenance(
            action="read_file", arguments=args, step=1,
            available_alternatives=["read_file"], parent_id=None,
            observed_context=[{"role": "user", "content": "inspect"}]
        )
        self.assertEqual(first["context_hash"], second["context_hash"])
        self.assertEqual(first["arguments_hash"], second["arguments_hash"])


if __name__ == "__main__":
    unittest.main()
