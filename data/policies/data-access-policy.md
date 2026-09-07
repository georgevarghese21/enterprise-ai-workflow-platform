# NovaTech Data & Resource Access Policy

## Purpose

This policy governs how NovaTech employees and contractors request and are
granted access to internal resources, including databases, code
repositories, cloud accounts, and internal tools. It exists to protect
customer data and company IP while keeping day-to-day access requests fast
for low-risk cases.

## Sensitivity tiers

Every resource at NovaTech is classified into one of three sensitivity
tiers, and the approval path for an access request depends entirely on the
tier of the resource being requested:

- **LOW** — Internal, non-customer data such as analytics dashboards,
  internal wikis, and read-only reporting tools. No customer PII is
  present.
- **MEDIUM** — Resources that contain aggregated or de-identified customer
  data, staging environments, or internal source code repositories that are
  not customer-facing production systems.
- **HIGH** — Production systems, resources containing raw customer PII or
  payment data, and cloud accounts with the ability to modify production
  infrastructure.

## Approval requirements by tier

- **LOW sensitivity**: Auto-approved. The requesting employee's manager is
  notified but does not need to act. Access is provisioned immediately.
- **MEDIUM sensitivity**: Requires approval from the requesting employee's
  direct manager. Approval must be recorded before access is provisioned.
  Access is time-boxed to 90 days by default and must be renewed.
- **HIGH sensitivity**: Requires approval from both the requesting
  employee's manager and the Security department. Access is time-boxed to
  30 days by default. All HIGH sensitivity access, once granted, is logged
  and subject to quarterly access review.

## Contractors

Contractors follow the same tiering rules as full-time employees, with one
difference: contractors may never be granted standing access to HIGH
sensitivity production databases. A contractor who needs temporary access
to a HIGH sensitivity resource must have the access explicitly time-boxed
to no more than 5 business days and co-approved by Security.

## Revocation

Access to any resource is automatically revoked when an employee changes
departments, and must be re-requested under the new department's context.
All access, regardless of tier, is revoked immediately upon offboarding.

## Emergency access

In a production incident, an on-call engineer may request emergency
break-glass access to a HIGH sensitivity resource. Emergency access is
granted immediately without waiting for approval, but a Security approver
must be notified in real time and the access is automatically revoked
after 4 hours unless explicitly extended.
