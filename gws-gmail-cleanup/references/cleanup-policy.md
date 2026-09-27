# Cleanup Policy Guide

Ask the user to define keep/remove rules before auditing. Do not assume all old or promotional mail is disposable.

## Recommended Keep Prompts

- Which labels should always be protected?
- Should Sent, Starred, Important, and custom keep labels be protected?
- Should PDFs and MP3s always be kept?
- Which senders or domains should never be touched?
- Which terms indicate personal or sensitive mail for this user?
- Is the first destructive action Trash or permanent delete?

## Common Protection Categories

Suggest these as defaults, then let the user edit them:

- Medical: doctor, dental, dentist, health, healthcare, pharmacy, prescription, patient, clinic, hospital, therapy.
- Financial: bank, statement, mortgage, loan, tax, IRS, W-2, W-9, 1099, payroll, invoice, receipt, payment, PayPal, Venmo, Stripe, refund.
- Legal and identity: legal, attorney, court, SSN, passport, DMV, driver license.
- Work and housing: employment, onboarding, offer letter, background check, contract, agreement, DocuSign, HelloSign, EchoSign, lease, rent, landlord.
- Account/security: password, login, verification, confirm, confirmation, security, account.
- User-preserved content: PDFs, MP3s, Sent, Starred, Important, and custom keep labels.

## Recommended Phases

1. Baseline: record Gmail/Google storage and Trash state.
2. Audit: generate JSON reports grouped by bucket, domain, year, label, and estimated size.
3. Review: present candidates and held/protected messages.
4. Trash: move approved messages to Trash by default.
5. Permanent delete: run only after explicit second approval, or immediately only when the user explicitly asks to skip Trash.
