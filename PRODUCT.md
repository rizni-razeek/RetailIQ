# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Flask-rendered HTML templates, CSS, and vanilla JavaScript with no frontend
framework or build system.

## Users

Small and medium retail business owners and staff who need to turn their own POS
sales history into practical demand and stock decisions.

## Product Purpose

RetailIQ provides tenant-isolated historical sales uploads, category-level demand
forecasts, inventory comparison, stock intelligence, anomaly analysis, and
analytics through a lightweight web application.

## Positioning

RetailIQ combines a business's own category-level sales history with a trained
forecasting pipeline, current inventory entered separately, and explicit
prototype decision rules in one operational workflow.

## Operating Context

Users register a business account, upload POS CSV history, generate recursive
7-, 14-, or 30-day forecasts, record current category stock, and review stock and
historical anomaly results. Business identity is always derived server-side from
the authenticated user.

## Capabilities and Constraints

- Authentication uses the existing JWT REST API.
- The frontend is served by the existing Flask application.
- Historical uploads require category-level date, family, and sales data.
- Future promotion is assumed to be zero during forecasting.
- Stock quantities must use units compatible with the uploaded sales data.
- Forecast accuracy for fixed-origin 7-, 14-, and 30-day horizons has not been
  separately validated.
- Anomalies indicate unusual residuals, not causes or business incidents.
- The stock multiplier and anomaly threshold are configurable prototype rules.

## Brand Commitments

RetailIQ should feel intelligent, editorial, calm, modern, and data-confident.
`docs/design/RetailIQ_DesignSystem.html` is the authoritative visual source for
tokens, typography, components, spacing, responsive application structure, and
light/dark themes.

## Evidence on Hand

The repository contains verified backend APIs and automated tests. It does not
contain customer testimonials, operational accuracy claims, production usage
metrics, or other marketing proof; future interfaces must not fabricate them.

## Product Principles

- Show only business-owned data derived from the authenticated account.
- Prefer clear operational states and actions over promotional language.
- State model assumptions and prototype rules honestly.
- Keep the interface lightweight and usable for routine retail work.
- Never substitute fictional dashboard data for unavailable information.

## Accessibility & Inclusion

Use semantic HTML, connected form labels, visible keyboard focus, understandable
errors, sufficient contrast, and layouts that remain usable at tablet and mobile
widths.
