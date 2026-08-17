# Ledger UX validation

These are the three pre-release experiments for the UX refresh. Results are intentionally left pending until they are run with participants or the specified devices.

| Experiment | Hypothesis | Method and evidence | Owner | Decision date | Success threshold | Failure response |
|---|---|---|---|---|---|---|
| Five-second comprehension test | A new visitor can state that Ledger splits group expenses and calculates repayments. | Show the landing page for five seconds to five people, then record their unaided summaries. | Implementer | Before merge | At least four summaries identify both expense splitting and repayment calculation. | Revise the landing-page copy and repeat the test. |
| First-group task test | A newly registered user can create a group and explain the next step without assistance. | Observe three people in fresh sessions; record completion and confusion notes. | Implementer | Before production deployment | At least two people complete the task unaided and can explain that they should invite a username or add an expense. | Revise onboarding or the empty dashboard and repeat the test. |
| Responsive clarity test | Login, sign-up, group detail, expense entry, popovers, and the welcome modal remain usable at 375px and desktop widths. | Complete the flows with keyboard and a touch-sized viewport; save screenshots and an interaction checklist. | Implementer | Before production deployment | No clipped content, hidden action, keyboard trap, or horizontal scrolling. | Block rollout until the affected layout or interaction is fixed. |
