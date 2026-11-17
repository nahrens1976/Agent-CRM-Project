import unittest

from app import evaluate_scenario, guardrail_decision


class GuardrailTests(unittest.TestCase):
    context = {"contact": {"name": "Casey", "company": "Example Co", "owner": "Morgan"}}

    def test_draft_is_allowed_but_no_send_is_permitted(self):
        decision = guardrail_decision("create_draft", self.context)
        self.assertTrue(decision["allowed"])
        scenario = {"slug": "reengage-dormant-contact", "input_context": {"contact_owner": "Morgan"}}
        output, checks, _ = evaluate_scenario(scenario)
        self.assertFalse(output["message_sent"])
        self.assertTrue(all(check[1] for check in checks))

    def test_unapproved_external_actions_are_blocked(self):
        for action in ("send_email", "create_external_record", "delete_crm_data"):
            with self.subTest(action=action):
                decision = guardrail_decision(action, self.context)
                self.assertFalse(decision["allowed"])
                self.assertEqual(decision["guardrail"], action)

    def test_missing_contact_company_or_owner_is_not_invented(self):
        for field in ("name", "company", "owner"):
            with self.subTest(field=field):
                context = {"contact": dict(self.context["contact"])}
                context["contact"][field] = None
                decision = guardrail_decision("create_draft", context)
                self.assertFalse(decision["allowed"])
                self.assertIn({"name": "contact", "company": "company", "owner": "owner"}[field], decision["missing"])

    def test_ambiguous_decision_and_deadline_stay_blank(self):
        for slug, blank_field in (("guardrail-ambiguous-decision", "decision"), ("guardrail-ambiguous-deadline", "deadline")):
            with self.subTest(slug=slug):
                output, checks, _ = evaluate_scenario({"slug": slug, "input_context": {}})
                self.assertEqual(output["blank_field"], blank_field)
                self.assertTrue(all(check[1] for check in checks))


if __name__ == "__main__":
    unittest.main()

