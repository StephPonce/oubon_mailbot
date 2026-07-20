/**
 * Fail-if-reverted pins for the signal display contract
 * (discovery-reliability spec, Step 5 / decision D15).
 *
 * The spec's exact pin: a product whose data_coverage.by_source.twitter ===
 * "n/a" renders NO Twitter metric; one that actually carries
 * twitter_evidence still does (old rows, back-compat).
 */

import { describe, expect, it } from 'vitest';

import { visibleSocialSections } from './discoveryDisplay';

describe('visibleSocialSections (spec Step 5 / D15)', () => {
  it('by_source.twitter === "n/a" renders NO Twitter metric (the fail-if-reverted pin)', () => {
    const product = {
      data_coverage: {
        by_source: { twitter: 'n/a', amazon_reviews: 'real', reddit: 'n/a' },
      },
      amazon_evidence: { found_matches: true },
      twitter_evidence: null,
    };
    const { visible, notQueried } = visibleSocialSections(product);
    expect(visible.twitter).toBe(false);
    expect(visible.amazon_reviews).toBe(true);
    expect(notQueried).toContain('X/Twitter');
  });

  it('a row that actually carries X data still renders it (old rows, back-compat)', () => {
    // Legacy row: no data_coverage at all, but real twitter evidence.
    const legacy = {
      twitter_evidence: { found_real_tweets: true, sample_tweets: ['t1'] },
    };
    const { visible, notQueried } = visibleSocialSections(legacy);
    expect(visible.twitter).toBe(true);
    // Legacy rows make no "not queried" claims — we don't know what ran.
    expect(notQueried).toEqual([]);
  });

  it('queried-but-empty ("empty") still renders — searched-and-found-nothing is information', () => {
    const product = {
      data_coverage: { by_source: { twitter: 'empty', amazon_reviews: 'empty' } },
    };
    const { visible } = visibleSocialSections(product);
    expect(visible.twitter).toBe(true);
    expect(visible.amazon_reviews).toBe(true);
  });

  it('amazon n/a collapses into the not-queried line, never a zeroed card', () => {
    const product = {
      data_coverage: { by_source: { amazon_reviews: 'n/a', twitter: 'real' } },
      twitter_evidence: { found_real_tweets: false },
    };
    const { visible, notQueried } = visibleSocialSections(product);
    expect(visible.amazon_reviews).toBe(false);
    expect(notQueried).toContain('Amazon reviews');
  });

  it('legacy row with no evidence renders neither section and claims nothing', () => {
    const { visible, notQueried } = visibleSocialSections({});
    expect(visible.twitter).toBe(false);
    expect(visible.amazon_reviews).toBe(false);
    expect(notQueried).toEqual([]);
  });
});
