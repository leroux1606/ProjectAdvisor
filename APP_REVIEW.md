# App Review

Date: 2026-03-27

## Review Scope

This review covers the current `Project Plan Scrutinizer` codebase with a focus on:

- correctness and functional behavior
- product and UX gaps
- security and reliability risks
- practical enhancement opportunities

Validation performed:

- ran the automated test suite: `61 passed`
- executed the pipeline locally against `ProjectAlpha.txt`
- reviewed the main runtime paths for UI, pipeline, auth, and payments

## Functionality Verified

- The app supports authentication with local SQLite-backed accounts.
- The analysis pipeline runs in deterministic mode without an OpenAI key.
- File ingestion supports `PDF`, `DOCX`, `TXT`, and `MD`.
- The sample file `ProjectAlpha.txt` was successfully analysed.
- The sample analysis produced:
  - overall score: `4.7`
  - grade: `D`
  - sections found: `10`
  - recommendations generated: `26`
- The rule-engine test suite currently passes in full.

## Findings

### 1. Deterministic mode is not fully deterministic

Severity: High

Files:

- `app/pipeline/orchestrator.py`
- `app/pipeline/section_extractor.py`

Issue:

- The UI toggle and orchestrator `enable_llm` flag only control the AI insights layer.
- Section extraction still falls back to the LLM whenever `OPENAI_API_KEY` exists, even if the user expects deterministic-only execution.

Why it matters:

- This breaks the product promise that the system can run in a fully rule-based mode.
- It also makes results harder to reason about because section extraction behavior changes based on environment, not explicit user intent.

Recommendation:

- Pass a single `enable_llm` or `allow_llm_fallback` flag through to `extract_sections()`.
- When deterministic mode is selected, disable all LLM usage, including extraction fallback.

### 2. Analysis quota is consumed before a successful run completes

Severity: High

Files:

- `app.py`
- `app/auth/service.py`

Issue:

- `consume_analysis(user)` is called before `run_pipeline(...)`.
- If ingestion, preprocessing, section extraction, or rule evaluation fails afterward, the user can lose a free analysis or paid credit without receiving a valid report.

Why it matters:

- This creates a billing and trust issue.
- It is especially problematic for paid credit users because failed runs can consume purchased value.

Recommendation:

- Move quota deduction to after a successful report is generated.
- If pre-consumption is required for concurrency reasons, add explicit rollback/refund behavior on failure.

### 3. Stripe webhook handling is not idempotent

Severity: High

Files:

- `app/payments/webhook.py`
- `app/auth/db.py`

Issue:

- Stripe webhooks can be delivered more than once.
- The current handlers insert transactions and add credits without checking whether the event or session has already been processed.

Why it matters:

- Duplicate `checkout.session.completed` deliveries could add credits multiple times.
- This can create incorrect balances, support overhead, and revenue leakage.

Recommendation:

- Store processed Stripe event IDs or enforce uniqueness on `stripe_session_id`.
- Ignore duplicate webhook deliveries after the first successful application.

### 4. Unescaped HTML rendering introduces injection risk

Severity: Medium

Files:

- `app.py`
- `app/components/dashboard_page.py`
- `app/components/findings_display.py`
- `app/components/top_issues.py`
- `app/components/recommendations_display.py`

Issue:

- The app uses `unsafe_allow_html=True` in many places while interpolating dynamic values such as:
  - `user.email`
  - rule finding text
  - AI insight text
  - recommendation content

Why it matters:

- Email validation is weak, so crafted input could be rendered as HTML.
- If AI insights are enabled later, model output is also rendered directly into HTML blocks.
- Even in a local app, this is an avoidable security and robustness risk.

Recommendation:

- Escape dynamic strings before inserting them into HTML.
- Prefer native Streamlit components for user-visible text where possible.
- Tighten email validation to reject malformed values beyond a basic `@` check.

### 5. Documentation does not match the current implementation

Severity: Medium

Files:

- `README.md`

Issue:

- The README still describes the system as requiring an OpenAI key and describes the section extractor as LLM-based.
- That no longer reflects the current hybrid architecture and deterministic-first behavior.

Why it matters:

- New users may think the app cannot run without an API key.
- The docs currently understate the rule-engine design and overstate LLM dependence.

Recommendation:

- Update the README to describe deterministic-first execution, optional AI insights, current auth/payment behavior, and the actual run instructions.

### 6. Test coverage is strong for rules, but thin for app flows

Severity: Medium

Files:

- `tests/test_rule_engine.py`

Issue:

- The existing tests are focused on the rule engine and pipeline behavior.
- There is little or no automated coverage for:
  - auth registration and login
  - credit consumption behavior
  - Streamlit page flow
  - Stripe webhook fulfillment

Why it matters:

- The most failure-prone business logic now sits in auth and payments, not only the rule engine.
- Regressions in billing and access control may go unnoticed.

Recommendation:

- Add targeted tests for auth service, webhook handling, and credit accounting.
- Add at least one end-to-end happy-path test for account creation and analysis access.

## Proposed Enhancements

### Product and UX

- Add a visible "deterministic mode" badge on the main page, not only in the sidebar.
- Show remaining free analyses and credit balance directly above the Analyse button.
- Add a downloadable report export option such as `Markdown` or `PDF`.
- Show a clear message when a payment success page is reached but entitlement is still waiting for webhook confirmation.
- Add sample project plans in the UI for quick first-run testing.

### Reliability

- Make usage deduction transactional and failure-safe.
- Add structured application logging around upload failures, parsing failures, and webhook outcomes.
- Add webhook idempotency protection and reconciliation tooling.
- Introduce a small service layer around payments so pricing, fulfillment, and transaction logging are easier to test independently.

### Security

- Escape all dynamic content rendered via `unsafe_allow_html=True`.
- Strengthen registration validation for email format and password rules.
- Consider session hardening if this moves beyond local/demo use.
- Keep secrets out of local files in deployed environments and rely on environment injection.

### Performance

- Cache expensive parsing or section extraction results for repeated reruns of the same uploaded content.
- Consider hashing uploaded file bytes and memoizing preprocessing + extraction.
- If large plans become common, move analysis execution off the Streamlit request path into a background job model.
- Add file size limits and early validation to avoid expensive parsing on unexpectedly large uploads.

## Overall Assessment

The application is in a solid state for a local prototype:

- the core deterministic analysis pipeline works
- the rule-engine tests are passing
- file ingestion and report generation are functional

The biggest gaps are not in the rules themselves but in operational behavior around:

- deterministic-mode guarantees
- usage charging
- payment fulfillment safety
- safe HTML rendering

If those areas are tightened, the app will be much closer to a reliable production-grade audit tool.

## Browser and UI Review Addendum

### Live browser test status

Stripe status during this review:

- Stripe was not configured and was not included in runtime validation.

Browser automation status:

- I attempted a live browser interaction against `http://localhost:3000`.
- The application server was confirmed running locally on port `3000`.
- However, browser automation tools were not available in this execution environment, so I could not truthfully complete a click-by-click browser session or capture live DOM behavior.

What was runtime-verified:

- the Streamlit app process was live on `localhost:3000`
- the analysis pipeline executed successfully against `ProjectAlpha.txt`
- local tests passed

What remains not directly browser-verified in this review:

- actual keyboard tab order
- visible focus state behavior in the browser
- screen reader announcements
- exact rendered spacing, alignment, and responsive behavior at multiple viewport sizes
- final drag-and-drop upload affordance behavior in-browser

### Look and feel assessment

Overall visual direction:

- The app has a reasonably modern dark theme with consistent card styling, rounded controls, and clear report grouping.
- The general direction feels more modern than default Streamlit, but it does not yet feel fully polished or enterprise-grade.

Strengths:

- Consistent dark palette across auth, dashboard, pricing, and report surfaces.
- Good use of grouped sections, cards, and expanders for report readability.
- Typography hierarchy is present and easy to follow.
- The main workflow is simple: authenticate, submit plan, review findings.

Weaknesses:

- The UI relies heavily on custom HTML injection rather than a cohesive design system.
- Emoji-heavy labels such as `🔍`, `📁`, `📝`, `⚠️`, and `🏛` make the product feel less formal than a professional audit platform.
- Secondary text colors are too low contrast in several places, which makes the design feel visually muted and hurts readability.
- The product lacks trust signals expected in a professional tool, such as privacy, security, retention, and compliance messaging.
- Some screens are visually dense and could use clearer spacing, stronger section dividers, and more restrained use of grey helper text.

Professionalism verdict:

- Moderately modern: yes.
- Fully professional / enterprise-ready: not yet.

Recommended look-and-feel improvements:

- Reduce decorative emoji use in primary navigation and headings.
- Standardize spacing, typography scale, and card patterns into a small UI system.
- Increase contrast for helper text and button text.
- Add a simple footer with product, privacy, and support links.
- Add a more explicit empty-state and onboarding experience for first-time users.

## Accessibility and Compliance Review

Important note:

- This is a product and engineering accessibility review, not a legal certification.
- The app should not currently be described as compliant with WCAG 2.1 AA, WCAG 2.2 AA, Section 508, EN 301 549, ADA, or GDPR.

### Standards baseline used

References used in this review:

- W3C WCAG 2.2 guidance for contrast and labels/instructions
- GDPR privacy notice guidance for data collection transparency

### Accessibility findings

#### 1. Contrast failures in multiple text combinations

Severity: High

Observed color contrast calculations:

- `#e2e8f0` on `#0f172a`: `14.48:1` - passes
- `#94a3b8` on `#0f172a`: `6.96:1` - passes normal text AA
- `#64748b` on `#0f172a`: `3.75:1` - fails normal text AA
- `#64748b` on `#1e293b`: `3.07:1` - fails normal text AA
- `#ffffff` on `#3b82f6`: `3.68:1` - fails normal text AA for standard-size button text

Why it matters:

- Several subtitles, helper texts, and button labels are below WCAG minimum contrast for normal-sized text.
- This affects readability for users with low vision and is a direct accessibility blocker for AA conformance.

#### 2. Analyzer inputs hide visible labels

Severity: High

Files:

- `app.py`

Observed implementation:

- The main text area uses `label_visibility="collapsed"`.
- The file uploader also uses `label_visibility="collapsed"`.

Why it matters:

- WCAG requires labels or instructions for user inputs.
- The current analyzer depends mainly on tab context and placeholder text instead of visible field labels next to the controls.
- Placeholder text is not a durable substitute for visible instructions because it disappears during interaction and is less robust for many users.

Recommendation:

- Show visible labels for both the pasted-text field and the upload control.
- Keep instructional helper text visible outside the input itself.

#### 3. Focus visibility is not explicitly designed

Severity: Medium

Issue:

- The custom CSS defines hover states but does not define clear custom focus states for buttons, tabs, text areas, or upload controls.
- Default browser or Streamlit focus states may still exist, but the current code does not intentionally preserve or enhance them.

Why it matters:

- WCAG 2.2 adds stronger expectations around focus visibility and non-obscured focus.
- Keyboard users need a clearly visible focus indicator at all times.

Recommendation:

- Add explicit `:focus-visible` styles with a high-contrast outline or ring for all interactive elements.
- Test keyboard-only navigation end to end.

#### 4. Error prevention and field guidance are only partially addressed

Severity: Medium

Strengths:

- Auth inputs now include visible labels and placeholder guidance.
- Error messages for empty auth fields and missing analysis input are clear.

Gaps:

- The analyzer form does not clearly communicate preferred file structure, size expectations, or what happens after upload.
- Password requirements are minimal and not explained beyond length.

Recommendation:

- Add persistent helper text for accepted file types, expected plan content, and analysis limits.
- Add inline validation cues before submission where possible.

#### 5. Heavy reliance on color and visual styling

Severity: Medium

Issue:

- Severity, state, and hierarchy are often conveyed using color, colored badges, and subtle visual emphasis.
- This may be adequate visually, but it needs confirmation that meaning is not color-dependent alone.

Recommendation:

- Ensure severity is always expressed with text, not just color.
- Confirm that status components are announced correctly by assistive technology.

### Compliance mapping

#### WCAG 2.1 Level A and AA

Current status:

- Not compliant based on identified issues.

Most relevant gaps:

- contrast failures for normal text
- hidden analyzer labels
- incomplete focus-state assurance
- no evidence yet of tested keyboard or screen-reader behavior

#### WCAG 2.2

Current status:

- Not compliant or at minimum not yet supportable as compliant.

Most relevant added concern:

- focus visibility and focus-not-obscured requirements need explicit validation

#### Section 508

Current status:

- Not supportable as compliant at this stage.

Reason:

- Section 508 web conformance is generally evaluated through WCAG-aligned accessibility requirements, and the current app has unresolved WCAG-level issues.

#### EN 301 549

Current status:

- Not supportable as compliant at this stage.

Reason:

- The same core accessibility gaps would prevent a strong EN 301 549 conformance claim for the web interface.

#### ADA compliance mapping

Current status:

- The app should not currently be described as ADA compliant.

Reason:

- In practice, ADA risk evaluation for web apps commonly maps to WCAG conformance expectations.
- Since WCAG issues are still present, ADA readiness is also incomplete.

### GDPR review

Current status:

- Not GDPR-ready based on the current product surface and documentation.

Observed gaps:

- no visible privacy notice at account signup
- no visible explanation of what personal data is collected and why
- no stated retention policy for account, transaction, or uploaded plan data
- no visible mechanism for data export, rectification, or erasure requests
- no visible explanation of payment processor data sharing with Stripe
- no visible contact path for privacy or data rights requests

Why it matters:

- The app collects personal data through accounts and stores transaction history.
- It also processes uploaded project plans, which may contain personal or sensitive business data.
- GDPR requires transparent disclosure at the point of collection and clear handling of data-subject rights.

Recommendation:

- Add a privacy notice link and summary at signup.
- Document lawful basis, retention, processors, deletion rules, and user rights.
- Add operational workflows for delete-account, export-my-data, and data-access requests.

## Priority next steps

1. Fix contrast failures, especially button text and secondary text.
2. Restore visible labels and helper text for the analyzer input controls.
3. Add explicit keyboard focus styles and test with keyboard-only navigation.
4. Remove or escape unsafe HTML rendering of dynamic content.
5. Add privacy notice, retention disclosure, and user data-rights workflows before making any GDPR or enterprise compliance claims.
