# Multi-Touch Sequence Play: Podcast → Blog → Demo (14-Day Path)

> Leads who follow a podcast → blog → demo-request path within 14 days close at 39% — nearly 5× the 8.2% dataset-wide rate across 46 observed leads.

*Sequence Play — generated from Finding F3 by `claude-sonnet-4-6` on 2026-05-25T14:03:14+00:00.*

This 46-lead cohort converts at 39% versus the 8.2% baseline, making it the highest-signal journey pattern in the dataset. Buyer language from this segment clusters around three distinct pain themes: attribution opacity, manual lead routing backlogs, and forecast hygiene failures. A sequenced play that mirrors the content journey these buyers already self-selected into — and speaks directly to those three pain themes — should accelerate the path to demo and protect the close rate. The sequence must be deployable this week with existing content and channel access.

## Sequence Architecture Overview

5-touch, 14-day sequence triggered when a contact completes: (1) a tracked podcast listen or referral click AND (2) a blog page visit — both within a 14-day rolling window. Enrollment fires before or at the moment of demo request to warm the AE hand-off. If demo request fires first, enroll immediately and compress to touches 3–5 only.

## Trigger & Enrollment Criteria (RevOps Setup)

- Trigger source A: UTM-tagged podcast link click (episode landing page or show-notes CTA) recorded in CRM/MAP within last 14 days.
- Trigger source B: Blog page visit tracked via pixel or known-visitor session within the same 14-day window.
- Both conditions must be TRUE within the 14-day window to enroll. Use an AND logic smart list or workflow branch.
- Exclude: contacts already in an active deal stage of 'Proposal' or later, and any contact who has already received this sequence.
- Estimated addressable volume based on finding: ~46 leads per measurement period — confirm cadence with your MAP's historical session data before setting send caps.

## Touch 1 — Day 0: Enrollment Email (Automated, Marketing Sender)

- Trigger: fires within 1 hour of second qualifying touch being met.
- Subject line option A: 'The episode that sent you here — a few things worth seeing'
- Subject line option B: 'You went from the podcast to the blog. Here's what's next.'
- Body angle: Acknowledge the journey explicitly. Reference that listeners who dig into the blog are usually wrestling with a specific operational problem, not just browsing. Name the three pain clusters without being presumptuous — attribution visibility, routing/ops backlog, forecast hygiene.
- CTA: Single link to a 'Which problem fits you?' landing page or a segmented blog hub (three tiles, one per pain theme). Do NOT push demo here — they haven't asked yet.
- If demo request already submitted: skip to Touch 3.

## Touch 2 — Day 3: Pain-Specific Follow-Up Email (Automated, Branch Logic)

- Branch on which blog post(s) the contact visited (use page URL or topic tag).
- Branch A — Attribution content visited: Subject: 'When marketing reports numbers ops can't reconcile' | Body: Lead with the attribution opacity problem. Offer a one-pager or short video showing how campaign-to-close attribution is surfaced in the product.
- Branch B — Routing/Ops content visited: Subject: 'Monday morning lead routing — there's a version that doesn't involve a spreadsheet' | Body: Speak to the manual ops backlog. Link to a workflow automation walkthrough or a relevant help doc / demo clip.
- Branch C — Forecast content visited: Subject: 'Deals in three forecast categories at once is a data model problem, not a rep problem' | Body: Address forecast hygiene directly. Link to a forecast accuracy use-case page or a recorded walkthrough.
- Branch D — No clear blog signal / multiple pages: Use Branch A as default (attribution is the broadest pain in the cohort language).
- CTA in all branches: 'See a 12-minute walkthrough' (ungated video or interactive demo) — still not a hard demo push.

## Touch 3 — Day 6: AE LinkedIn Touch (Manual, AE-Executed)

- AE receives a daily CRM task/view filtered to: 'Enrolled in Podcast-Blog sequence AND Day 6 AND no demo booked'.
- Message frame: Reference the podcast and the specific blog topic if visible in CRM. Keep to 3 sentences max. Ask one diagnostic question tied to their likely pain branch (e.g., 'Are you currently reconciling attribution in your CRM or pulling it out separately?').
- Do not paste a calendar link in the first message. Goal is a reply, not a booking.
- RevOps action: Create the CRM task view/queue this week so AEs are not hunting for contacts manually.

## Touch 4 — Day 9: Demo Invitation Email (Automated, AE Sender Name)

- Only sends if: no demo booked AND no reply to Touch 3 LinkedIn.
- Subject: 'Worth 25 minutes to see if this fits your stack?'
- Body: Short. Recap the pain theme from their branch. State explicitly what the demo covers (not a generic product tour — frame it as a working session on their specific problem area).
- CTA: Direct calendar booking link (Chili Piper, Calendly, or equivalent). This is the first hard demo CTA in the sequence.
- Include one social proof data point IF available from your own closed-won data — do not fabricate one.

## Touch 5 — Day 13: Break-Up / Last-Mile Email (Automated, AE Sender Name)

- Only sends if: no demo booked AND no reply across all prior touches.
- Subject: 'Closing the loop — still worth a conversation?'
- Body: Acknowledge they've been through a lot of content. Give them an easy out AND an easy yes. Two-option CTA: (A) Book 25 min, (B) 'Not the right time — remove me from follow-up' (honor this immediately via unsubscribe/suppression tag).
- After Touch 5 with no response: move to a low-frequency nurture track, do not re-enroll in this sequence for 90 days.

## AE Hand-Off Brief (Template — Attach to Demo Confirmation)

- Field 1 — Journey: 'This contact came in via podcast → blog within 14 days. Cohort close rate: 39%.'
- Field 2 — Pain branch: [Auto-populated from Branch A/B/C/D tag in CRM]
- Field 3 — Suggested opening question by branch:
-   Branch A: 'How are you currently connecting campaign spend to closed revenue — is that a report you can pull today?'
-   Branch B: 'Walk me through how leads get assigned to your team right now — is that automated or does someone own that process?'
-   Branch C: 'When you look at your forecast this week, how many deals would you say are in the right stage versus where they actually are?'
- Field 4 — Do not: pitch the full platform in the first 10 minutes. This buyer self-educated. Start with their problem, not your features.

## Measurement & Iteration (RevOps Ownership)

- Primary metric: Demo-booked rate from sequence enrollment (target: exceed the implied ~39% close-rate cohort behavior — track weekly).
- Secondary metrics: Reply rate by touch number (identifies where sequence loses momentum), branch conversion rate (which pain theme books fastest).
- Report out at Day 30 and Day 60 with: enrollments, demo books, deals created, deals closed from this sequence cohort.
- Iteration trigger: If Touch 2 open rate falls below 25% or click rate below 8%, A/B test subject lines before changing body copy.
- Attribution tagging: Tag all sequence emails with UTM source = 'podcast-blog-sequence' and a touch number parameter so downstream attribution can be reconciled — directly addressing the attribution opacity pain the buyers themselves named.
