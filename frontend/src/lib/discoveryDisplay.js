/**
 * Pure display-contract helpers for the discovery UI
 * (discovery-reliability spec, Step 5). No React, no side effects —
 * unit-testable in a bare node environment.
 */

/**
 * Signal display contract (spec Step 5, decision D15): the UI renders ONLY
 * signals the backend actually queried for that row, driven by
 * data_coverage.by_source — "real"/"empty" ⇒ render the section; "n/a" ⇒
 * collapse into one "not queried" line, never a zeroed metric card. Rows
 * without coverage data (old cache/catalog payloads) fall back to evidence
 * presence, so legacy rows that carry X data still show it (back-compat)
 * while new rows — where X is retired as a sentiment source — stop
 * rendering a dead X metric.
 * @returns {{visible: {amazon_reviews: boolean, twitter: boolean}, notQueried: string[]}}
 */
export function visibleSocialSections(product) {
  const bySource = product?.data_coverage?.by_source || null;
  const dataSources = product?.data_sources || {};
  const evidencePresent = {
    amazon_reviews:
      product?.amazon_evidence != null || dataSources.amazon_reviews != null,
    twitter: product?.twitter_evidence != null,
  };
  const labels = { amazon_reviews: 'Amazon reviews', twitter: 'X/Twitter' };
  const visible = {};
  const notQueried = [];
  for (const key of Object.keys(labels)) {
    if (bySource && key in bySource) {
      visible[key] = bySource[key] !== 'n/a';
      if (!visible[key]) notQueried.push(labels[key]);
    } else {
      // Legacy row: render only what carries data; make no "not queried"
      // claim — we don't actually know what that run queried.
      visible[key] = evidencePresent[key];
    }
  }
  return { visible, notQueried };
}
