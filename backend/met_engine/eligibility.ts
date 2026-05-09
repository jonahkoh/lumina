/**
 * MET Engine — Subsidy Computation (pure)
 *
 * Reads data/aic-subsidy-rules.json. Verified against MOH/AIC sites.
 *
 *   finalCost = max(0, baseCost × (1 - rate) - rebate)
 */

import {
  Citizenship,
  TransportMode,
  ServiceTier,
  SubsidyComputation,
} from './types';
import rules from './data/aic-subsidy-rules.json' with { type: 'json' };

export function computeSubsidy(params: {
  citizenship: Citizenship;
  monthlyIncomeSGD: number;
  transportMode: TransportMode;
}): SubsidyComputation {
  const serviceTier = mapTransportModeToServiceTier(params.transportMode);
  const baseSubsidyRate = lookupBaseSubsidyRate(
    params.citizenship,
    params.monthlyIncomeSGD
  );
  const rebate = lookupInterimRebate(
    params.citizenship,
    params.monthlyIncomeSGD,
    serviceTier
  );

  return {
    citizenship: params.citizenship,
    monthlyIncomeSGD: params.monthlyIncomeSGD,
    serviceTier,
    baseSubsidyRate,
    interimRebateSGD: rebate.amountSGD,
    interimRebateValid: rebate.valid,
    interimRebateExclusionReason: rebate.exclusionReason,
    computedAt: new Date().toISOString(),
  };
}

export function applySubsidy(
  baseCostSGD: number,
  subsidy: SubsidyComputation
): number {
  const afterBase = baseCostSGD * (1 - subsidy.baseSubsidyRate);
  const rebate = subsidy.interimRebateValid ? subsidy.interimRebateSGD : 0;
  return Math.max(0, afterBase - rebate);
}

// =============================================================================
// INTERNALS
// =============================================================================

function mapTransportModeToServiceTier(mode: TransportMode): ServiceTier {
  switch (mode) {
    case 'driver_only':
      return 'transport_only';
    case 'escort_only':
    case 'both':
      return 'basic_escort_transport';
  }
}

interface SubsidyTier {
  pchiMaxSGD: number | null;
  subsidyRate: number;
}

function lookupBaseSubsidyRate(citizenship: Citizenship, pchi: number): number {
  if (citizenship === 'foreigner') return 0;

  // Zero-income → AV-based fallback (defaults to top tier; AV check is upstream).
  if (pchi === 0) {
    return citizenship === 'sg_citizen'
      ? rules.baseSubsidy.noIncomeFallback.sgCitizenRate
      : rules.baseSubsidy.noIncomeFallback.sgPRRate;
  }

  const tiers: SubsidyTier[] =
    citizenship === 'sg_citizen'
      ? rules.baseSubsidy.tiers.sg_citizen
      : rules.baseSubsidy.tiers.sg_pr;

  for (const tier of tiers) {
    if (tier.pchiMaxSGD === null || pchi <= tier.pchiMaxSGD) {
      return tier.subsidyRate;
    }
  }
  return 0;
}

interface RebateTier {
  pchiMaxSGD: number | null;
  rebateSGD: number;
}

interface RebateLookup {
  amountSGD: number;
  valid: boolean;
  exclusionReason?: string;
}

function lookupInterimRebate(
  citizenship: Citizenship,
  pchi: number,
  serviceTier: ServiceTier
): RebateLookup {
  if (citizenship !== 'sg_citizen') {
    return {
      amountSGD: 0,
      valid: false,
      exclusionReason: 'Interim rebate is for Singapore citizens only',
    };
  }

  const now = new Date();
  const startsAt = new Date(rules.interimRebates.effectiveFrom);
  const expiresAt = new Date(rules.interimRebates.expiresAt);

  if (now < startsAt) {
    return {
      amountSGD: 0,
      valid: false,
      exclusionReason: `Rebate not yet effective (starts ${rules.interimRebates.effectiveFrom})`,
    };
  }
  if (now > expiresAt) {
    return {
      amountSGD: 0,
      valid: false,
      exclusionReason: `Rebate expired on ${rules.interimRebates.expiresAt}`,
    };
  }

  const tierTable: RebateTier[] = (rules.interimRebates.byServiceTier as Record<
    string,
    RebateTier[]
  >)[serviceTier];

  if (!tierTable) {
    return {
      amountSGD: 0,
      valid: false,
      exclusionReason: `No rebate table for service tier ${serviceTier}`,
    };
  }

  for (const tier of tierTable) {
    if (tier.pchiMaxSGD === null || pchi <= tier.pchiMaxSGD) {
      return { amountSGD: tier.rebateSGD, valid: tier.rebateSGD > 0 };
    }
  }

  return { amountSGD: 0, valid: false, exclusionReason: 'PCHI exceeds top tier' };
}
